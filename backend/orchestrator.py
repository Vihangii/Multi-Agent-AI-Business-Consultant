"""
Orchestrator Module
Connects the three agents (data_agent, forecast_agent, recommendation_agent)
and runs the full analysis → forecast → recommendation pipeline.
"""

import logging
import time
from pathlib import Path

import pandas as pd

from backend.agents.data_agent import (
    analyze_data,
    clean_dataframe,
    find_date_column,
    find_revenue_column,
)
from backend.agents.forecast_agent import forecast_revenue
from backend.agents.recommendation_agent import generate_recommendations

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stage results
# ---------------------------------------------------------------------------

class PipelineResult:
    """Container for the full pipeline output."""

    def __init__(self):
        self.success: bool = False
        self.error: str | None = None

        # Stage 1: Data Agent outputs
        self.raw_row_count: int = 0
        self.cleaned_row_count: int = 0
        self.date_column: str | None = None
        self.revenue_column: str | None = None
        self.cleaned_df: pd.DataFrame | None = None
        self.analysis: dict | None = None

        # Stage 2: Forecast Agent outputs
        self.forecast_df: pd.DataFrame | None = None
        self.forecast_summary: dict | None = None

        # Stage 3: Recommendation Agent outputs
        self.recommendations: str | None = None

        # Metadata
        self.elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Serialise the result to a JSON-safe dictionary."""
        result = {
            "success": self.success,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }

        if self.analysis is not None:
            result["analysis"] = self.analysis

        if self.forecast_summary is not None:
            result["forecast_summary"] = self.forecast_summary

        if self.forecast_df is not None:
            result["forecast"] = self.forecast_df.to_dict(orient="records")

        if self.recommendations is not None:
            result["recommendations"] = self.recommendations

        # Include metadata about data processing/detection
        result["date_column"] = self.date_column
        result["revenue_column"] = self.revenue_column
        result["raw_row_count"] = self.raw_row_count
        result["cleaned_row_count"] = self.cleaned_row_count

        return result


# ---------------------------------------------------------------------------
# Individual pipeline stages
# ---------------------------------------------------------------------------

def _run_data_stage(df: pd.DataFrame, result: PipelineResult) -> pd.DataFrame:
    """
    Stage 1 — Data Agent: detect columns, clean data, and compute statistics.

    Args:
        df: Raw DataFrame loaded from the user's file.
        result: PipelineResult being populated.

    Returns:
        Cleaned DataFrame ready for forecasting.

    Raises:
        ValueError: If required columns cannot be detected or the cleaned
                    DataFrame is empty.
    """
    logger.info("🔍 Stage 1/3 — Data Agent: analysing uploaded data …")

    result.raw_row_count = len(df)

    # Detect columns
    date_col = find_date_column(df)
    if date_col is None:
        raise ValueError(
            "Could not detect a date column. "
            "Please ensure your dataset contains a recognisable date column "
            "(e.g. 'date', 'order_date', 'timestamp')."
        )

    revenue_col = find_revenue_column(df)
    if revenue_col is None:
        raise ValueError(
            "Could not detect a revenue/sales column. "
            "Please ensure your dataset contains a recognisable numeric column "
            "(e.g. 'revenue', 'sales', 'amount')."
        )

    result.date_column = date_col
    result.revenue_column = revenue_col
    logger.info("  ✔ Detected date column: '%s'", date_col)
    logger.info("  ✔ Detected revenue column: '%s'", revenue_col)

    # Clean
    cleaned_df = clean_dataframe(df, date_col, revenue_col)
    if cleaned_df.empty:
        raise ValueError(
            "The dataset is empty after cleaning. "
            "Please check that the date and revenue columns contain valid data."
        )

    result.cleaned_df = cleaned_df
    result.cleaned_row_count = len(cleaned_df)
    logger.info(
        "  ✔ Cleaned data: %d → %d rows",
        result.raw_row_count,
        result.cleaned_row_count,
    )

    # Analyse
    analysis = analyze_data(cleaned_df)
    if "error" in analysis:
        raise ValueError(analysis["error"])

    result.analysis = analysis
    logger.info("  ✔ Statistical analysis complete")

    return cleaned_df


def _run_forecast_stage(
    cleaned_df: pd.DataFrame,
    result: PipelineResult,
    periods: int | None = None,
    frequency: str | None = None,
) -> None:
    """
    Stage 2 — Forecast Agent: generate revenue forecast with Prophet.

    Args:
        cleaned_df: Cleaned DataFrame from Stage 1.
        result: PipelineResult being populated.
        periods: Optional override for forecast horizon.
        frequency: Optional override for forecast frequency.
    """
    logger.info("📈 Stage 2/3 — Forecast Agent: generating forecast …")

    kwargs: dict = {}
    if periods is not None:
        kwargs["periods"] = periods
    if frequency is not None:
        kwargs["frequency"] = frequency

    forecast_output = forecast_revenue(cleaned_df, **kwargs)

    result.forecast_df = forecast_output["forecast_df"]
    result.forecast_summary = forecast_output["summary"]

    logger.info(
        "  ✔ Forecast generated — trend: %s, predicted growth: %s%%",
        result.forecast_summary.get("forecast_trend", "N/A"),
        result.forecast_summary.get("predicted_growth_percent", "N/A"),
    )


def _run_recommendation_stage(result: PipelineResult) -> None:
    """
    Stage 3 — Recommendation Agent: produce AI-powered business advice.

    Args:
        result: PipelineResult populated by the first two stages.
    """
    logger.info("🤖 Stage 3/3 — Recommendation Agent: generating insights …")

    recommendations = generate_recommendations(
        analysis=result.analysis,
        forecast_summary=result.forecast_summary,
    )

    result.recommendations = recommendations
    logger.info("  ✔ Recommendations generated")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_pipeline(
    file_path: str | None = None,
    df: pd.DataFrame | None = None,
    *,
    periods: int | None = None,
    frequency: str | None = None,
    skip_recommendations: bool = False,
) -> PipelineResult:
    """
    Execute the full multi-agent pipeline end-to-end.

    Accepts **either** a file path to a CSV/Excel file or a pre-loaded
    DataFrame.  The pipeline runs three stages sequentially:

        1. **Data Agent** — column detection, cleaning, statistical analysis.
        2. **Forecast Agent** — Prophet-based revenue forecasting.
        3. **Recommendation Agent** — GPT-powered strategic recommendations.

    Args:
        file_path: Path to a CSV or Excel file to analyse.
        df: Pre-loaded pandas DataFrame (used instead of *file_path*).
        periods: Optional forecast horizon override.
        frequency: Optional forecast frequency override ('D', 'W', 'MS').
        skip_recommendations: If ``True``, skip Stage 3 (useful for testing
            without an OpenAI API key).

    Returns:
        A :class:`PipelineResult` containing outputs from every stage.

    Examples:
        >>> result = run_pipeline(file_path="data/sales.csv")
        >>> print(result.recommendations)

        >>> result = run_pipeline(df=my_dataframe, skip_recommendations=True)
        >>> print(result.forecast_summary)
    """
    start = time.time()
    result = PipelineResult()

    try:
        # ------------------------------------------------------------------
        # Load data
        # ------------------------------------------------------------------
        if df is not None:
            raw_df = df.copy()
        elif file_path is not None:
            raw_df = _load_file(file_path)
        else:
            raise ValueError(
                "You must provide either 'file_path' or 'df'."
            )

        # ------------------------------------------------------------------
        # Stage 1: Data Agent
        # ------------------------------------------------------------------
        cleaned_df = _run_data_stage(raw_df, result)

        # ------------------------------------------------------------------
        # Stage 2: Forecast Agent
        # ------------------------------------------------------------------
        _run_forecast_stage(
            cleaned_df,
            result,
            periods=periods,
            frequency=frequency,
        )

        # ------------------------------------------------------------------
        # Stage 3: Recommendation Agent (optional)
        # ------------------------------------------------------------------
        if not skip_recommendations:
            _run_recommendation_stage(result)

        result.success = True
        logger.info("✅ Pipeline completed successfully")

    except Exception as exc:
        result.success = False
        result.error = str(exc)
        logger.error("❌ Pipeline failed: %s", exc, exc_info=True)

    finally:
        result.elapsed_seconds = time.time() - start
        logger.info("⏱  Total elapsed: %.2fs", result.elapsed_seconds)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_file(file_path: str) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    Args:
        file_path: Path to the data file.

    Returns:
        Raw DataFrame.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)
    elif suffix in (".xls", ".xlsx"):
        return pd.read_excel(path)
    else:
        raise ValueError(
            f"Unsupported file format '{suffix}'. "
            "Please upload a .csv or .xlsx file."
        )
