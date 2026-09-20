"""
Recommendation Agent
Uses OpenAI GPT-4o-mini to generate actionable business recommendations
based on data analysis and forecast results.
"""

import logging

from openai import OpenAI

from backend.config import OPENAI_MODEL, require_openai_key

logger = logging.getLogger(__name__)


class RecommendationError(Exception):
    """Raised when the recommendation stage cannot produce a report."""


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Create the OpenAI client on first use so importing this module never needs a key."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=require_openai_key())
    return _client


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


def generate_recommendations(
    analysis: dict,
    forecast_summary: dict,
    whatif: dict | None = None,
    language: str | None = None,
) -> str:
    """
    Generate AI-powered business recommendations using OpenAI.

    Args:
        analysis: Dictionary from data_agent.analyze_data().
        forecast_summary: Dictionary from forecast_agent.forecast_revenue()['summary'].
        whatif: Optional scenario table from forecast_revenue()['whatif'].
        language: Language for the report (default English).

    Returns:
        Formatted markdown string of business recommendations.

    Raises:
        RecommendationError: If no API key is configured, the API call fails,
            or the model returns an empty response.
    """
    user_prompt = _build_user_prompt(analysis, forecast_summary, whatif)
    system_prompt = SYSTEM_PROMPT + _language_instruction(language)

    try:
        client = _get_client()
    except ValueError as e:
        raise RecommendationError(str(e)) from e

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
            top_p=0.9,
        )
    except Exception as e:
        logger.error("OpenAI request failed: %s", e)
        raise RecommendationError(f"OpenAI request failed: {e}") from e

    recommendations = response.choices[0].message.content
    if not recommendations or not recommendations.strip():
        raise RecommendationError("OpenAI returned an empty response.")

    return recommendations
