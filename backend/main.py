"""
FastAPI Main Application Module
Provides endpoints for the Multi-Agent AI Business Consultant Backend.
"""

import io
import logging
from typing import Any, Dict

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, Security, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from backend.config import (
    API_KEY,
    CORS_ORIGINS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    OPENAI_MODEL,
    has_openai_key,
)
from backend.agents.data_agent import find_date_column, find_revenue_column
from backend.orchestrator import run_pipeline

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backend.main")

# Initialize FastAPI App
app = FastAPI(
    title="Multi-Agent AI Business Consultant API",
    description="Backend API powering automated data analysis, revenue forecasting, and strategic recommendations.",
    version="1.1.0",
)

# Configure CORS Middleware
# Defaults to any origin for local development; set CORS_ORIGINS in .env to restrict.
# Browsers reject "*" combined with credentials, so only allow credentials for explicit origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Optional API-key protection
# ---------------------------------------------------------------------------
# When API_KEY is set in .env, /analyze and /inspect require an `X-API-Key`
# header. When it is unset (local dev) the endpoints are open.

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    if not API_KEY:
        return
    if provided != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")


async def _read_upload(file: UploadFile) -> pd.DataFrame:
    """Validate, size-check and parse an uploaded CSV/Excel file."""
    filename = file.filename or ""
    lower_filename = filename.lower()
    if not lower_filename.endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .csv, .xlsx, or .xls file.",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB.",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    def parse() -> pd.DataFrame:
        if lower_filename.endswith(".csv"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(io.BytesIO(content), encoding="latin-1")
        return pd.read_excel(io.BytesIO(content))

    try:
        return await run_in_threadpool(parse)
    except Exception as e:
        logger.error("Failed to parse uploaded file: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse the uploaded file as a valid table. Error: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["General"])
async def root() -> Dict[str, str]:
    """
    Root endpoint offering a simple welcome and API metadata.
    """
    return {
        "message": "Welcome to the Multi-Agent AI Business Consultant API",
        "status": "active",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["General"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint to monitor application and dependency status.
    """
    return {
        "status": "healthy",
        "service": "multi-agent-consultant-backend",
        "openai_configured": has_openai_key(),
        "openai_model": OPENAI_MODEL,
        "max_upload_mb": MAX_UPLOAD_MB,
        "auth_required": bool(API_KEY),
    }


@app.post("/inspect", tags=["Analysis"], dependencies=[Depends(require_api_key)])
async def inspect_dataset(
    file: UploadFile = File(..., description="The CSV or Excel file to inspect."),
) -> Dict[str, Any]:
    """
    Cheap pre-flight: returns the column names, the columns auto-detection
    would pick, and a small preview — so a client can let the user confirm
    or override the columns before running the full pipeline.
    """
    df = await _read_upload(file)
    preview = df.head(5).astype(str).to_dict(orient="records")
    return {
        "columns": [str(c) for c in df.columns],
        "row_count": int(len(df)),
        "detected_date_column": find_date_column(df),
        "detected_revenue_column": find_revenue_column(df),
        "preview": preview,
    }


@app.post("/analyze", tags=["Analysis"], dependencies=[Depends(require_api_key)])
async def analyze_dataset(
    file: UploadFile = File(..., description="The CSV or Excel file containing transaction/revenue data."),
    periods: int | None = Query(
        default=None,
        description="Number of periods to forecast into the future. Defaults to a ~6-month horizon for the detected/selected frequency.",
        ge=2,
        le=1000,
    ),
    frequency: str | None = Query(
        default=None,
        description="Override for forecast frequency: 'D' (daily), 'W' (weekly), or 'MS' (monthly). Auto-detected if omitted.",
        pattern="^(D|W|MS)$",
    ),
    skip_recommendations: bool = Query(
        default=False,
        description="If True, skips Stage 3 (AI recommendations) to save LLM tokens or run offline.",
    ),
    date_column: str | None = Query(
        default=None,
        description="Name of the date column. Auto-detected if omitted.",
    ),
    revenue_column: str | None = Query(
        default=None,
        description="Name of the revenue column. Auto-detected if omitted.",
    ),
) -> Dict[str, Any]:
    """
    Accepts a dataset file upload, runs the multi-agent analysis, forecasting,
    and business recommendation pipeline, and returns the comprehensive results.
    """
    df = await _read_upload(file)

    # The pipeline is CPU-bound (Prophet) and makes a blocking HTTP call (OpenAI),
    # so run it off the event loop to keep the server responsive.
    logger.info("Starting pipeline execution for uploaded file: %s", file.filename)
    try:
        pipeline_result = await run_in_threadpool(
            run_pipeline,
            df=df,
            periods=periods,
            frequency=frequency,
            skip_recommendations=skip_recommendations,
            date_column=date_column,
            revenue_column=revenue_column,
        )
    except Exception as e:
        logger.error("Internal error during pipeline run: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred during the analysis: {str(e)}",
        )

    if not pipeline_result.success:
        logger.error("Pipeline run failed: %s", pipeline_result.error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline execution failed: {pipeline_result.error}",
        )

    return pipeline_result.to_dict()
