from types import SimpleNamespace

import pytest

from backend.agents import recommendation_agent as ra


@pytest.fixture(autouse=True)
def reset_client():
    ra._client = None
    yield
    ra._client = None


def _fake_client(content):
    def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_build_user_prompt_tolerates_missing_fields():
    # Both dicts empty: every fallback path is exercised and nothing raises
    prompt = ra._build_user_prompt({}, {})
    assert "Total Revenue: N/A" in prompt
    assert "Overall Growth" not in prompt  # optional section omitted


def test_build_user_prompt_formats_numbers():
    analysis = {"revenue": {"total": 1234567.891, "mean": 10}}
    forecast = {
        "predicted_growth_percent": 12.3456,
        "confidence_interval": {"lower": 1, "upper": 2},
    }
    prompt = ra._build_user_prompt(analysis, forecast)
    assert "$1,234,567.89" in prompt
    assert "$10.00" in prompt
    assert "12.35%" in prompt
    assert "$1.00 to $2.00" in prompt


def test_generate_raises_when_no_api_key(monkeypatch):
    def no_key():
        raise ValueError("no key")
    monkeypatch.setattr(ra, "require_openai_key", no_key)
    with pytest.raises(ra.RecommendationError, match="no key"):
        ra.generate_recommendations({}, {})


def test_generate_returns_model_output(monkeypatch):
    monkeypatch.setattr(ra, "_get_client", lambda: _fake_client("## Report"))
    assert ra.generate_recommendations({}, {}) == "## Report"


def test_generate_raises_on_empty_output(monkeypatch):
    monkeypatch.setattr(ra, "_get_client", lambda: _fake_client("   "))
    with pytest.raises(ra.RecommendationError, match="empty"):
        ra.generate_recommendations({}, {})


def test_generate_wraps_api_errors(monkeypatch):
    def create(**kwargs):
        raise RuntimeError("boom")
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ra, "_get_client", lambda: client)
    with pytest.raises(ra.RecommendationError, match="boom"):
        ra.generate_recommendations({}, {})
