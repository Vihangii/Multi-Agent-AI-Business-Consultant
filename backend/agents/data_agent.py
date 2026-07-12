"""
Data Analysis Agent
Handles data loading, cleaning, column detection, and statistical analysis.
"""

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
    columns_lower = {col.lower().strip(): col for col in df.columns}

    # Strategy 1: Match against known aliases
    for alias in DATE_ALIASES:
        if alias in columns_lower:
            return columns_lower[alias]

    # Strategy 2: Partial match (column name contains a date keyword)
    for alias in DATE_ALIASES:
        for col_lower, col_original in columns_lower.items():
            if alias in col_lower:
                return col_original

    # Strategy 3: Try parsing each column as datetime
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
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
    columns_lower = {col.lower().strip(): col for col in df.columns}

    # Strategy 1: Exact match against known aliases
    for alias in REVENUE_ALIASES:
        if alias in columns_lower:
            return columns_lower[alias]

    # Strategy 2: Partial match
    for alias in REVENUE_ALIASES:
        for col_lower, col_original in columns_lower.items():
            if alias in col_lower:
                return col_original

    # Strategy 3: Pick the numeric column with the highest standard deviation
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        std_values = {col: df[col].std() for col in numeric_cols}
        return max(std_values, key=std_values.get)

    return None


def clean_dataframe(
    df: pd.DataFrame,
    date_col: str,
    revenue_col: str,
) -> pd.DataFrame:
    """
    Clean and prepare the DataFrame for analysis.

    Steps:
      1. Keep only the date and revenue columns.
      2. Parse the date column to datetime.
      3. Convert the revenue column to numeric.
      4. Drop rows with missing values.
      5. Remove duplicate dates (keep last).
      6. Sort by date ascending.
      7. Reset the index.

    Args:
        df: Raw input DataFrame.
        date_col: Name of the date column.
        revenue_col: Name of the revenue column.

    Returns:
        Cleaned DataFrame with columns ['ds', 'y'] (Prophet-compatible).
    """
    # Work on a copy with only the required columns
    cleaned = df[[date_col, revenue_col]].copy()

    # Standardise column names for downstream use (Prophet expects 'ds' and 'y')
    cleaned.columns = ["ds", "y"]

    # Parse dates
    cleaned["ds"] = pd.to_datetime(cleaned["ds"], errors="coerce")

    # Parse revenue to numeric (handles currency symbols, commas, etc.)
    if cleaned["y"].dtype == object:
        cleaned["y"] = (
            cleaned["y"]
            .astype(str)
            .str.replace(r"[^\d.\-]", "", regex=True)
        )
    cleaned["y"] = pd.to_numeric(cleaned["y"], errors="coerce")

    # Drop rows where parsing failed
    cleaned = cleaned.dropna(subset=["ds", "y"])

    # Remove negative revenue values
    cleaned = cleaned[cleaned["y"] >= 0]

    # Remove duplicates — aggregate by date if needed
    cleaned = cleaned.groupby("ds", as_index=False)["y"].sum()

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
                "direction": "increasing" if overall_growth > 0 else "decreasing",
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

    # --- Volatility ---
    if len(monthly_stats) >= 2:
        monthly_changes = monthly_stats.pct_change().dropna()
        stats["volatility"] = {
            "avg_monthly_change_percent": round(float(monthly_changes.mean() * 100), 2),
            "max_monthly_drop_percent": round(float(monthly_changes.min() * 100), 2),
            "max_monthly_spike_percent": round(float(monthly_changes.max() * 100), 2),
        }

    return stats
