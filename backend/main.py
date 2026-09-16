"""
FastAPI Main Application Module
Provides endpoints for the Multi-Agent AI Business Consultant Backend.
"""

import logging
from typing import Any, Dict

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    version="1.0.0",
)

# Configure CORS Middleware
# Allows request from any origin by default for local development. Can be restricted in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint to monitor application and dependency status.
    """
    return {
        "status": "healthy",
        "service": "multi-agent-consultant-backend",
    }


@app.post("/analyze", tags=["Analysis"])
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
) -> Dict[str, Any]:
    """
    Accepts a dataset file upload, runs the multi-agent analysis, forecasting,
    and business recommendation pipeline, and returns the comprehensive results.
    """
    # 1. Validate file extension
    filename = file.filename or ""
    lower_filename = filename.lower()
    if not (lower_filename.endswith(".csv") or lower_filename.endswith(".xlsx") or lower_filename.endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .csv, .xlsx, or .xls file.",
        )

    # 2. Read file content into a Pandas DataFrame
    try:
        # Read the uploaded file binary stream directly
        content = await file.read()
        if lower_filename.endswith(".csv"):
            # Try parsing CSV. Handle possible encoding issues.
            try:
                df = pd.read_csv(pd.io.common.BytesIO(content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(pd.io.common.BytesIO(content), encoding="latin-1")
        else:
            # Excel files
            df = pd.read_excel(pd.io.common.BytesIO(content))

    except Exception as e:
        logger.error("Failed to parse uploaded file: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse the uploaded file as a valid table. Error: {str(e)}",
        )

    # 3. Run the orchestrator pipeline
    logger.info("Starting pipeline execution for uploaded file: %s", filename)
    try:
        pipeline_result = run_pipeline(
            df=df,
            periods=periods,
            frequency=frequency,
            skip_recommendations=skip_recommendations,
        )

        # 4. Handle pipeline execution failures
        if not pipeline_result.success:
            logger.error("Pipeline run failed: %s", pipeline_result.error)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline execution failed: {pipeline_result.error}",
            )

        # Return serialized results
        return pipeline_result.to_dict()

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error("Internal error during pipeline run: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred during the analysis: {str(e)}",
        )
