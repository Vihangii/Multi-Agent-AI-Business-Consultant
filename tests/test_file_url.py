"""Tests for the file_url ingestion path used on Vercel (bodies > 4.5 MB)."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from backend import io_utils
from backend.io_utils import UploadError, fetch_remote_file
from backend.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def file_server(request):
    """Serves whatever bytes are registered in `files` under /<name>."""
    files: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            name = self.path.lstrip("/").split("?")[0]
            body = files.get(name)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            if "nolength" not in self.path:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}", files
    srv.shutdown()


@pytest.fixture(autouse=True)
def allow_localhost(monkeypatch):
    monkeypatch.setattr(io_utils, "FILE_URL_ALLOWED_HOSTS", ["127.0.0.1", "*.public.blob.vercel-storage.com"])


def test_fetch_remote_file_ok(file_server, daily_csv_bytes):
    base, files = file_server
    files["sales.csv"] = daily_csv_bytes
    name, content = fetch_remote_file(f"{base}/sales.csv")
    assert name == "sales.csv"
    assert content == daily_csv_bytes


def test_fetch_rejects_disallowed_host():
    with pytest.raises(UploadError) as exc:
        fetch_remote_file("https://evil.example.com/x.csv")
    assert exc.value.status_code == 400
    assert "not allowed" in str(exc.value)


def test_fetch_wildcard_host_matches():
    assert io_utils._host_allowed("abc123.public.blob.vercel-storage.com")
    assert not io_utils._host_allowed("public.blob.vercel-storage.com.evil.com")


@pytest.mark.parametrize("url", ["ftp://127.0.0.1/x.csv", "not a url", "file:///etc/passwd"])
def test_fetch_rejects_non_http(url):
    with pytest.raises(UploadError) as exc:
        fetch_remote_file(url)
    assert exc.value.status_code == 400


def test_fetch_rejects_bad_extension(file_server):
    base, files = file_server
    files["data.json"] = b"{}"
    with pytest.raises(UploadError) as exc:
        fetch_remote_file(f"{base}/data.json")
    assert exc.value.status_code == 400


def test_fetch_rejects_oversized_by_content_length(file_server, monkeypatch):
    base, files = file_server
    monkeypatch.setattr(io_utils, "MAX_UPLOAD_BYTES", 100)
    files["big.csv"] = b"x" * 101
    with pytest.raises(UploadError) as exc:
        fetch_remote_file(f"{base}/big.csv")
    assert exc.value.status_code == 413


def test_fetch_rejects_oversized_while_streaming(file_server, monkeypatch):
    base, files = file_server
    monkeypatch.setattr(io_utils, "MAX_UPLOAD_BYTES", 100)
    files["big.csv"] = b"x" * 101
    with pytest.raises(UploadError) as exc:
        fetch_remote_file(f"{base}/big.csv?nolength")  # no Content-Length header
    assert exc.value.status_code == 413


def test_fetch_404_is_422(file_server):
    base, _ = file_server
    with pytest.raises(UploadError) as exc:
        fetch_remote_file(f"{base}/missing.csv")
    assert exc.value.status_code == 422


# --- through the API -------------------------------------------------------

def test_inspect_via_file_url(file_server, daily_csv_bytes):
    base, files = file_server
    files["sales.csv"] = daily_csv_bytes
    r = client.post("/inspect", data={"file_url": f"{base}/sales.csv"})
    assert r.status_code == 200, r.text
    assert r.json()["detected_date_column"] == "date"


def test_inspect_via_file_url_query_param(file_server, daily_csv_bytes):
    base, files = file_server
    files["sales.csv"] = daily_csv_bytes
    r = client.post("/inspect", params={"file_url": f"{base}/sales.csv"})
    assert r.status_code == 200, r.text


def test_analyze_requires_file_or_url():
    r = client.post("/analyze", params={"skip_recommendations": True})
    assert r.status_code == 400
    assert "file_url" in r.json()["detail"]


def test_analyze_disallowed_host_is_400():
    r = client.post("/analyze", data={"file_url": "https://evil.example.com/x.csv"})
    assert r.status_code == 400


@pytest.mark.slow
def test_analyze_via_file_url(file_server, daily_csv_bytes):
    base, files = file_server
    files["sales.csv"] = daily_csv_bytes
    r = client.post(
        "/analyze",
        data={"file_url": f"{base}/sales.csv"},
        params={"skip_recommendations": True, "periods": 7, "frequency": "D"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["forecast_summary"]["forecast_periods"] == 7


def test_health_reports_platform():
    body = client.get("/health").json()
    assert body["platform"] in {"server", "vercel"}
    assert "max_multipart_mb" in body
    assert isinstance(body["file_url_allowed_hosts"], list)
