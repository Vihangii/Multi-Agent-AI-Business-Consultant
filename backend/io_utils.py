"""
Shared upload parsing used by both the FastAPI endpoints and the Streamlit
dashboard (in built-in mode), so a file is interpreted the same way no matter
which entry point receives it.
"""

import io

import pandas as pd

from backend.agents.data_agent import find_date_column, find_revenue_column
from backend.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB

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
    return {
        "columns": [str(c) for c in df.columns],
        "row_count": int(len(df)),
        "detected_date_column": find_date_column(df),
        "detected_revenue_column": find_revenue_column(df),
        "preview": df.head(5).astype(str).to_dict(orient="records"),
    }
