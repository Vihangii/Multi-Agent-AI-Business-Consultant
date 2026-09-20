"""
Data Analysis Agent
Handles data loading, cleaning, column detection, and statistical analysis.
"""

import re

import pandas as pd
import numpy as np


# Common aliases for date and revenue columns across different datasets
DATE_ALIASES = [
    "date", "dates", "datetime", "timestamp", "time", "period",
    "month", "year", "day", "order_date", "transaction_date",
    "sale_date", "invoice_date", "created_at", "created_date",
]

REVENUE_ALIASES = [
    "revenue", "sales", "income", "total", "amount", "turnover",
    "gross_sales", "net_sales", "total_sales", "total_revenue",
    "sales_amount", "order_amount", "transaction_amount", "price",
    "unit_price", "gross_revenue", "net_revenue", "earnings",
]


def _tokens(name: str) -> list[str]:
    """Split a column name into lowercase word tokens: 'OrderDate' -> ['order', 'date']."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))  # camelCase -> camel Case
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def _match_by_alias(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """
    Find the column that best matches the alias list.

    Aliases are ordered strongest-first, so the first alias that matches any
    column wins. For each alias a whole-name match ('Revenue') is preferred
    over a whole-word match ('revenue_usd'). Matching is on word tokens, so
    'holiday' does not match 'day' and 'lifetime_value' does not match 'time'.
    """
    tokenised = {col: _tokens(col) for col in df.columns}

    for alias in aliases:
        alias_tokens = alias.split("_")

        for col, toks in tokenised.items():
            if toks == alias_tokens:
                return col

        for col, toks in tokenised.items():
            # alias tokens must appear as a contiguous run of whole tokens
            for i in range(len(toks) - len(alias_tokens) + 1):
                if toks[i:i + len(alias_tokens)] == alias_tokens:
                    return col
    return None


def find_date_column(df: pd.DataFrame) -> str | None:
    """
    Detect the date/time column in the DataFrame.

    Strategy:
      1. Match column names against known date aliases (case-insensitive).
      2. Fall back to checking if any column can be parsed as datetime.

    Args:
        df: Input DataFrame.

    Returns:
        Column name if found, otherwise None.
    """
    # Strategy 1 & 2: whole-name, then whole-word alias match
    match = _match_by_alias(df, DATE_ALIASES)
    if match is not None:
        return match

    # Strategy 3: Try parsing each non-numeric column as datetime
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue  # plain numbers (e.g. 2024) would parse as epoch timestamps
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.5:
                return col
        except Exception:
            continue

    return None


def find_revenue_column(df: pd.DataFrame) -> str | None:
    """
    Detect the revenue/sales column in the DataFrame.

    Strategy:
      1. Match column names against known revenue aliases (case-insensitive).
      2. Fall back to selecting the first numeric column with high variance.

    Args:
        df: Input DataFrame.

    Returns:
        Column name if found, otherwise None.
    """
    # Strategy 1 & 2: whole-name, then whole-word alias match
    match = _match_by_alias(df, REVENUE_ALIASES)
    if match is not None:
        return match

    # Strategy 3: Pick the numeric column with the highest standard deviation
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        std_values = {col: df[col].std() for col in numeric_cols}
        return max(std_values, key=std_values.get)

    return None


def to_numeric_series(series: pd.Series) -> pd.Series:
    """Coerce a column to numbers, stripping currency symbols, commas, etc."""
    if not pd.api.types.is_numeric_dtype(series):
        series = series.astype(str).str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(series, errors="coerce")


def numeric_columns(df: pd.DataFrame, exclude: tuple[str, ...] = ()) -> list[str]:
    """
    Columns that are numeric, or that become mostly numeric after stripping
    currency formatting — candidates for a what-if driver (e.g. marketing spend).
    """
    out: list[str] = []
    for col in df.columns:
        if col in exclude:
            continue
        if pd.api.types.is_bool_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        parsed = to_numeric_series(df[col])
        if parsed.notna().sum() >= max(1, len(df) * 0.8):
            out.append(str(col))
    return out


def clean_dataframe(
    df: pd.DataFrame,
    date_col: str,
    revenue_col: str,
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Clean and prepare the DataFrame for analysis.

    Steps:
      1. Keep the date and revenue columns (plus any *extra_cols*).
      2. Parse the date column to datetime.
      3. Convert the revenue (and extra) columns to numeric.
      4. Drop rows with missing date/revenue.
      5. Aggregate duplicate dates (sum).
      6. Sort by date ascending.
      7. Reset the index.

    Args:
        df: Raw input DataFrame.
        date_col: Name of the date column.
        revenue_col: Name of the revenue column.
        extra_cols: Additional numeric columns to carry through (e.g. a
            what-if driver such as marketing spend). They keep their names.

    Returns:
        Cleaned DataFrame with columns ['ds', 'y', *extra_cols] (Prophet-compatible).
    """
    extra_cols = [c for c in (extra_cols or []) if c not in (date_col, revenue_col)]

    # Work on a copy with only the required columns
    cleaned = df[[date_col, revenue_col, *extra_cols]].copy()

    # Standardise column names for downstream use (Prophet expects 'ds' and 'y')
    cleaned.columns = ["ds", "y", *extra_cols]

    # Parse dates
    cleaned["ds"] = pd.to_datetime(cleaned["ds"], errors="coerce")

    # Parse revenue and extras to numeric (handles currency symbols, commas, etc.)
    cleaned["y"] = to_numeric_series(cleaned["y"])
    for col in extra_cols:
        cleaned[col] = to_numeric_series(cleaned[col])

    # Drop rows where parsing failed
    cleaned = cleaned.dropna(subset=["ds", "y"])

    # Remove negative revenue values
    cleaned = cleaned[cleaned["y"] >= 0]

    # Remove duplicates — aggregate by date if needed
    cleaned = cleaned.groupby("ds", as_index=False)[["y", *extra_cols]].sum(min_count=1)

    # Sort chronologically
    cleaned = cleaned.sort_values("ds").reset_index(drop=True)

    return cleaned


def analyze_data(df: pd.DataFrame) -> dict:
    """
    Perform statistical analysis on the cleaned DataFrame.

    Expects a DataFrame with columns 'ds' (datetime) and 'y' (numeric revenue).

    Args:
        df: Cleaned DataFrame with 'ds' and 'y' columns.

    Returns:
        Dictionary containing summary statistics and insights.
    """
    if df.empty:
        return {"error": "DataFrame is empty. Cannot perform analysis."}

    revenue = df["y"]

    # --- Basic Statistics ---
    stats = {
        "total_records": int(len(df)),
        "date_range": {
            "start": str(df["ds"].min().date()),
            "end": str(df["ds"].max().date()),
            "span_days": int((df["ds"].max() - df["ds"].min()).days),
        },
        "revenue": {
            "total": round(float(revenue.sum()), 2),
            "mean": round(float(revenue.mean()), 2),
            "median": round(float(revenue.median()), 2),
            "std_dev": round(float(revenue.std()), 2),
            "min": round(float(revenue.min()), 2),
            "max": round(float(revenue.max()), 2),
        },
    }

    # --- Growth Metrics ---
    if len(df) >= 2:
        first_value = revenue.iloc[0]
        last_value = revenue.iloc[-1]
        if first_value > 0:
            overall_growth = ((last_value - first_value) / first_value) * 100
            stats["growth"] = {
                "overall_percent": round(float(overall_growth), 2),
                "direction": (
                    "increasing" if overall_growth > 0
                    else "decreasing" if overall_growth < 0
                    else "flat"
                ),
            }

    # --- Monthly Aggregation ---
    df_monthly = df.copy()
    df_monthly["month"] = df_monthly["ds"].dt.to_period("M")
    monthly_stats = df_monthly.groupby("month")["y"].sum()

    stats["monthly"] = {
        "best_month": str(monthly_stats.idxmax()),
        "best_month_revenue": round(float(monthly_stats.max()), 2),
        "worst_month": str(monthly_stats.idxmin()),
        "worst_month_revenue": round(float(monthly_stats.min()), 2),
        "avg_monthly_revenue": round(float(monthly_stats.mean()), 2),
    }

    # --- Volatility --- (a zero-revenue month yields inf in pct_change; drop it)
    monthly_changes = (
        monthly_stats.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    )
    if not monthly_changes.empty:
        stats["volatility"] = {
            "avg_monthly_change_percent": round(float(monthly_changes.mean() * 100), 2),
            "max_monthly_drop_percent": round(float(monthly_changes.min() * 100), 2),
            "max_monthly_spike_percent": round(float(monthly_changes.max() * 100), 2),
        }

    return stats
