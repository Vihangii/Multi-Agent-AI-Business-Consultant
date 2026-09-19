import io

import pandas as pd
import pytest

from backend import io_utils
from backend.io_utils import UploadError, inspect_dataframe, parse_upload


def test_parse_csv(daily_csv_bytes):
    df = parse_upload("sales.csv", daily_csv_bytes)
    assert list(df.columns) == ["date", "revenue"]
    assert len(df) == 400


def test_parse_excel(daily_df):
    buf = io.BytesIO()
    daily_df.to_excel(buf, index=False)
    df = parse_upload("sales.xlsx", buf.getvalue())
    assert list(df.columns) == ["date", "revenue"]
    assert len(df) == 400


def test_parse_latin1_fallback():
    content = "date,revenue\n2024-01-01,caf\xe9\n".encode("latin-1")
    df = parse_upload("x.csv", content)
    assert df["revenue"].iloc[0] == "café"


@pytest.mark.parametrize(
    "name, content, code",
    [
        ("x.txt", b"a,b\n1,2", 400),
        ("x.csv", b"", 400),
        ("x.xlsx", b"not an excel file", 422),
    ],
)
def test_parse_rejects(name, content, code):
    with pytest.raises(UploadError) as exc:
        parse_upload(name, content)
    assert exc.value.status_code == code


def test_parse_rejects_oversized(monkeypatch):
    monkeypatch.setattr(io_utils, "MAX_UPLOAD_BYTES", 5)
    with pytest.raises(UploadError) as exc:
        parse_upload("x.csv", b"a,b\n1,2\n")
    assert exc.value.status_code == 413


def test_inspect_dataframe(daily_df):
    info = inspect_dataframe(daily_df)
    assert info["columns"] == ["date", "revenue"]
    assert info["row_count"] == 400
    assert info["detected_date_column"] == "date"
    assert info["detected_revenue_column"] == "revenue"
    assert len(info["preview"]) == 5
    assert all(isinstance(v, str) for row in info["preview"] for v in row.values())
