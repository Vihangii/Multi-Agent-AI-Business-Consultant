import pytest
from fastapi.testclient import TestClient

from backend import main as main_module
from backend import orchestrator
from backend.agents import recommendation_agent as ra
from backend.main import app

client = TestClient(app)


def test_root_and_health():
    assert client.get("/").status_code == 200
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert "openai_configured" in body


def test_analyze_rejects_bad_extension():
    r = client.post("/analyze", files={"file": ("data.txt", b"a,b\n1,2", "text/plain")})
    assert r.status_code == 400


def test_analyze_rejects_empty_file():
    r = client.post("/analyze", files={"file": ("data.csv", b"", "text/csv")})
    assert r.status_code == 400


def test_analyze_rejects_oversized_file(monkeypatch):
    from backend import io_utils
    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(io_utils, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/analyze", files={"file": ("data.csv", b"x" * 11, "text/csv")})
    assert r.status_code == 413


def test_analyze_rejects_unparseable_columns():
    csv = b"foo,bar\nx,y\nz,w\n"
    r = client.post(
        "/analyze",
        files={"file": ("data.csv", csv, "text/csv")},
        params={"skip_recommendations": True},
    )
    assert r.status_code == 400
    assert "date column" in r.json()["detail"]


@pytest.mark.slow
def test_analyze_end_to_end_skip_recommendations(daily_csv_bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        params={"skip_recommendations": True, "periods": 14, "frequency": "D"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["date_column"] == "date"
    assert body["revenue_column"] == "revenue"
    assert body["forecast_summary"]["forecast_periods"] == 14
    assert "recommendations" not in body
    assert "recommendations_error" not in body


@pytest.mark.slow
def test_analyze_reports_recommendation_failure_without_failing_pipeline(daily_csv_bytes, monkeypatch):
    def boom(**kwargs):
        raise ra.RecommendationError("no key configured")
    monkeypatch.setattr(orchestrator, "generate_recommendations", boom)

    r = client.post(
        "/analyze",
        files={"file": ("sales.csv", daily_csv_bytes, "text/csv")},
        params={"periods": 7, "frequency": "D"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "recommendations" not in body
    assert body["recommendations_error"] == "no key configured"
