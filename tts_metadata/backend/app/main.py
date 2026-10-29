"""FastAPI Application Main Entry Point.

Configures the FastAPI application, CORS middleware, system health check endpoints,
and registers the metadata API router.
"""

import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import test_connection
from app.metadata import router as metadata_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sanskrit.api")

# Initialize FastAPI application
app = FastAPI(
    title="TTS Metadata Management System API",
    description="Read-only REST API for querying TTS metadata records from PostgreSQL.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Register routers
app.include_router(metadata_router, prefix="/api/v1/metadata")


@app.get(
    "/",
    summary="Root Status",
    response_description="Confirmation message that API is running",
)
def root():
    """Confirm that the TTS Metadata Management API is running."""
    return {
        "status": "online",
        "service": "TTS Metadata Management System API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/health",
        "db_health": "/health/database",
    }


@app.get(
    "/health",
    summary="API Health Check",
    response_description="Current service health",
)
def health_check():
    """Return API service health status."""
    return {
        "status": "healthy",
        "service": "TTS Metadata Management System",
    }


@app.get(
    "/health/database",
    summary="Database Health Check",
    response_description="Database connectivity status",
)
def database_health():
    """Check connectivity to PostgreSQL database safely without exposing secrets."""
    is_connected, message = test_connection()

    if is_connected:
        return {
            "status": "connected",
            "database": settings.db_name,
            "table": settings.metadata_table,
            "message": message,
        }
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "disconnected",
                "database": settings.db_name,
                "error": message,
            },
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
