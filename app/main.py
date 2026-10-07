"""
Purpose:
    Creates the FastAPI application and registers HTTP routes.

Place in the system:
    This is the backend application entry point. Later request handling,
    retrieval, streaming, and observability components will be attached here.
"""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Local AI Document Chat",
    version="0.1.0",
    description="Local document-grounded chat service.",
)

app.include_router(health_router)