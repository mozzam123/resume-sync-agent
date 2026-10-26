"""FastAPI application wiring."""

from __future__ import annotations

from fastapi import FastAPI

from api import router

app = FastAPI(title="Resume Sync Agent", version="0.1.0")

app.include_router(router, prefix="/api")
