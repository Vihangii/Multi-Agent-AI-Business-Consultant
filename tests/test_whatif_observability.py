"""What-if scenarios, language parameter, metrics, rate limiting, request ids."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import observability
from backend.agents import recommendation_agent as ra
from backend.agents.data_agent import clean_dataframe, numeric_columns
from backend.agents.forecast_agent import WHATIF_STEPS, forecast_revenue
from backend.main import app
from backend.observability import Metrics, RateLimiter

client = TestClient(app)


@pytest.fixture
def driver_df():
    rng = np.random.default_rng(0)
    d = pd.date_range("2024-01-01", periods=300)
    spend = 1000 + 300 * np.sin(np.arange(300) / 25) + rng.normal(0, 30, 300)
    rev = 100 + 0.8 * spend + np.linspace(0, 200, 300) + rng.normal(0, 30, 300)
    return pd.DataFrame({
        "date": d,
        "revenue": rev.round(2),
        "marketing_spend": spend.round(2),
        "region": ["N", "S"] * 150,
        "units": rng.integers(1, 50, 300),
    })


# --- data agent -----------------------------------------------------------

def test_numeric_columns_excludes_date_revenue_and_text(driver_df):
    cols = numeric_columns(driver_df, exclude=("date", "revenue"))
    assert cols == ["marketing_spend", "units"]


def test_numeric_columns_accepts_currency_strings():
    df = pd.DataFrame({"spend": ["$1,000", "$2,000", "$3,000"], "note": ["a", "b", "c"]})
    assert numeric_columns(df) == ["spend"]


def test_clean_dataframe_carries_extra_column_and_aggregates(driver_df):
    df = pd.concat([driver_df.head(3), driver_df.head(1)])  # duplicate first date
    cleaned = clean_dataframe(df, "date", "revenue", extra_cols=["marketing_spend"])
    assert list(cleaned.columns) == ["ds", "y", "marketing_spend"]
    assert len(cleaned) == 3
    assert cleaned["marketing_spend"].iloc[0] == pytest.approx(2 * driver_df["marketing_spend"].iloc[0])


# --- forecast agent -------------------------------------------------------

@pytest.mark.slow
def test_whatif_with_regressor_learns_elasticity(driver_df):
    cleaned = clean_dataframe(driver_df, "date", "revenue", extra_cols=["marketing_spend"])
    out = forecast_revenue(cleaned, periods=20, frequency="D", regressor="marketing_spend")

    w = out["whatif"]
    assert w["driver"] == "marketing_spend"
    assert w["method"] == "regressor"
    assert w["steps"] == WHATIF_STEPS
    assert [s["change_percent"] for s in w["scenarios"]] == WHATIF_STEPS

    by_pct = {s["change_percent"]: s for s in w["scenarios"]}
    assert by_pct[0]["delta_vs_baseline_percent"] == 0
    # more spend -> more revenue, monotonic, and not a 1:1 passthrough
    assert by_pct[10]["total_forecasted"] > by_pct[0]["total_forecasted"] > by_pct[-10]["total_forecasted"]
    assert 0 < by_pct[10]["delta_vs_baseline_percent"] < 10
    assert len(by_pct[10]["series"]) == 20
    assert out["summary"]["regressor"] == "marketing_spend"


@pytest.mark.slow
def test_whatif_without_regressor_is_uplift(daily_df):
    cleaned = clean_dataframe(daily_df, "date", "revenue")
    out = forecast_revenue(cleaned, periods=10, frequency="D")
    w = out["whatif"]
    assert w["driver"] is None and w["method"] == "uplift"
    by_pct = {s["change_percent"]: s for s in w["scenarios"]}
    assert by_pct[20]["delta_vs_baseline_percent"] == pytest.approx(20.0, abs=0.01)


def test_forecast_rejects_missing_regressor(daily_df):
    cleaned = clean_dataframe(daily_df, "date", "revenue")
    with pytest.raises(ValueError, match="Regressor column"):
        forecast_revenue(cleaned, regressor="nope")


# --- recommendation agent -------------------------------------------------

def test_language_instruction():
    assert ra._language_instruction(None) == ""
    assert ra._language_instruction("english") == ""
    assert "Spanish" in ra._language_instruction("Spanish")


def test_prompt_includes_whatif_only_with_driver():
    whatif = {
        "driver": "spend", "baseline_driver_value": 100,
        "scenarios": [{"change_percent": 10, "total_forecasted": 1100, "delta_vs_baseline_percent": 10.0}],
    }
    assert "What-if Scenarios" in ra._build_user_prompt({}, {}, whatif)
    assert "What-if Scenarios" not in ra._build_user_prompt({}, {}, {"driver": None, "scenarios": []})


# --- API ------------------------------------------------------------------

def test_health_lists_languages_and_limits():
    body = client.get("/health").json()
    assert "Spanish" in body["languages"]
    assert body["whatif_steps"] == WHATIF_STEPS
    assert "rate_limit_per_minute" in body


def test_inspect_returns_numeric_columns(driver_df):
    csv = driver_df.to_csv(index=False).encode()
    r = client.post("/inspect", files={"file": ("d.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.json()["numeric_columns"] == ["marketing_spend", "units"]


def test_analyze_rejects_unknown_regressor(daily_csv_bytes):
    r = client.post(
        "/analyze",
        files={"file": ("s.csv", daily_csv_bytes, "text/csv")},
        params={"skip_recommendations": True, "regressor_column": "nope"},
    )
    assert r.status_code == 400
    assert "driver column 'nope' does not exist" in r.json()["detail"]


def test_analyze_rejects_text_regressor(driver_df):
    csv = driver_df.to_csv(index=False).encode()
    r = client.post(
        "/analyze",
        files={"file": ("d.csv", csv, "text/csv")},
        params={"skip_recommendations": True, "regressor_column": "region"},
    )
    assert r.status_code == 400
    assert "not numeric enough" in r.json()["detail"]


@pytest.mark.slow
def test_analyze_with_regressor_returns_whatif(driver_df):
    csv = driver_df.to_csv(index=False).encode()
    r = client.post(
        "/analyze",
        files={"file": ("d.csv", csv, "text/csv")},
        params={"skip_recommendations": True, "regressor_column": "marketing_spend", "periods": 7, "frequency": "D"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["regressor_column"] == "marketing_spend"
    assert body["whatif"]["method"] == "regressor"
    assert len(body["whatif"]["scenarios"]) == len(WHATIF_STEPS)


def test_metrics_endpoint_exposes_prometheus_text():
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "http_requests_total{" in r.text
    assert 'route="/health"' in r.text
    assert "http_request_duration_seconds_bucket" in r.text
    assert "process_uptime_seconds" in r.text


def test_request_id_header_roundtrip():
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    r2 = client.get("/health")
    assert len(r2.headers["x-request-id"]) >= 8
    assert "Server-Timing" in r2.headers or "server-timing" in r2.headers


# --- rate limiter ---------------------------------------------------------

def test_rate_limiter_token_bucket():
    rl = RateLimiter(per_minute=2)
    assert rl.check("a")[0] and rl.check("a")[0]
    allowed, wait = rl.check("a")
    assert not allowed and wait > 0
    assert rl.check("b")[0]  # separate client


def test_rate_limiter_disabled():
    rl = RateLimiter(per_minute=0)
    assert all(rl.check("a")[0] for _ in range(100))


def test_analyze_is_rate_limited(monkeypatch, daily_csv_bytes):
    monkeypatch.setattr(observability, "rate_limiter", RateLimiter(per_minute=1))
    files = {"file": ("s.csv", daily_csv_bytes, "text/csv")}
    # first request consumes the token (it may fail for other reasons; only the limiter matters)
    client.post("/analyze", files=files, params={"skip_recommendations": True, "date_column": "nope"})
    r = client.post("/analyze", files=files, params={"skip_recommendations": True, "date_column": "nope"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert "Rate limit" in r.json()["detail"]
    # /inspect and /health are not limited
    assert client.get("/health").status_code == 200


def test_metrics_registry_render_counts():
    m = Metrics()
    m.observe("GET", "/x", 200, 0.02)
    m.observe("GET", "/x", 500, 3.0)
    m.record_pipeline("success")
    text = m.render()
    assert 'http_requests_total{method="GET",route="/x",status="200"} 1' in text
    assert 'http_request_duration_seconds_count{method="GET",route="/x"} 2' in text
    assert 'pipeline_runs_total{outcome="success"} 1' in text
