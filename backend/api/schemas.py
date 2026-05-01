"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    name: str
    size: int
    source_type: str  # "pdf" or "latex"


class UploadResponse(BaseModel):
    session_id: str
    file_info: FileInfo


class DeepSeekSettings(BaseModel):
    thinking_enabled: bool = True
    reasoning_effort: Literal["high", "max"] = "max"


class OpenAISettings(BaseModel):
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh"] = "medium"
    verbosity: Literal["low", "medium", "high"] = "high"


class ModelConfig(BaseModel):
    provider: str  # "openai", "deepseek", "anthropic", "gemini"
    model: str
    api_key: str
    base_url: str | None = None
    deepseek_settings: DeepSeekSettings | None = None
    openai_settings: OpenAISettings | None = None


class StyleOverrides(BaseModel):
    palette: list[str] | None = None  # e.g. ["#0b1220", "#ff8a3d", "#f5f7fb"]
    font: str | None = None
    density: str | None = None        # "compact" | "normal" | "spacious"


class GenerationOptions(BaseModel):
    canvas_format: str = "ppt169"
    style: str = "academic"
    num_pages: int | None = None
    language: str = "zh"
    detail_level: str = "normal"
    timeout_seconds: int | None = Field(default=None, ge=1)
    style_overrides: StyleOverrides | None = None
    enable_visual_critic: bool = False


class GenerateRequest(BaseModel):
    session_id: str
    instruction: str = ""
    model_settings: ModelConfig = Field(alias="model_config")
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class GenerateResponse(BaseModel):
    job_id: str
    status: str = "started"


class JobStatus(BaseModel):
    status: str  # parsing, research, strategy, generation, postprocess, export, complete, error, cancelled
    progress: float = 0.0
    message: str = ""
    slides_completed: int = 0
    total_slides: int = 0
    output_path: str | None = None
    error: str | None = None


class CancelJobResponse(BaseModel):
    job_id: str
    status: str


class ReexportResponse(BaseModel):
    job_id: str
    status: str
    output_path: str


class PreviewSlide(BaseModel):
    index: int
    name: str
    source: str  # "output" or "final"
    content: str


class PreviewResponse(BaseModel):
    job_id: str
    project_dir: str | None = None
    slides: list[PreviewSlide] = Field(default_factory=list)
    output_path: str | None = None
    status: str


class RefineRequest(BaseModel):
    """Request to iterate on an existing generation using user feedback."""

    job_id: str           # ID of the completed generation job to refine
    feedback: str         # User's natural-language feedback / instructions
    model_settings: ModelConfig = Field(alias="model_config")
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    target_pages: list[int] = Field(default_factory=list)
    allow_structure_changes: bool = False


class RefineResponse(BaseModel):
    job_id: str   # new job ID for the refine run
    status: str = "started"


class ProviderModel(BaseModel):
    id: str
    display_name: str
    supports_vision: bool = False


class ProviderListItem(BaseModel):
    name: str
    display_name: str
    default_base_url: str | None = None
    models: list[ProviderModel]


class ProvidersResponse(BaseModel):
    providers: list[ProviderListItem]
