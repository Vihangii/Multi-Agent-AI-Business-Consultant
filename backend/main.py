"""
FastAPI Main Application Module
Provides endpoints for the Multi-Agent AI Business Consultant Backend.
"""

import logging
from typing import Any, Dict

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Security, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from backend.config import (
    API_KEY,
    CORS_ORIGINS,
    FILE_URL_ALLOWED_HOSTS,
    IS_VERCEL,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    OPENAI_MODEL,
    has_openai_key,
)
from backend.io_utils import UploadError, fetch_remote_file, inspect_dataframe, parse_upload
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

# Vercel serverless functions reject request bodies over 4.5 MB before the
# function runs, so files bigger than that are uploaded to Vercel Blob by the
# browser and passed here as `file_url` instead of a multipart `file`.
_FILE_DESC = "The CSV or Excel file (multipart). Omit and pass file_url for files over 4.5 MB on Vercel."
_URL_DESC = "URL of an already-uploaded CSV/Excel file (e.g. Vercel Blob). Host must be allow-listed."


async def _read_upload(file: UploadFile | None, file_url: str | None) -> tuple[str, pd.DataFrame]:
    """
    Validate, size-check and parse the input file, given either as a multipart
    upload or as an allow-listed URL. Returns (filename, DataFrame).
    """
    if file is None and not file_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a multipart 'file' or a 'file_url'.",
        )
    try:
        if file is not None:
            filename = file.filename or ""
            # Read at most one byte over the limit so oversized files are
            # rejected without buffering the whole thing.
            content = await file.read(MAX_UPLOAD_BYTES + 1)
        else:
            filename, content = await run_in_threadpool(fetch_remote_file, file_url)
        df = await run_in_threadpool(parse_upload, filename, content)
        return filename, df
    except UploadError as e:
        if e.status_code == 422:
            logger.error("Failed to read input file: %s", e)
        raise HTTPException(status_code=e.status_code, detail=str(e))


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
        # Multipart bodies are capped by the platform on Vercel; larger files must use file_url
        "max_multipart_mb": 4.5 if IS_VERCEL else MAX_UPLOAD_MB,
        "file_url_allowed_hosts": FILE_URL_ALLOWED_HOSTS,
        "platform": "vercel" if IS_VERCEL else "server",
    }


@app.post("/inspect", tags=["Analysis"], dependencies=[Depends(require_api_key)])
async def inspect_dataset(
    file: UploadFile | None = File(default=None, description=_FILE_DESC),
    file_url: str | None = Form(default=None, description=_URL_DESC),
    file_url_q: str | None = Query(default=None, alias="file_url", description=_URL_DESC),
) -> Dict[str, Any]:
    """
    Cheap pre-flight: returns the column names, the columns auto-detection
    would pick, and a small preview — so a client can let the user confirm
    or override the columns before running the full pipeline.
    """
    _, df = await _read_upload(file, file_url or file_url_q)
    return inspect_dataframe(df)


@app.post("/analyze", tags=["Analysis"], dependencies=[Depends(require_api_key)])
async def analyze_dataset(
    file: UploadFile | None = File(default=None, description=_FILE_DESC),
    file_url: str | None = Form(default=None, description=_URL_DESC),
    file_url_q: str | None = Query(default=None, alias="file_url", description=_URL_DESC),
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
    filename, df = await _read_upload(file, file_url or file_url_q)

    # The pipeline is CPU-bound (Prophet) and makes a blocking HTTP call (OpenAI),
    # so run it off the event loop to keep the server responsive.
    logger.info("Starting pipeline execution for uploaded file: %s", filename)
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
