"""
Recommendation (Strategist) Agent
Turns the analysis, forecast, scenarios and anomalies into an actionable
strategy report. Two modes:

  - tools (default): the model is given function-calling tools
    (monthly breakdown, top/worst periods, period comparison, weekday
    profile, anomalies, what-if) and queries the data itself before writing.
  - static: one prompt with a pre-built summary — used when the provider or
    model has no tool support, or STRATEGIST_MODE=static.

Works with any provider from backend.llm (OpenAI, Anthropic, Ollama).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from backend.agents.anomaly_agent import anomalies_for_prompt
from backend.agents.strategist_tools import TOOL_SPECS, DataContext, execute_tool
from backend.config import AGENT_MAX_TOOL_ROUNDS, STRATEGIST_MODE
from backend.llm import LLMClient, LLMNotConfigured, get_llm

logger = logging.getLogger(__name__)


class RecommendationError(Exception):
    """Raised when the recommendation stage cannot produce a report."""


@dataclass
class StrategistResult:
    report: str
    mode: str  # "tools" | "static"
    provider: str
    model: str
    tool_calls: list[dict] = field(default_factory=list)  # trace: name, arguments, result_preview, ms
    rounds: int = 0
    usage: dict = field(default_factory=dict)


def _money(value) -> str:
    """Format a number as $1,234.56; pass non-numeric values (e.g. 'N/A') through."""
    if isinstance(value, (int, float)):
        return f"${value:,.2f}"
    return str(value)


def _pct(value) -> str:
    """Format a number as 12.34%; pass non-numeric values through."""
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"
    return str(value)

SYSTEM_PROMPT = """You are an elite business strategy consultant with 20+ years of experience 
advising Fortune 500 companies. You specialize in data-driven decision making, revenue optimization, 
and growth strategy.

Your task is to analyze the provided business data and forecasts, then deliver a comprehensive 
strategic report. Your recommendations must be:

1. SPECIFIC — Include concrete actions, not vague advice.
2. DATA-DRIVEN — Reference the actual numbers from the analysis.
3. PRIORITIZED — Rank recommendations by potential impact.
4. ACTIONABLE — Each recommendation should have clear implementation steps.

Structure your response in the following format:

## 📊 Executive Summary
A 2-3 sentence overview of the business's current state and trajectory.

## 🔍 Key Findings
Bullet points of the most important insights from the data.

## ⚠️ Risk Assessment
Identify potential risks based on the data trends and volatility.

## 🚀 Strategic Recommendations
Provide 5-7 numbered recommendations, each with:
- **What**: The specific action to take
- **Why**: Data-backed justification
- **Impact**: Expected outcome (quantify where possible)
- **Timeline**: Suggested implementation timeframe

## 📈 Growth Opportunities
Identify 2-3 untapped growth opportunities based on the patterns you see.

## 🎯 90-Day Action Plan
A prioritized list of immediate actions for the next 90 days.

Use professional language but keep it accessible. Include relevant emojis for visual clarity."""

# Languages offered by the UI. Any other string is passed through to the model as-is.
SUPPORTED_LANGUAGES = [
    "English", "Spanish", "French", "German", "Portuguese", "Italian", "Dutch",
    "Sinhala", "Tamil", "Hindi", "Arabic", "Chinese (Simplified)", "Japanese", "Korean",
]


TOOLS_ADDENDUM = """

You have tools that query the underlying data. Before writing the report:
1. Call get_monthly_breakdown and get_anomalies at minimum.
2. Use get_top_periods, compare_periods, get_weekday_profile and what_if wherever a
   recommendation would benefit from a concrete number — cite the numbers you retrieve.
3. For every anomaly, state whether you treat it as a one-off (excluded from planning)
   or a signal (acted on), and why.
Only quote figures you obtained from the data or the tools. When you have what you
need, write the full report in the required format as your final answer."""


def _language_instruction(language: str | None) -> str:
    lang = (language or "English").strip()
    if lang.lower() in ("", "en", "english"):
        return ""
    return (
        f"\n\nIMPORTANT: Write the ENTIRE report in {lang}. Keep the section structure, "
        "markdown formatting and emojis; translate all headings and content. "
        "Keep numbers, currency symbols and dates in their original form."
    )


def _build_user_prompt(analysis: dict, forecast_summary: dict, whatif: dict | None = None) -> str:
    """
    Build a detailed user prompt from analysis and forecast data.

    Args:
        analysis: Dictionary from data_agent.analyze_data().
        forecast_summary: Dictionary from forecast_agent.forecast_revenue()['summary'].

    Returns:
        Formatted prompt string.
    """
    rev = analysis.get("revenue", {})
    prompt = f"""Analyze the following business data and provide your strategic recommendations.

--- DATA ANALYSIS RESULTS ---

📅 Date Range: {analysis.get('date_range', {}).get('start', 'N/A')} to {analysis.get('date_range', {}).get('end', 'N/A')} ({analysis.get('date_range', {}).get('span_days', 'N/A')} days)
📋 Total Records: {analysis.get('total_records', 'N/A')}

💰 Revenue Statistics:
  - Total Revenue: {_money(rev.get('total', 'N/A'))}
  - Average: {_money(rev.get('mean', 'N/A'))}
  - Median: {_money(rev.get('median', 'N/A'))}
  - Std Deviation: {_money(rev.get('std_dev', 'N/A'))}
  - Min: {_money(rev.get('min', 'N/A'))}
  - Max: {_money(rev.get('max', 'N/A'))}
"""

    # Growth metrics
    growth = analysis.get("growth", {})
    if growth:
        prompt += f"""
📈 Growth:
  - Overall Growth: {_pct(growth.get('overall_percent', 'N/A'))}
  - Direction: {growth.get('direction', 'N/A')}
"""

    # Monthly performance
    monthly = analysis.get("monthly", {})
    if monthly:
        prompt += f"""
📆 Monthly Performance:
  - Best Month: {monthly.get('best_month', 'N/A')} ({_money(monthly.get('best_month_revenue', 0))})
  - Worst Month: {monthly.get('worst_month', 'N/A')} ({_money(monthly.get('worst_month_revenue', 0))})
  - Avg Monthly Revenue: {_money(monthly.get('avg_monthly_revenue', 0))}
"""

    # Volatility
    volatility = analysis.get("volatility", {})
    if volatility:
        prompt += f"""
📊 Volatility:
  - Avg Monthly Change: {_pct(volatility.get('avg_monthly_change_percent', 'N/A'))}
  - Max Monthly Drop: {_pct(volatility.get('max_monthly_drop_percent', 'N/A'))}
  - Max Monthly Spike: {_pct(volatility.get('max_monthly_spike_percent', 'N/A'))}
"""

    # Forecast summary
    ci = forecast_summary.get("confidence_interval", {})
    prompt += f"""
--- FORECAST RESULTS ({forecast_summary.get('forecast_periods', '?')} x '{forecast_summary.get('forecast_frequency', '?')}' periods) ---

🔮 Forecast Details:
  - Data Granularity: {forecast_summary.get('data_granularity', 'N/A')}
  - Last Actual Value: {_money(forecast_summary.get('last_actual_value', 0))} ({forecast_summary.get('last_actual_date', 'N/A')})
  - Forecast End Value: {_money(forecast_summary.get('forecast_end_value', 0))} ({forecast_summary.get('forecast_end_date', 'N/A')})
  - Predicted Growth: {_pct(forecast_summary.get('predicted_growth_percent', 'N/A'))}
  - Trend: {forecast_summary.get('forecast_trend', 'N/A')}
  - Confidence Range: {_money(ci.get('lower', 0))} to {_money(ci.get('upper', 0))}
  - Avg Forecasted Value: {_money(forecast_summary.get('avg_forecasted_value', 0))}
  - Peak Forecast: {_money(forecast_summary.get('peak_forecasted_value', 0))} ({forecast_summary.get('peak_forecasted_date', 'N/A')})
"""

    # What-if scenarios (only meaningful with a real driver column)
    if whatif and whatif.get("driver") and whatif.get("scenarios"):
        lines = []
        for sc in whatif["scenarios"]:
            if sc.get("change_percent") == 0:
                continue
            lines.append(
                f"  - {sc['change_percent']:+d}% {whatif['driver']}: total forecast "
                f"{_money(sc.get('total_forecasted', 0))} ({_pct(sc.get('delta_vs_baseline_percent'))} vs baseline)"
            )
        prompt += f"""
🎛️ What-if Scenarios (driver: {whatif['driver']}, current level {whatif.get('baseline_driver_value', 'N/A')}):
""" + "\n".join(lines) + "\n"

    prompt += "\nBased on this data, provide your comprehensive strategic analysis and recommendations."

    return prompt


def _llm() -> LLMClient:
    try:
        return get_llm()
    except LLMNotConfigured as e:
        raise RecommendationError(str(e)) from e


def generate_recommendations(
    analysis: dict,
    forecast_summary: dict,
    whatif: dict | None = None,
    language: str | None = None,
    anomalies: dict | None = None,
) -> str:
    """
    Static mode: one prompt, one answer. Kept as the fallback for providers
    without tool support and as a simple entry point for library use.

    Raises:
        RecommendationError: If no provider is configured, the request fails,
            or the model returns an empty response.
    """
    user_prompt = _build_user_prompt(analysis, forecast_summary, whatif)
    if anomalies:
        user_prompt += "\n\n🚨 Anomalies:\n" + anomalies_for_prompt(anomalies)
    system_prompt = SYSTEM_PROMPT + _language_instruction(language)
    llm = _llm()

    try:
        response = llm.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=4000,
            temperature=0.7,
        )
    except Exception as e:
        logger.error("%s request failed: %s", llm.provider, e)
        raise RecommendationError(f"{llm.provider} request failed: {e}") from e

    if not response.text or not response.text.strip():
        raise RecommendationError(f"{llm.provider} returned an empty response.")
    return response.text


def run_strategist(ctx: DataContext, language: str | None = None, mode: str | None = None) -> StrategistResult:
    """
    Produce the strategy report, letting the model query the data with tools.

    Falls back to static mode when tools are disabled or unsupported. The
    returned trace of tool calls is surfaced in the UI as "agent activity".

    Raises:
        RecommendationError: as generate_recommendations.
    """
    mode = (mode or STRATEGIST_MODE or "tools").lower()
    llm = _llm()
    if mode != "tools" or not getattr(llm, "supports_tools", False):
        report = generate_recommendations(ctx.analysis, ctx.forecast_summary, ctx.whatif, language, ctx.anomalies)
        return StrategistResult(report=report, mode="static", provider=llm.provider, model=llm.model)

    system_prompt = SYSTEM_PROMPT + TOOLS_ADDENDUM + _language_instruction(language)
    user_prompt = (
        _build_user_prompt(ctx.analysis, ctx.forecast_summary, ctx.whatif)
        + "\n\n🚨 Anomaly summary:\n" + anomalies_for_prompt(ctx.anomalies)
        + "\n\nUse the tools to investigate before answering."
    )
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    trace: list[dict] = []
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    rounds = 0

    try:
        while True:
            response = llm.chat(messages, TOOL_SPECS, max_tokens=4000, temperature=0.7)
            for k in usage_total:
                usage_total[k] += int(response.usage.get(k, 0) or 0)

            if not response.tool_calls:
                text = response.text.strip()
                if not text:
                    raise RecommendationError(f"{llm.provider} returned an empty response.")
                return StrategistResult(
                    report=text, mode="tools", provider=llm.provider, model=llm.model,
                    tool_calls=trace, rounds=rounds, usage=usage_total,
                )

            rounds += 1
            messages.append({"role": "assistant", "content": response.text or "", "tool_calls": response.tool_calls})
            for call in response.tool_calls:
                t0 = time.perf_counter()
                result = execute_tool(ctx, call.name, call.arguments)
                trace.append({
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result_preview": result[:300],
                    "ms": round((time.perf_counter() - t0) * 1000, 1),
                })
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result})

            if rounds >= AGENT_MAX_TOOL_ROUNDS:
                # Stop the loop: ask for the final answer without offering tools
                messages.append({"role": "user", "content": "You have gathered enough. Write the final report now, in the required format."})
                response = llm.chat(messages, None, max_tokens=4000, temperature=0.7)
                text = response.text.strip()
                if not text:
                    raise RecommendationError(f"{llm.provider} returned an empty response.")
                return StrategistResult(
                    report=text, mode="tools", provider=llm.provider, model=llm.model,
                    tool_calls=trace, rounds=rounds, usage=usage_total,
                )
    except RecommendationError:
        raise
    except Exception as e:
        logger.error("%s request failed: %s", llm.provider, e)
        raise RecommendationError(f"{llm.provider} request failed: {e}") from e
