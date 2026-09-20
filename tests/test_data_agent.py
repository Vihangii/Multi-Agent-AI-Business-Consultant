import numpy as np
import pandas as pd
import pytest

from backend.agents.data_agent import (
    analyze_data,
    clean_dataframe,
    find_date_column,
    find_revenue_column,
)


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "columns, expected",
    [
        (["Date", "Revenue"], "Date"),
        (["order_date", "amount"], "order_date"),
        (["OrderDate", "amount"], "OrderDate"),
        (["Transaction Date", "amount"], "Transaction Date"),
        (["created_at", "amount"], "created_at"),
    ],
)
def test_find_date_column_by_alias(columns, expected):
    df = pd.DataFrame({c: ["2024-01-01"] * 3 for c in columns})
    assert find_date_column(df) == expected


def test_find_date_column_ignores_substring_false_positives():
    # "holiday" contains "day", "lifetime_value" contains "time"; neither is a date column
    df = pd.DataFrame({
        "holiday": [0, 1, 0],
        "lifetime_value": [10.0, 20.0, 30.0],
        "when": ["2024-01-01", "2024-01-02", "2024-01-03"],
    })
    assert find_date_column(df) == "when"  # found via datetime parsing fallback


def test_find_date_column_does_not_pick_numeric_year_like_columns():
    df = pd.DataFrame({"units": [2019, 2020, 2021], "revenue": [1.0, 2.0, 3.0]})
    assert find_date_column(df) is None


@pytest.mark.parametrize(
    "columns, expected",
    [
        (["date", "Revenue"], "Revenue"),
        (["date", "total_sales"], "total_sales"),
        (["date", "GrossRevenue"], "GrossRevenue"),
        (["date", "Sales Amount"], "Sales Amount"),
    ],
)
def test_find_revenue_column_by_alias(columns, expected):
    df = pd.DataFrame({c: [1, 2, 3] for c in columns})
    assert find_revenue_column(df) == expected


def test_find_revenue_column_prefers_real_revenue_over_unit_price():
    df = pd.DataFrame({
        "date": ["2024-01-01"] * 3,
        "unit_price": [9.99, 9.99, 9.99],
        "revenue_usd": [100.0, 200.0, 300.0],
    })
    assert find_revenue_column(df) == "revenue_usd"


def test_find_revenue_column_falls_back_to_highest_variance_numeric():
    df = pd.DataFrame({
        "date": ["2024-01-01"] * 4,
        "qty": [1, 1, 1, 2],
        "foo": [100.0, 5000.0, 20.0, 9000.0],
    })
    assert find_revenue_column(df) == "foo"


def test_find_columns_return_none_when_nothing_matches():
    df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
    assert find_date_column(df) is None
    assert find_revenue_column(df) is None


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def test_clean_dataframe_parses_currency_strings_and_aggregates_dates():
    df = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-01", "2024-01-01", "bad", "2024-01-03"],
        "revenue": ["$1,000.50", "200", "300", "5", "-10"],
    })
    cleaned = clean_dataframe(df, "date", "revenue")

    assert list(cleaned.columns) == ["ds", "y"]
    # "bad" date dropped, negative dropped, duplicates summed, sorted ascending
    assert cleaned["ds"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert cleaned["y"].tolist() == [500.0, 1000.5]


def test_clean_dataframe_returns_empty_when_nothing_parses():
    df = pd.DataFrame({"date": ["x", "y"], "revenue": ["a", "b"]})
    assert clean_dataframe(df, "date", "revenue").empty


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def test_analyze_data_basic_stats(daily_df):
    cleaned = clean_dataframe(daily_df, "date", "revenue")
    stats = analyze_data(cleaned)

    assert stats["total_records"] == len(cleaned)
    assert stats["date_range"]["start"] == "2024-01-01"
    assert stats["revenue"]["total"] == pytest.approx(float(cleaned["y"].sum()), rel=1e-6)
    assert stats["growth"]["direction"] == "increasing"
    assert "monthly" in stats
    assert "volatility" in stats


def test_analyze_data_handles_zero_revenue_month_without_inf():
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    y = np.where(dates.month == 2, 0.0, 100.0)  # entire February is zero
    stats = analyze_data(pd.DataFrame({"ds": dates, "y": y}))

    for v in stats["volatility"].values():
        assert np.isfinite(v)


def test_analyze_data_empty_returns_error():
    assert "error" in analyze_data(pd.DataFrame({"ds": [], "y": []}))
