"""
Forecast Agent
Uses Facebook Prophet to generate revenue forecasts.
"""

import pandas as pd
from prophet import Prophet


# Supported Prophet frequency aliases and the ~6-month default horizon for each
DEFAULT_PERIODS = {"D": 180, "W": 26, "MS": 6}
SUPPORTED_FREQUENCIES = frozenset(DEFAULT_PERIODS)

# Prophet technically fits on 2 points, but anything under ~10 produces
# meaningless trends and often fails inside the optimiser.
MIN_DATA_POINTS = 10


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
        ValueError: If data has fewer than MIN_DATA_POINTS rows after preparation.
    """
    prophet_df = df[["ds", "y"]].copy()

    # Ensure correct types
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
    prophet_df["y"] = pd.to_numeric(prophet_df["y"], errors="coerce")

    # Drop any remaining nulls
    prophet_df = prophet_df.dropna()

    # Sort chronologically
    prophet_df = prophet_df.sort_values("ds").reset_index(drop=True)

    if len(prophet_df) < MIN_DATA_POINTS:
        raise ValueError(
            f"Not enough data for forecasting. Got {len(prophet_df)} rows, "
            f"need at least {MIN_DATA_POINTS}."
        )

    return prophet_df


def forecast_revenue(
    df: pd.DataFrame,
    periods: int | None = None,
    frequency: str | None = None,
    backtest: bool = True,
) -> dict:
    """
    Generate a revenue forecast using Prophet.

    Args:
        df: Cleaned DataFrame with 'ds' and 'y' columns.
        periods: Number of future periods to forecast. If None, a ~6-month
            horizon is chosen based on the detected data granularity.
        frequency: Frequency of predictions — 'D' (daily), 'W' (weekly),
            'MS' (month start). If None, auto-detected from the data.
        backtest: If True, also fit on the first ~80% of the history and
            score the model on the held-out tail (MAPE / MAE / coverage).

    Returns:
        Dictionary containing:
          - forecast_df: Full forecast DataFrame (historical + future).
          - summary: Key forecast metrics and insights, including an
            ``accuracy`` block when backtesting ran.

    Raises:
        ValueError: If *frequency* is not one of the supported values.
    """
    # Prepare data
    prophet_df = prepare_prophet_data(df)

    # Detect data granularity from the median gap between observations
    date_diffs = prophet_df["ds"].diff().dropna().dt.days
    median_diff = date_diffs.median()

    if median_diff >= 25:
        detected_freq, default_periods, data_granularity = "MS", 6, "monthly"
    elif median_diff >= 6:
        detected_freq, default_periods, data_granularity = "W", 26, "weekly"
    else:
        detected_freq, default_periods, data_granularity = "D", 180, "daily"

    # Only fall back to auto-detected values when the caller did not specify
    if frequency is None:
        frequency = detected_freq
    elif frequency not in SUPPORTED_FREQUENCIES:
        raise ValueError(
            f"Unsupported frequency '{frequency}'. "
            f"Choose one of: {', '.join(sorted(SUPPORTED_FREQUENCIES))}."
        )
    if periods is None:
        periods = default_periods if frequency == detected_freq else DEFAULT_PERIODS[frequency]

    # Configure and fit Prophet model
    model = _fit_model(prophet_df, data_granularity)

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
    predicted_growth = _safe_growth_percent(last_actual, final_predicted)

    summary = {
        "data_granularity": data_granularity,
        "forecast_frequency": frequency,
        "forecast_periods": periods,
        "last_actual_date": str(last_historical_date.date()),
        "last_actual_value": round(last_actual, 2),
        "forecast_end_date": str(future_forecast["ds"].iloc[-1].date()),
        "forecast_end_value": round(final_predicted, 2),
        "predicted_growth_percent": predicted_growth,
        "forecast_trend": _trend_label(predicted_growth),
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

    if backtest:
        accuracy = _backtest(prophet_df, data_granularity)
        if accuracy is not None:
            summary["accuracy"] = accuracy

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


def _safe_growth_percent(baseline: float, final: float) -> float | None:
    """
    Percentage change from *baseline* to *final*.

    Returns None (JSON null) instead of inf/nan when the baseline is zero,
    which is a legal value since cleaning keeps y >= 0.
    """
    if baseline == 0 or baseline != baseline:  # zero or NaN
        return None
    return round(((final - baseline) / baseline) * 100, 2)


def _trend_label(growth_percent: float | None) -> str:
    if growth_percent is None:
        return "undetermined"
    if growth_percent > 0:
        return "upward"
    if growth_percent < 0:
        return "downward"
    return "flat"


def _fit_model(prophet_df: pd.DataFrame, data_granularity: str) -> Prophet:
    """Build and fit a Prophet model with settings appropriate to the data."""
    span_days = (prophet_df["ds"].max() - prophet_df["ds"].min()).days
    model = Prophet(
        yearly_seasonality=(span_days >= 365),
        weekly_seasonality=(data_granularity == "daily"),
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_mode="multiplicative",
        interval_width=0.95,
    )
    model.fit(prophet_df)
    return model


# Fraction of history held out for the backtest, and the minimum train size
BACKTEST_HOLDOUT = 0.2
BACKTEST_MIN_TRAIN = MIN_DATA_POINTS


def _backtest(prophet_df: pd.DataFrame, data_granularity: str) -> dict | None:
    """
    Fit on the first (1 - BACKTEST_HOLDOUT) of the history and score the
    prediction on the held-out tail.

    Returns None when there is not enough data to hold anything out.
    """
    n = len(prophet_df)
    n_test = max(1, int(n * BACKTEST_HOLDOUT))
    n_train = n - n_test
    if n_train < BACKTEST_MIN_TRAIN:
        return None

    train = prophet_df.iloc[:n_train]
    test = prophet_df.iloc[n_train:]

    model = _fit_model(train, data_granularity)
    pred = model.predict(test[["ds"]])

    actual = test["y"].to_numpy(dtype=float)
    yhat = pred["yhat"].to_numpy(dtype=float)
    lower = pred["yhat_lower"].to_numpy(dtype=float)
    upper = pred["yhat_upper"].to_numpy(dtype=float)

    abs_err = abs(actual - yhat)
    nonzero = actual != 0
    mape = float((abs_err[nonzero] / actual[nonzero]).mean() * 100) if nonzero.any() else None
    coverage = float(((actual >= lower) & (actual <= upper)).mean() * 100)

    return {
        "holdout_points": int(n_test),
        "holdout_start": str(test["ds"].iloc[0].date()),
        "holdout_end": str(test["ds"].iloc[-1].date()),
        "mae": round(float(abs_err.mean()), 2),
        "mape_percent": round(mape, 2) if mape is not None else None,
        "interval_coverage_percent": round(coverage, 2),
        "rating": _accuracy_rating(mape),
    }


def _accuracy_rating(mape: float | None) -> str:
    """Plain-language label for a MAPE value (common forecasting rule of thumb)."""
    if mape is None:
        return "unknown"
    if mape < 10:
        return "excellent"
    if mape < 20:
        return "good"
    if mape < 50:
        return "fair"
    return "poor"
