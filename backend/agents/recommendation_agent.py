"""
Recommendation Agent
Uses OpenAI GPT-4o-mini to generate actionable business recommendations
based on data analysis and forecast results.
"""

import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY, OPENAI_MODEL


# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

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


def _build_user_prompt(analysis: dict, forecast_summary: dict) -> str:
    """
    Build a detailed user prompt from analysis and forecast data.

    Args:
        analysis: Dictionary from data_agent.analyze_data().
        forecast_summary: Dictionary from forecast_agent.forecast_revenue()['summary'].

    Returns:
        Formatted prompt string.
    """
    prompt = f"""Analyze the following business data and provide your strategic recommendations.

--- DATA ANALYSIS RESULTS ---

📅 Date Range: {analysis.get('date_range', {}).get('start', 'N/A')} to {analysis.get('date_range', {}).get('end', 'N/A')} ({analysis.get('date_range', {}).get('span_days', 'N/A')} days)
📋 Total Records: {analysis.get('total_records', 'N/A')}

💰 Revenue Statistics:
  - Total Revenue: ${analysis.get('revenue', {}).get('total', 'N/A'):,.2f}
  - Average: ${analysis.get('revenue', {}).get('mean', 'N/A'):,.2f}
  - Median: ${analysis.get('revenue', {}).get('median', 'N/A'):,.2f}
  - Std Deviation: ${analysis.get('revenue', {}).get('std_dev', 'N/A'):,.2f}
  - Min: ${analysis.get('revenue', {}).get('min', 'N/A'):,.2f}
  - Max: ${analysis.get('revenue', {}).get('max', 'N/A'):,.2f}
"""

    # Growth metrics
    growth = analysis.get("growth", {})
    if growth:
        prompt += f"""
📈 Growth:
  - Overall Growth: {growth.get('overall_percent', 'N/A')}%
  - Direction: {growth.get('direction', 'N/A')}
"""

    # Monthly performance
    monthly = analysis.get("monthly", {})
    if monthly:
        prompt += f"""
📆 Monthly Performance:
  - Best Month: {monthly.get('best_month', 'N/A')} (${monthly.get('best_month_revenue', 0):,.2f})
  - Worst Month: {monthly.get('worst_month', 'N/A')} (${monthly.get('worst_month_revenue', 0):,.2f})
  - Avg Monthly Revenue: ${monthly.get('avg_monthly_revenue', 0):,.2f}
"""

    # Volatility
    volatility = analysis.get("volatility", {})
    if volatility:
        prompt += f"""
📊 Volatility:
  - Avg Monthly Change: {volatility.get('avg_monthly_change_percent', 'N/A')}%
  - Max Monthly Drop: {volatility.get('max_monthly_drop_percent', 'N/A')}%
  - Max Monthly Spike: {volatility.get('max_monthly_spike_percent', 'N/A')}%
"""

    # Forecast summary
    prompt += f"""
--- FORECAST RESULTS (6-Month Outlook) ---

🔮 Forecast Details:
  - Data Granularity: {forecast_summary.get('data_granularity', 'N/A')}
  - Last Actual Value: ${forecast_summary.get('last_actual_value', 0):,.2f} ({forecast_summary.get('last_actual_date', 'N/A')})
  - Forecast End Value: ${forecast_summary.get('forecast_end_value', 0):,.2f} ({forecast_summary.get('forecast_end_date', 'N/A')})
  - Predicted Growth: {forecast_summary.get('predicted_growth_percent', 'N/A')}%
  - Trend: {forecast_summary.get('forecast_trend', 'N/A')}
  - Confidence Range: ${forecast_summary.get('confidence_interval', {}).get('lower', 0):,.2f} to ${forecast_summary.get('confidence_interval', {}).get('upper', 0):,.2f}
  - Avg Forecasted Value: ${forecast_summary.get('avg_forecasted_value', 0):,.2f}
  - Peak Forecast: ${forecast_summary.get('peak_forecasted_value', 0):,.2f} ({forecast_summary.get('peak_forecasted_date', 'N/A')})

Based on this data, provide your comprehensive strategic analysis and recommendations."""

    return prompt


def generate_recommendations(analysis: dict, forecast_summary: dict) -> str:
    """
    Generate AI-powered business recommendations using OpenAI.

    Args:
        analysis: Dictionary from data_agent.analyze_data().
        forecast_summary: Dictionary from forecast_agent.forecast_revenue()['summary'].

    Returns:
        Formatted string of business recommendations.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    user_prompt = _build_user_prompt(analysis, forecast_summary)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
            top_p=0.9,
        )

        recommendations = response.choices[0].message.content
        return recommendations

    except Exception as e:
        return (
            f"⚠️ Error generating recommendations: {str(e)}\n\n"
            "Please check your OpenAI API key and try again."
        )
