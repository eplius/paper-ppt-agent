"""Global configuration using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Canvas format definitions (adapted from ppt-master)
CANVAS_FORMATS = {
    "ppt169": {
        "name": "PPT 16:9",
        "width": 1280,
        "height": 720,
        "viewbox": "0 0 1280 720",
        "ratio": "16:9",
    },
    "ppt43": {
        "name": "PPT 4:3",
        "width": 1024,
        "height": 768,
        "viewbox": "0 0 1024 768",
        "ratio": "4:3",
    },
}

# Design color schemes
DESIGN_STYLES = {
    "academic": {
        "name": "Academic",
        "background": "#FFFFFF",
        "primary": "#1A365D",
        "accent": "#2B6CB0",
        "body_text": "#2D3748",
    },
    "consulting": {
        "name": "Consulting",
        "background": "#FFFFFF",
        "primary": "#003A70",
        "accent": "#0077B6",
        "body_text": "#1A202C",
    },
    "tech": {
        "name": "Tech",
        "background": "#0F172A",
        "primary": "#3B82F6",
        "accent": "#06B6D4",
        "body_text": "#E2E8F0",
    },
    "general": {
        "name": "General",
        "background": "#FFFFFF",
        "primary": "#4F46E5",
        "accent": "#7C3AED",
        "body_text": "#374151",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM defaults
    default_llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    default_llm_model: str = "gpt-4o"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Paper parsing
    mineru_api_key: str | None = None
    mineru_api_url: str | None = None

    # Image generation
    image_backend: str | None = None

    # Paths
    assets_dir: Path = PROJECT_ROOT / "assets"
    workspaces_dir: Path = PROJECT_ROOT / "workspaces"
    runtime_dir: Path = PROJECT_ROOT / ".runtime"
    templates_dir: Path = PROJECT_ROOT / "assets" / "templates"
    icons_dir: Path = PROJECT_ROOT / "assets" / "icons"
    references_dir: Path = PROJECT_ROOT / "assets" / "references"

    # Limits
    max_concurrent_jobs: int = 3
    job_timeout_seconds: int = 1800  # 30 minutes


settings = Settings()
