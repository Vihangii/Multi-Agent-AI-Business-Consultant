"""
Shared upload parsing and inspection for the API endpoints: validation,
CSV/Excel parsing, allow-listed remote download and column inspection.
"""

import io
from fnmatch import fnmatch
from urllib.parse import urlsplit

import httpx
import pandas as pd

from backend.agents.data_agent import find_date_column, find_revenue_column, numeric_columns
from backend.config import FILE_URL_ALLOWED_HOSTS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")


class UploadError(ValueError):
    """Raised for user-fixable upload problems (bad type, too big, unparseable)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    """
    Validate and parse an uploaded CSV/Excel file into a DataFrame.

    Raises:
        UploadError: with ``status_code`` 400 (bad extension / empty),
            413 (too large) or 422 (cannot be parsed as a table).
    """
    lower = (filename or "").lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise UploadError(
            "Unsupported file format. Please upload a .csv, .xlsx, or .xls file.", 400
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadError(f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB.", 413)
    if not content:
        raise UploadError("Uploaded file is empty.", 400)

    try:
        if lower.endswith(".csv"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(io.BytesIO(content), encoding="latin-1")
        return pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise UploadError(
            f"Could not parse the uploaded file as a valid table. Error: {e}", 422
        ) from e


def inspect_dataframe(df: pd.DataFrame) -> dict:
    """Column names, auto-detection result and a short preview of a DataFrame."""
    date_col = find_date_column(df)
    revenue_col = find_revenue_column(df)
    return {
        "columns": [str(c) for c in df.columns],
        "row_count": int(len(df)),
        "detected_date_column": date_col,
        "detected_revenue_column": revenue_col,
        # Candidates for a what-if driver column (numeric, not date/revenue)
        "numeric_columns": numeric_columns(df, exclude=tuple(c for c in (date_col, revenue_col) if c)),
        "preview": df.head(5).astype(str).to_dict(orient="records"),
    }


def _host_allowed(host: str) -> bool:
    host = host.lower()
    return any(
        fnmatch(host, pattern) if "*" in pattern else host == pattern
        for pattern in FILE_URL_ALLOWED_HOSTS
    )


def fetch_remote_file(url: str, timeout: float = 30.0) -> tuple[str, bytes]:
    """
    Download a previously uploaded file (e.g. from Vercel Blob) for analysis.

    The host must be on FILE_URL_ALLOWED_HOSTS and the body is streamed so a
    download is abandoned as soon as it exceeds MAX_UPLOAD_BYTES.

    Returns:
        (filename, content) — filename is the last path segment of the URL.

    Raises:
        UploadError: 400 for a bad/forbidden URL, 413 for an oversized file,
            422 if the download fails.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UploadError("file_url must be an http(s) URL.", 400)
    if not _host_allowed(parts.hostname):
        raise UploadError(
            f"Downloads from '{parts.hostname}' are not allowed. "
            f"Permitted hosts: {', '.join(FILE_URL_ALLOWED_HOSTS)}",
            400,
        )

    filename = parts.path.rsplit("/", 1)[-1] or "upload"
    lower = filename.lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise UploadError(
            "Unsupported file format. The URL must end in .csv, .xlsx, or .xls.", 400
        )

    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
            resp.raise_for_status()
            declared = resp.headers.get("content-length")
            if declared and int(declared) > MAX_UPLOAD_BYTES:
                raise UploadError(
                    f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB.", 413
                )
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_UPLOAD_BYTES:
                    raise UploadError(
                        f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB.", 413
                    )
    except UploadError:
        raise
    except httpx.HTTPError as e:
        raise UploadError(f"Could not download file_url: {e}", 422) from e

    return filename, bytes(buf)
