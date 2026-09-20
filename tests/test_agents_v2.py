"""Provider abstraction, tool-using strategist, critic and anomaly agents."""

import json

import numpy as np
import pandas as pd
import pytest

from backend import llm as llm_mod
from backend.agents import critic_agent, recommendation_agent as ra
from backend.agents.anomaly_agent import anomalies_for_prompt, detect_anomalies
from backend.agents.strategist_tools import (
    TOOL_SPECS,
    TOOLS,
    DataContext,
    execute_tool,
    what_if,
)
from backend.llm import AnthropicProvider, LLMResponse, ToolCall, ToolSpec, set_llm


# ---------------------------------------------------------------------------
# Fake provider: scripted responses, records every call
# ---------------------------------------------------------------------------

class FakeLLM:
    provider = "fake"
    model = "fake-1"

    def __init__(self, responses, supports_tools=True):
        self.responses = list(responses)
        self.supports_tools = supports_tools
        self.calls = []  # (messages, tools, kwargs)

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append((list(messages), tools, kwargs))
        if not self.responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def _reset_llm():
    set_llm(None)
    yield
    set_llm(None)


@pytest.fixture
def ctx(daily_df):
    from backend.agents.data_agent import analyze_data, clean_dataframe

    cleaned = clean_dataframe(daily_df, "date", "revenue")
    analysis = analyze_data(cleaned)
    forecast_summary = {"data_granularity": "daily", "forecast_trend": "upward", "predicted_growth_percent": 4.2,
                        "forecast_periods": 30, "forecast_frequency": "D", "forecast_end_value": 900.0,
                        "accuracy": {"mape_percent": 5.1, "rating": "excellent"}}
    whatif = {"driver": "spend", "method": "regressor", "baseline_driver_value": 100.0, "steps": [-10, 0, 10],
              "scenarios": [
                  {"change_percent": -10, "driver_value": 90, "forecast_end_value": 850, "avg_forecasted_value": 800, "total_forecasted": 24000, "delta_vs_baseline": -2000, "delta_vs_baseline_percent": -7.7, "series": []},
                  {"change_percent": 0, "driver_value": 100, "forecast_end_value": 900, "avg_forecasted_value": 866, "total_forecasted": 26000, "delta_vs_baseline": 0, "delta_vs_baseline_percent": 0.0, "series": []},
                  {"change_percent": 10, "driver_value": 110, "forecast_end_value": 950, "avg_forecasted_value": 933, "total_forecasted": 28000, "delta_vs_baseline": 2000, "delta_vs_baseline_percent": 7.7, "series": []},
              ]}
    anomalies = {"points": [{"date": "2024-03-01", "actual": 10.0, "expected": 600.0, "deviation": -590.0, "deviation_percent": -98.3,
                             "z_score": -6.1, "direction": "drop", "severity": "high", "outside_interval": True}],
                 "periods": [], "summary": {"point_count": 1, "spike_count": 0, "drop_count": 1, "largest_drop": None,
                                            "largest_spike": None, "period_count": 0, "anomalous_share_percent": 0.25}}
    return DataContext(cleaned_df=cleaned, analysis=analysis, forecast_summary=forecast_summary, whatif=whatif, anomalies=anomalies, granularity="daily")


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def test_resolve_provider_auto_prefers_anthropic_then_openai(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(llm_mod, "has_anthropic_key", lambda: True)
    monkeypatch.setattr(llm_mod, "has_openai_key", lambda: True)
    assert llm_mod.resolve_provider() == "anthropic"
    monkeypatch.setattr(llm_mod, "has_anthropic_key", lambda: False)
    assert llm_mod.resolve_provider() == "openai"
    monkeypatch.setattr(llm_mod, "has_openai_key", lambda: False)
    monkeypatch.setattr(llm_mod, "OLLAMA_MODEL", None)
    assert llm_mod.resolve_provider() is None
    monkeypatch.setattr(llm_mod, "OLLAMA_MODEL", "llama3.1")
    assert llm_mod.resolve_provider() == "ollama"


def test_resolve_provider_forced_without_key_is_none(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(llm_mod, "has_anthropic_key", lambda: False)
    assert llm_mod.resolve_provider() is None
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "bogus")
    assert llm_mod.resolve_provider() is None


def test_get_llm_raises_helpful_error(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_mod, "OLLAMA_MODEL", None)
    with pytest.raises(llm_mod.LLMNotConfigured, match="OLLAMA_MODEL"):
        llm_mod.get_llm()


def test_anthropic_message_conversion_groups_tool_results():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("t1", "a", {"x": 1}), ToolCall("t2", "b", {})]},
        {"role": "tool", "tool_call_id": "t1", "name": "a", "content": "r1"},
        {"role": "tool", "tool_call_id": "t2", "name": "b", "content": "r2"},
        {"role": "assistant", "content": "done"},
    ]
    system, converted = AnthropicProvider.to_anthropic(messages)
    assert system == "sys"
    assert converted[0] == {"role": "user", "content": "hi"}
    assert [b["type"] for b in converted[1]["content"]] == ["tool_use", "tool_use"]
    assert converted[1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "a", "input": {"x": 1}}
    # both results in ONE user message
    assert converted[2]["role"] == "user"
    assert [b["tool_use_id"] for b in converted[2]["content"]] == ["t1", "t2"]
    assert converted[3] == {"role": "assistant", "content": [{"type": "text", "text": "done"}]}


def test_openai_message_conversion_roundtrip():
    from backend.llm import OpenAIProvider

    messages = [
        {"role": "assistant", "content": None, "tool_calls": [ToolCall("c1", "what_if", {"change_percent": 10})]},
        {"role": "tool", "tool_call_id": "c1", "name": "what_if", "content": "{}"},
    ]
    out = OpenAIProvider._to_openai(messages)
    assert out[0]["tool_calls"][0]["function"] == {"name": "what_if", "arguments": '{"change_percent": 10}'}
    assert out[1] == {"role": "tool", "tool_call_id": "c1", "content": "{}"}


def test_parse_args_tolerates_bad_json():
    assert llm_mod._parse_args('{"a": 1}') == {"a": 1}
    assert llm_mod._parse_args({"b": 2}) == {"b": 2}
    assert llm_mod._parse_args("not json") == {}
    assert llm_mod._parse_args("") == {}


# ---------------------------------------------------------------------------
# Strategist tools
# ---------------------------------------------------------------------------

def test_tool_specs_cover_all_tools():
    assert {t.name for t in TOOL_SPECS} == set(TOOLS)
    for t in TOOL_SPECS:
        assert t.parameters["type"] == "object"


def test_monthly_breakdown_and_top_periods(ctx):
    months = json.loads(execute_tool(ctx, "get_monthly_breakdown", {"last_n": 3}))["months"]
    assert len(months) == 3 and months[-1]["change_percent"] is not None
    best = json.loads(execute_tool(ctx, "get_top_periods", {"kind": "best", "n": 2}))["periods"]
    worst = json.loads(execute_tool(ctx, "get_top_periods", {"kind": "worst", "n": 2}))["periods"]
    assert best[0]["revenue"] >= worst[0]["revenue"]


def test_compare_periods_and_weekday(ctx):
    r = json.loads(execute_tool(ctx, "compare_periods", {"start_a": "2024-01-01", "end_a": "2024-01-31", "start_b": "2024-02-01", "end_b": "2024-02-29"}))
    assert r["period_a"]["records"] == 31 and r["period_b"]["records"] == 29
    w = json.loads(execute_tool(ctx, "get_weekday_profile", {}))
    assert len(w["weekdays"]) == 7


def test_what_if_interpolates_and_clamps(ctx):
    r = json.loads(what_if(ctx, 5))
    assert r["scenario"]["total_forecasted"] == pytest.approx(27000)
    assert "interpolation" in r["note"]
    r = json.loads(what_if(ctx, 40))
    assert r["scenario"]["change_percent"] == 10 and "clamped" in r["note"]


def test_execute_tool_errors_are_json_not_exceptions(ctx):
    assert "Unknown tool" in json.loads(execute_tool(ctx, "nope", {}))["error"]
    assert "Bad arguments" in json.loads(execute_tool(ctx, "what_if", {"wrong": 1}))["error"]
    assert "error" in json.loads(execute_tool(ctx, "compare_periods", {"start_a": "x", "end_a": "y", "start_b": "z", "end_b": "w"}))


# ---------------------------------------------------------------------------
# Strategist loop
# ---------------------------------------------------------------------------

def test_run_strategist_tool_loop(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    fake = FakeLLM([
        LLMResponse(text="", tool_calls=[ToolCall("1", "get_monthly_breakdown", {"last_n": 2}), ToolCall("2", "get_anomalies", {})], stop_reason="tool_use", usage={"input_tokens": 10, "output_tokens": 5}),
        LLMResponse(text="", tool_calls=[ToolCall("3", "what_if", {"change_percent": 10})], stop_reason="tool_use", usage={"input_tokens": 20, "output_tokens": 5}),
        LLMResponse(text="## 📊 Executive Summary\nGrowth is strong.", usage={"input_tokens": 30, "output_tokens": 50}),
    ])
    set_llm(fake)
    out = ra.run_strategist(ctx, language="English")

    assert out.mode == "tools" and out.provider == "fake"
    assert out.report.startswith("## 📊 Executive Summary")
    assert [t["tool"] for t in out.tool_calls] == ["get_monthly_breakdown", "get_anomalies", "what_if"]
    assert out.rounds == 2
    assert out.usage == {"input_tokens": 60, "output_tokens": 60}
    # tools offered on every turn; tool results fed back with matching ids
    assert all(call[1] is not None for call in fake.calls)
    last_messages = fake.calls[-1][0]
    tool_msgs = [m for m in last_messages if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["1", "2", "3"]
    assert "Anomaly summary" in fake.calls[0][0][1]["content"]


def test_run_strategist_caps_rounds(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    monkeypatch.setattr(ra, "AGENT_MAX_TOOL_ROUNDS", 2)
    fake = FakeLLM([
        LLMResponse(text="", tool_calls=[ToolCall("1", "get_forecast_summary", {})], stop_reason="tool_use"),
        LLMResponse(text="", tool_calls=[ToolCall("2", "get_forecast_summary", {})], stop_reason="tool_use"),
        LLMResponse(text="final report"),  # answer to the forced "write it now" turn (no tools offered)
    ])
    set_llm(fake)
    out = ra.run_strategist(ctx)
    assert out.report == "final report" and out.rounds == 2
    assert fake.calls[-1][1] is None  # tools withheld on the final call
    assert "Write the final report now" in fake.calls[-1][0][-1]["content"]


def test_run_strategist_static_when_tools_unsupported(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    fake = FakeLLM([LLMResponse(text="static report")], supports_tools=False)
    set_llm(fake)
    out = ra.run_strategist(ctx)
    assert out.mode == "static" and out.report == "static report" and out.tool_calls == []
    assert fake.calls[0][1] is None
    assert "Anomalies" in fake.calls[0][0][1]["content"]


def test_run_strategist_static_mode_setting(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "static")
    fake = FakeLLM([LLMResponse(text="static report")])
    set_llm(fake)
    assert ra.run_strategist(ctx).mode == "static"


def test_run_strategist_wraps_errors(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    set_llm(FakeLLM([RuntimeError("boom")]))
    with pytest.raises(ra.RecommendationError, match="boom"):
        ra.run_strategist(ctx)


def test_run_strategist_empty_answer_is_error(ctx, monkeypatch):
    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    set_llm(FakeLLM([LLMResponse(text="   ")]))
    with pytest.raises(ra.RecommendationError, match="empty"):
        ra.run_strategist(ctx)


def test_generate_recommendations_not_configured(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_mod, "has_openai_key", lambda: False)
    with pytest.raises(ra.RecommendationError, match="OPENAI_API_KEY"):
        ra.generate_recommendations({}, {})


# ---------------------------------------------------------------------------
# Critic
# ---------------------------------------------------------------------------

def _facts():
    return {"analysis": {"growth": {"overall_percent": 8.7}}, "forecast_summary": {"forecast_trend": "upward"}}


def test_critic_passes_when_no_issues():
    fake = FakeLLM([LLMResponse(text=json.dumps({"issues": [], "revised_report": "same"}))])
    r = critic_agent.review_report("Growth was 8.7%.", _facts(), llm=fake)
    assert r.status == "passed" and r.issues == [] and r.revised_report is None
    assert fake.calls[0][2]["json_mode"] is True
    assert "FACTS" in fake.calls[0][0][1]["content"]


def test_critic_corrects_report():
    report = "## Summary\nGrowth was 12% and the outlook is upward. " * 3
    revised = report.replace("12%", "8.7%")
    fake = FakeLLM([LLMResponse(text="```json\n" + json.dumps({
        "issues": [{"claim": "Growth was 12%", "correct_value": "8.7%", "section": "Summary"}],
        "revised_report": revised,
    }) + "\n```")])
    r = critic_agent.review_report(report, _facts(), llm=fake)
    assert r.status == "corrected" and len(r.issues) == 1
    assert r.revised_report == revised
    assert r.to_dict()["corrections"] == 1


def test_critic_keeps_original_when_rewrite_truncated():
    report = "A long report " * 50
    fake = FakeLLM([LLMResponse(text=json.dumps({"issues": [{"claim": "x", "correct_value": "y", "section": "s"}], "revised_report": "too short"}))])
    r = critic_agent.review_report(report, _facts(), llm=fake)
    assert r.status == "corrected" and r.revised_report is None and "incomplete" in r.note


def test_critic_unverified_on_garbage_or_failure():
    r = critic_agent.review_report("r", _facts(), llm=FakeLLM([LLMResponse(text="not json at all")]))
    assert r.status == "unverified"
    r = critic_agent.review_report("r", _facts(), llm=FakeLLM([RuntimeError("down")]))
    assert r.status == "unverified" and "down" in r.note


def test_critic_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(llm_mod, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_mod, "has_openai_key", lambda: False)
    assert critic_agent.review_report("r", _facts()).status == "skipped"


def test_build_facts_sheet_strips_series():
    facts = critic_agent.build_facts_sheet({}, {}, {"driver": "d", "method": "regressor", "baseline_driver_value": 1,
                                                    "scenarios": [{"change_percent": 0, "series": [1, 2, 3]}]}, None, [{"month": "2024-01"}])
    assert "series" not in facts["whatif"]["scenarios"][0]
    assert facts["monthly_revenue"] == [{"month": "2024-01"}]


# ---------------------------------------------------------------------------
# Anomaly agent
# ---------------------------------------------------------------------------

def _series_with_shocks():
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    rng = np.random.default_rng(1)
    y = 500 + np.linspace(0, 50, 200) + rng.normal(0, 10, 200)
    y[100] = 20.0     # collapse
    y[150] = 1500.0   # spike
    cleaned = pd.DataFrame({"ds": dates, "y": y})
    forecast = pd.DataFrame({"ds": dates, "predicted": 500 + np.linspace(0, 50, 200),
                             "lower_bound": 470 + np.linspace(0, 50, 200), "upper_bound": 530 + np.linspace(0, 50, 200)})
    return cleaned, forecast


def test_detect_anomalies_finds_drop_and_spike():
    cleaned, forecast = _series_with_shocks()
    a = detect_anomalies(cleaned, forecast)
    dates = {p["date"]: p for p in a["points"]}
    assert "2024-04-10" in dates and dates["2024-04-10"]["direction"] == "drop" and dates["2024-04-10"]["severity"] == "high"
    assert "2024-05-30" in dates and dates["2024-05-30"]["direction"] == "spike"
    assert a["summary"]["drop_count"] >= 1 and a["summary"]["spike_count"] >= 1
    assert a["summary"]["largest_drop"]["date"] == "2024-04-10"
    assert all(p["outside_interval"] for p in a["points"] if p["severity"] == "high")


def test_detect_anomalies_monthly_shock():
    dates = pd.date_range("2024-01-01", periods=240, freq="D")
    y = np.full(240, 100.0)
    y[(dates.month == 5)] = 20.0  # May collapses
    cleaned = pd.DataFrame({"ds": dates, "y": y})
    forecast = pd.DataFrame({"ds": dates, "predicted": y, "lower_bound": y - 5, "upper_bound": y + 5})  # residuals zero
    a = detect_anomalies(cleaned, forecast)
    assert a["points"] == []
    periods = {p["period"]: p for p in a["periods"]}
    assert "2024-05" in periods and periods["2024-05"]["direction"] == "drop"
    assert "2024-06" in periods and periods["2024-06"]["direction"] == "spike"


def test_detect_anomalies_clean_series_is_empty():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    y = 100 + np.sin(np.arange(60) / 5)
    cleaned = pd.DataFrame({"ds": dates, "y": y})
    forecast = pd.DataFrame({"ds": dates, "predicted": y, "lower_bound": y - 1, "upper_bound": y + 1})
    a = detect_anomalies(cleaned, forecast)
    assert a["points"] == [] and a["periods"] == [] and a["summary"]["point_count"] == 0


def test_anomalies_for_prompt():
    assert "No significant anomalies" in anomalies_for_prompt(None)
    cleaned, forecast = _series_with_shocks()
    text = anomalies_for_prompt(detect_anomalies(cleaned, forecast))
    assert "2024-04-10" in text and "one-off" in text


# ---------------------------------------------------------------------------
# Full pipeline with the fake provider: anomalies → strategist tools → critic
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_end_to_end_with_fake_llm(monkeypatch):
    from backend import orchestrator
    from backend.orchestrator import run_pipeline

    monkeypatch.setattr(ra, "STRATEGIST_MODE", "tools")
    monkeypatch.setattr(orchestrator, "CRITIC_ENABLED", True)

    rng = np.random.default_rng(3)
    dates = pd.date_range("2024-01-01", periods=300, freq="D")
    y = 400 + np.linspace(0, 100, 300) + rng.normal(0, 15, 300)
    y[200] = 5.0  # one collapsed day
    df = pd.DataFrame({"date": dates, "revenue": y.round(2)})

    draft = "## 📊 Executive Summary\nGrowth was 99% and revenue collapsed on 2024-07-19."
    fixed = draft.replace("99%", "24.7%")
    fake = FakeLLM([
        LLMResponse(text="", tool_calls=[ToolCall("1", "get_monthly_breakdown", {}), ToolCall("2", "get_anomalies", {"limit": 5})], stop_reason="tool_use"),
        LLMResponse(text=draft),
        LLMResponse(text=json.dumps({"issues": [{"claim": "Growth was 99%", "correct_value": "24.7%", "section": "Executive Summary"}], "revised_report": fixed})),
    ])
    set_llm(fake)

    r = run_pipeline(df=df, periods=7, frequency="D")
    assert r.success, r.error
    assert r.anomalies["summary"]["drop_count"] >= 1
    assert r.anomalies["summary"]["largest_drop"]["date"] == "2024-07-19"
    assert r.recommendations == fixed
    assert r.agent["mode"] == "tools"
    assert [t["tool"] for t in r.agent["tool_calls"]] == ["get_monthly_breakdown", "get_anomalies"]
    assert r.agent["qa"]["status"] == "corrected" and r.agent["qa"]["corrections"] == 1
    assert r.agent["original_report"] == draft
    # the anomaly the tool returned really is the collapsed day
    assert "2024-07-19" in r.agent["tool_calls"][1]["result_preview"]
    # the critic saw the facts sheet with monthly revenue
    critic_prompt = fake.calls[2][0][1]["content"]
    assert "monthly_revenue" in critic_prompt and "anomalies" in critic_prompt
    out = r.to_dict()
    assert "anomalies" in out and out["agent"]["qa"]["issues"][0]["correct_value"] == "24.7%"


@pytest.mark.slow
def test_pipeline_critic_disabled_and_static_mode(monkeypatch):
    from backend import orchestrator
    from backend.orchestrator import run_pipeline

    monkeypatch.setattr(ra, "STRATEGIST_MODE", "static")
    monkeypatch.setattr(orchestrator, "CRITIC_ENABLED", False)
    set_llm(FakeLLM([LLMResponse(text="static report")]))
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    r = run_pipeline(df=pd.DataFrame({"date": dates, "revenue": np.linspace(100, 200, 120)}), periods=5, frequency="D")
    assert r.success and r.recommendations == "static report"
    assert r.agent["mode"] == "static" and r.agent["qa"]["status"] == "skipped"
