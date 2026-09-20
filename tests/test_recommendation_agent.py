import pytest

from backend import llm as llm_mod
from backend.agents import recommendation_agent as ra
from backend.llm import LLMResponse, set_llm


class _Fake:
    provider = "fake"
    model = "fake-1"
    supports_tools = True

    def __init__(self, text=None, exc=None):
        self.text, self.exc = text, exc

    def chat(self, messages, tools=None, **kwargs):
        if self.exc:
            raise self.exc
        return LLMResponse(text=self.text)


@pytest.fixture(autouse=True)
def reset_client():
    set_llm(None)
    yield
    set_llm(None)


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


def test_generate_raises_when_no_provider(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(llm_mod, "has_anthropic_key", lambda: False)
    monkeypatch.setattr(llm_mod, "has_openai_key", lambda: False)
    monkeypatch.setattr(llm_mod, "OLLAMA_MODEL", None)
    with pytest.raises(ra.RecommendationError, match="No LLM provider"):
        ra.generate_recommendations({}, {})


def test_generate_returns_model_output():
    set_llm(_Fake(text="## Report"))
    assert ra.generate_recommendations({}, {}) == "## Report"


def test_generate_raises_on_empty_output():
    set_llm(_Fake(text="   "))
    with pytest.raises(ra.RecommendationError, match="empty"):
        ra.generate_recommendations({}, {})


def test_generate_wraps_api_errors():
    set_llm(_Fake(exc=RuntimeError("boom")))
    with pytest.raises(ra.RecommendationError, match="boom"):
        ra.generate_recommendations({}, {})


def test_generate_includes_anomalies_in_prompt():
    class Capture(_Fake):
        def chat(self, messages, tools=None, **kwargs):
            self.messages = messages
            return LLMResponse(text="ok")

    fake = Capture()
    set_llm(fake)
    anomalies = {"points": [{"date": "2024-03-01", "actual": 1.0, "expected": 100.0, "deviation": -99.0, "deviation_percent": -99.0,
                             "z_score": -7.0, "direction": "drop", "severity": "high", "outside_interval": True}],
                 "periods": [], "summary": {"point_count": 1, "spike_count": 0, "drop_count": 1, "period_count": 0, "anomalous_share_percent": 1.0}}
    ra.generate_recommendations({}, {}, anomalies=anomalies)
    assert "2024-03-01" in fake.messages[1]["content"]
