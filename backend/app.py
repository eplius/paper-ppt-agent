"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.api.websocket import router as websocket_router
from backend.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Paper PPT Agent",
        version="0.1.0",
        description="Convert academic papers into editable PowerPoint presentations.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings.workspaces_dir.mkdir(parents=True, exist_ok=True)
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": "Paper PPT Agent", "frontend": "Open the Vite frontend to use the app."}

    app.include_router(api_router)
    app.include_router(websocket_router)
    return app


app = create_app()
