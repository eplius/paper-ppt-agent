"""Main API router."""

from fastapi import APIRouter

from .endpoints import download, generate, preview, providers, refine, session, status, upload

api_router = APIRouter(prefix="/api")
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(generate.router, tags=["generate"])
api_router.include_router(refine.router, tags=["refine"])
api_router.include_router(status.router, tags=["status"])
api_router.include_router(download.router, tags=["download"])
api_router.include_router(preview.router, tags=["preview"])
api_router.include_router(providers.router, tags=["providers"])
api_router.include_router(session.router, tags=["session"])
