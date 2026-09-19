"""Tests for /inspect, column overrides, API-key auth and backtest metrics."""

import pytest
from fastapi.testclient import TestClient

from backend import main as main_module
from backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# /inspect
# ---------------------------------------------------------------------------

def test_inspect_returns_columns_and_detection(daily_csv_bytes):
    r = client.post("/inspect", files={"file": ("sales.csv", daily_csv_bytes, "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["columns"] == ["date", "revenue"]
    assert body["detected_date_column"] == "date"
    assert body["detected_revenue_column"] == "revenue"
    assert body["row_count"] == 400
    assert len(body["preview"]) == 5


def test_inspect_rejects_bad_extension():
    r = client.post("/inspect", files={"file": ("x.json", b"{}", "application/json")})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Column overrides
# ---------------------------------------------------------------------------

def test_analyze_rejects_unknown_column_override(daily_csv_bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        params={"skip_recommendations": True, "date_column": "nope"},
    )
    assert r.status_code == 400
    assert "does not exist" in r.json()["detail"]
    assert "date, revenue" in r.json()["detail"]  # lists available columns


def test_analyze_rejects_same_column_for_both(daily_csv_bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        params={"skip_recommendations": True, "date_column": "date", "revenue_column": "date"},
    )
    assert r.status_code == 400
    assert "must be different" in r.json()["detail"]


@pytest.mark.slow
def test_analyze_uses_column_overrides(daily_df):
    # Rename columns to something detection would never find, then override
    df = daily_df.rename(columns={"date": "colA", "revenue": "colB"})
    csv = df.to_csv(index=False).encode()
    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", csv, "text/csv")},
        params={"skip_recommendations": True, "periods": 7, "frequency": "D",
                "date_column": "colA", "revenue_column": "colB"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date_column"] == "colA"
    assert body["revenue_column"] == "colB"
    assert body["columns"] == ["colA", "colB"]


# ---------------------------------------------------------------------------
# Backtest accuracy
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_analyze_includes_backtest_accuracy(daily_csv_bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        params={"skip_recommendations": True, "periods": 7, "frequency": "D"},
    )
    assert r.status_code == 200, r.text
    acc = r.json()["forecast_summary"]["accuracy"]
    assert acc["holdout_points"] == 80  # 20% of 400
    assert 0 <= acc["mape_percent"] < 100
    assert 0 <= acc["interval_coverage_percent"] <= 100
    assert acc["rating"] in {"excellent", "good", "fair", "poor"}


def test_backtest_skipped_when_too_little_data():
    import pandas as pd
    from backend.agents.forecast_agent import MIN_DATA_POINTS, _backtest

    df = pd.DataFrame({
        "ds": pd.date_range("2024-01-01", periods=MIN_DATA_POINTS + 1, freq="D"),
        "y": range(MIN_DATA_POINTS + 1),
    })
    assert _backtest(df, "daily") is None


# ---------------------------------------------------------------------------
# API-key auth
# ---------------------------------------------------------------------------

@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(main_module, "API_KEY", "s3cret")


def test_auth_open_when_key_unset(daily_csv_bytes, monkeypatch):
    monkeypatch.setattr(main_module, "API_KEY", None)
    r = client.post("/inspect", files={"file": ("sales.csv", daily_csv_bytes, "text/csv")})
    assert r.status_code == 200


def test_auth_rejects_missing_key(secured, daily_csv_bytes):
    r = client.post("/inspect", files={"file": ("sales.csv", daily_csv_bytes, "text/csv")})
    assert r.status_code == 401


def test_auth_rejects_wrong_key(secured, daily_csv_bytes):
    r = client.post(
        "/inspect",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401


def test_auth_accepts_correct_key(secured, daily_csv_bytes):
    r = client.post(
        "/inspect",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        headers={"X-API-Key": "s3cret"},
    )
    assert r.status_code == 200


def test_health_reports_auth_status(secured):
    assert client.get("/health").json()["auth_required"] is True
