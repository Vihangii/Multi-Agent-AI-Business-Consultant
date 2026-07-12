"""
Forecast Agent
Uses Facebook Prophet to generate revenue forecasts.
"""

import pandas as pd
from prophet import Prophet


def prepare_prophet_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare and validate data for Prophet.

    Prophet requires a DataFrame with exactly two columns:
      - 'ds': datetime column
      - 'y': numeric target column

    This function ensures the data meets those requirements and handles
    edge cases like insufficient data points.

    Args:
        df: Cleaned DataFrame with 'ds' and 'y' columns.

    Returns:
        Prophet-ready DataFrame.

    Raises:
        ValueError: If data has fewer than 2 rows after preparation.
    """
    prophet_df = df[["ds", "y"]].copy()

    # Ensure correct types
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
    prophet_df["y"] = pd.to_numeric(prophet_df["y"], errors="coerce")

    # Drop any remaining nulls
    prophet_df = prophet_df.dropna()

    # Sort chronologically
    prophet_df = prophet_df.sort_values("ds").reset_index(drop=True)

    if len(prophet_df) < 2:
        raise ValueError(
            f"Not enough data for forecasting. Got {len(prophet_df)} rows, need at least 2."
        )

    return prophet_df


def forecast_revenue(
    df: pd.DataFrame,
    periods: int = 180,
    frequency: str = "D",
) -> dict:
    """
    Generate a revenue forecast using Prophet.

    Args:
        df: Cleaned DataFrame with 'ds' and 'y' columns.
        periods: Number of future periods to forecast (default: 180 days ≈ 6 months).
        frequency: Frequency of predictions — 'D' (daily), 'W' (weekly), 'M' (monthly).

    Returns:
        Dictionary containing:
          - forecast_df: Full forecast DataFrame (historical + future).
          - summary: Key forecast metrics and insights.
    """
    # Prepare data
    prophet_df = prepare_prophet_data(df)

    # Detect data frequency and adjust if needed
    date_diffs = prophet_df["ds"].diff().dropna().dt.days
    median_diff = date_diffs.median()

    # Auto-adjust frequency and periods based on data granularity
    if median_diff >= 25:
        # Monthly data
        frequency = "MS"
        periods = 6
        data_granularity = "monthly"
    elif median_diff >= 6:
        # Weekly data
        frequency = "W"
        periods = 26
        data_granularity = "weekly"
    else:
        # Daily data
        frequency = "D"
        periods = 180
        data_granularity = "daily"

    # Configure and fit Prophet model
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=(data_granularity == "daily"),
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_mode="multiplicative",
        interval_width=0.95,
    )

    # Suppress Prophet's verbose logging
    model.fit(prophet_df)

    # Create future dates DataFrame
    future = model.make_future_dataframe(periods=periods, freq=frequency)

    # Generate forecast
    forecast = model.predict(future)

    # Split into historical and future
    last_historical_date = prophet_df["ds"].max()
    future_forecast = forecast[forecast["ds"] > last_historical_date].copy()

    # Build summary
    last_actual = float(prophet_df["y"].iloc[-1])
    final_predicted = float(future_forecast["yhat"].iloc[-1])
    predicted_growth = ((final_predicted - last_actual) / last_actual) * 100

    summary = {
        "data_granularity": data_granularity,
        "forecast_periods": periods,
        "last_actual_date": str(last_historical_date.date()),
        "last_actual_value": round(last_actual, 2),
        "forecast_end_date": str(future_forecast["ds"].iloc[-1].date()),
        "forecast_end_value": round(final_predicted, 2),
        "predicted_growth_percent": round(predicted_growth, 2),
        "forecast_trend": "upward" if predicted_growth > 0 else "downward",
        "confidence_interval": {
            "lower": round(float(future_forecast["yhat_lower"].iloc[-1]), 2),
            "upper": round(float(future_forecast["yhat_upper"].iloc[-1]), 2),
        },
        "avg_forecasted_value": round(float(future_forecast["yhat"].mean()), 2),
        "peak_forecasted_value": round(float(future_forecast["yhat"].max()), 2),
        "peak_forecasted_date": str(
            future_forecast.loc[future_forecast["yhat"].idxmax(), "ds"].date()
        ),
    }

    # Build a simplified forecast DataFrame for plotting
    forecast_result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    forecast_result = forecast_result.rename(columns={
        "yhat": "predicted",
        "yhat_lower": "lower_bound",
        "yhat_upper": "upper_bound",
    })

    return {
        "forecast_df": forecast_result,
        "summary": summary,
    }
