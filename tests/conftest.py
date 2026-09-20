"""Shared fixtures for the test-suite."""

import io

import numpy as np
import pandas as pd
import pytest


def make_daily_df(days: int = 400, start: str = "2024-01-01", seed: int = 0) -> pd.DataFrame:
    """Synthetic daily revenue with trend + weekly seasonality + noise."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=days, freq="D")
    trend = np.linspace(500, 900, days)
    weekly = 100 * np.sin(2 * np.pi * dates.dayofweek / 7.0)
    noise = rng.normal(0, 40, days)
    revenue = np.clip(trend + weekly + noise, 50, None)
    return pd.DataFrame({"date": dates, "revenue": np.round(revenue, 2)})


def make_monthly_df(months: int = 30, start: str = "2022-01-01") -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=months, freq="MS")
    revenue = np.linspace(10_000, 25_000, months)
    return pd.DataFrame({"month": dates, "sales": revenue})


@pytest.fixture
def daily_df() -> pd.DataFrame:
    return make_daily_df()


@pytest.fixture
def monthly_df() -> pd.DataFrame:
    return make_monthly_df()


@pytest.fixture
def daily_csv_bytes(daily_df) -> bytes:
    buf = io.StringIO()
    daily_df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Each test starts with a fresh token bucket so the suite never rate-limits itself."""
    from backend import observability

    observability.rate_limiter.reset()
    yield
    observability.rate_limiter.reset()
