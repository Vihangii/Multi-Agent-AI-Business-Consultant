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
from backend.agents.recommendation_agent import (
    RecommendationError,
    generate_recommendations,
)

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
        self.columns: list[str] = []
        self.date_column: str | None = None
        self.revenue_column: str | None = None
        self.cleaned_df: pd.DataFrame | None = None
        self.analysis: dict | None = None

        # Stage 2: Forecast Agent outputs
        self.forecast_df: pd.DataFrame | None = None
        self.forecast_summary: dict | None = None
        self.whatif: dict | None = None
        self.regressor_column: str | None = None

        # Stage 3: Recommendation Agent outputs
        self.recommendations: str | None = None
        self.recommendations_error: str | None = None

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

        if self.cleaned_df is not None:
            result["cleaned_data"] = self.cleaned_df.to_dict(orient="records")

        if self.forecast_summary is not None:
            result["forecast_summary"] = self.forecast_summary

        if self.forecast_df is not None:
            result["forecast"] = self.forecast_df.to_dict(orient="records")

        if self.whatif is not None:
            result["whatif"] = self.whatif

        if self.recommendations is not None:
            result["recommendations"] = self.recommendations
        if self.recommendations_error is not None:
            result["recommendations_error"] = self.recommendations_error

        # Include metadata about data processing/detection
        result["columns"] = self.columns
        result["date_column"] = self.date_column
        result["revenue_column"] = self.revenue_column
        result["regressor_column"] = self.regressor_column
        result["raw_row_count"] = self.raw_row_count
        result["cleaned_row_count"] = self.cleaned_row_count

        return result


# ---------------------------------------------------------------------------
# Individual pipeline stages
# ---------------------------------------------------------------------------

def _run_data_stage(
    df: pd.DataFrame,
    result: PipelineResult,
    date_column: str | None = None,
    revenue_column: str | None = None,
    regressor_column: str | None = None,
) -> pd.DataFrame:
    """
    Stage 1 — Data Agent: detect columns, clean data, and compute statistics.

    Args:
        df: Raw DataFrame loaded from the user's file.
        result: PipelineResult being populated.
        date_column: Explicit date column name; auto-detected if None.
        revenue_column: Explicit revenue column name; auto-detected if None.
        regressor_column: Optional numeric driver column (e.g. marketing
            spend) carried through cleaning for what-if scenarios.

    Returns:
        Cleaned DataFrame ready for forecasting.

    Raises:
        ValueError: If required columns cannot be detected or the cleaned
                    DataFrame is empty.
    """
    logger.info("🔍 Stage 1/3 — Data Agent: analysing uploaded data …")

    result.raw_row_count = len(df)
    result.columns = [str(c) for c in df.columns]

    # Use caller-supplied columns when given, otherwise detect
    for name, label in ((date_column, "date"), (revenue_column, "revenue"), (regressor_column, "driver")):
        if name is not None and name not in df.columns:
            raise ValueError(
                f"The {label} column '{name}' does not exist in the dataset. "
                f"Available columns: {', '.join(result.columns)}"
            )
    if date_column is not None and date_column == revenue_column:
        raise ValueError("The date column and revenue column must be different.")

    date_col = date_column if date_column is not None else find_date_column(df)
    if date_col is None:
        raise ValueError(
            "Could not detect a date column. "
            "Please ensure your dataset contains a recognisable date column "
            "(e.g. 'date', 'order_date', 'timestamp')."
        )

    revenue_col = revenue_column if revenue_column is not None else find_revenue_column(df)
    if revenue_col is None:
        raise ValueError(
            "Could not detect a revenue/sales column. "
            "Please ensure your dataset contains a recognisable numeric column "
            "(e.g. 'revenue', 'sales', 'amount')."
        )

    if regressor_column is not None and regressor_column in (date_col, revenue_col):
        raise ValueError("The driver column must be different from the date and revenue columns.")

    result.date_column = date_col
    result.revenue_column = revenue_col
    result.regressor_column = regressor_column
    logger.info("  ✔ Detected date column: '%s'", date_col)
    logger.info("  ✔ Detected revenue column: '%s'", revenue_col)
    if regressor_column:
        logger.info("  ✔ What-if driver column: '%s'", regressor_column)

    # Clean
    cleaned_df = clean_dataframe(
        df, date_col, revenue_col, extra_cols=[regressor_column] if regressor_column else None
    )
    if regressor_column and cleaned_df[regressor_column].notna().sum() < len(cleaned_df) * 0.8:
        raise ValueError(
            f"The driver column '{regressor_column}' is not numeric enough to use "
            "(needs a number on at least 80% of rows)."
        )
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
    regressor_column: str | None = None,
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
    if regressor_column is not None:
        kwargs["regressor"] = regressor_column

    forecast_output = forecast_revenue(cleaned_df, **kwargs)

    result.forecast_df = forecast_output["forecast_df"]
    result.forecast_summary = forecast_output["summary"]
    result.whatif = forecast_output.get("whatif")

    logger.info(
        "  ✔ Forecast generated — trend: %s, predicted growth: %s%%",
        result.forecast_summary.get("forecast_trend", "N/A"),
        result.forecast_summary.get("predicted_growth_percent", "N/A"),
    )


def _run_recommendation_stage(result: PipelineResult, language: str | None = None) -> None:
    """
    Stage 3 — Recommendation Agent: produce AI-powered business advice.

    Args:
        result: PipelineResult populated by the first two stages.
        language: Language to write the report in (default English).
    """
    logger.info("🤖 Stage 3/3 — Recommendation Agent: generating insights …")

    try:
        result.recommendations = generate_recommendations(
            analysis=result.analysis,
            forecast_summary=result.forecast_summary,
            whatif=result.whatif,
            language=language,
        )
        logger.info("  ✔ Recommendations generated")
    except RecommendationError as exc:
        # Stages 1-2 are still valuable; surface the failure instead of
        # failing the whole pipeline or passing an error string off as a report.
        result.recommendations_error = str(exc)
        logger.warning("  ✖ Recommendations skipped: %s", exc)


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
    date_column: str | None = None,
    revenue_column: str | None = None,
    regressor_column: str | None = None,
    language: str | None = None,
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
            without an OpenAI API key). If Stage 3 runs but fails, the
            pipeline still succeeds and ``recommendations_error`` is set.
        date_column: Explicit date column; overrides auto-detection.
        revenue_column: Explicit revenue column; overrides auto-detection.
        regressor_column: Optional numeric driver column used as a Prophet
            regressor for what-if scenarios (e.g. ``marketing_spend``).
        language: Language for the AI report (e.g. "Spanish"). Default English.

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
        cleaned_df = _run_data_stage(
            raw_df,
            result,
            date_column=date_column,
            revenue_column=revenue_column,
            regressor_column=regressor_column,
        )

        # ------------------------------------------------------------------
        # Stage 2: Forecast Agent
        # ------------------------------------------------------------------
        _run_forecast_stage(
            cleaned_df,
            result,
            periods=periods,
            frequency=frequency,
            regressor_column=regressor_column,
        )

        # ------------------------------------------------------------------
        # Stage 3: Recommendation Agent (optional)
        # ------------------------------------------------------------------
        if not skip_recommendations:
            _run_recommendation_stage(result, language=language)

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
