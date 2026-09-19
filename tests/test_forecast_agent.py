import math

import pandas as pd
import pytest

from backend.agents.data_agent import clean_dataframe
from backend.agents.forecast_agent import (
    MIN_DATA_POINTS,
    forecast_revenue,
    prepare_prophet_data,
)


def test_prepare_prophet_data_rejects_too_few_rows():
    df = pd.DataFrame({
        "ds": pd.date_range("2024-01-01", periods=MIN_DATA_POINTS - 1),
        "y": range(MIN_DATA_POINTS - 1),
    })
    with pytest.raises(ValueError, match="Not enough data"):
        prepare_prophet_data(df)


def test_forecast_rejects_unknown_frequency(daily_df):
    cleaned = clean_dataframe(daily_df, "date", "revenue")
    with pytest.raises(ValueError, match="Unsupported frequency"):
        forecast_revenue(cleaned, frequency="H")


@pytest.mark.slow
def test_forecast_daily_autodetect(daily_df):
    cleaned = clean_dataframe(daily_df, "date", "revenue")
    out = forecast_revenue(cleaned)

    summary = out["summary"]
    assert summary["data_granularity"] == "daily"
    assert summary["forecast_frequency"] == "D"
    assert summary["forecast_periods"] == 180

    fdf = out["forecast_df"]
    assert list(fdf.columns) == ["ds", "predicted", "lower_bound", "upper_bound"]
    future = fdf[fdf["ds"] > cleaned["ds"].max()]
    assert len(future) == 180
    assert summary["forecast_trend"] in {"upward", "downward", "flat"}
    assert isinstance(summary["predicted_growth_percent"], float)


@pytest.mark.slow
def test_forecast_monthly_with_overrides(monthly_df):
    cleaned = clean_dataframe(monthly_df, "month", "sales")
    out = forecast_revenue(cleaned, periods=3, frequency="MS")

    summary = out["summary"]
    assert summary["data_granularity"] == "monthly"
    assert summary["forecast_periods"] == 3
    future = out["forecast_df"][out["forecast_df"]["ds"] > cleaned["ds"].max()]
    assert len(future) == 3
    assert summary["forecast_trend"] == "upward"  # data is a rising line


@pytest.mark.slow
def test_forecast_zero_last_actual_does_not_produce_inf():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    y = [100.0] * 59 + [0.0]  # last observed value is zero
    out = forecast_revenue(pd.DataFrame({"ds": dates, "y": y}), periods=5)

    summary = out["summary"]
    assert summary["predicted_growth_percent"] is None  # JSON null rather than inf/nan
    assert summary["forecast_trend"] == "undetermined"
    for v in summary.values():
        if isinstance(v, float):
            assert math.isfinite(v)
