"""Pydantic request/response schemas for the API."""

from typing import List, Optional
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Legacy (single-turn) tag generation request."""
    description: str = Field(..., min_length=1)
    num_tags: int = 20
    include_categories: List[int] = [0, 3, 4, 5]
    include_background: bool = True
    style: str = ""


class StreamGenerateRequest(BaseModel):
    """Function-calling (multi-turn) tag generation request. Returns SSE stream."""
    description: str = Field(..., min_length=1)
    num_tags: int = 20
    include_background: bool = True
    style: str = ""
    detailed: bool = False
    anima_mode: bool = False
    custom_tags: Optional[List[str]] = None


class RandomExpandRequest(BaseModel):
    """Expand base character tags with random scene tags. Returns SSE stream."""
    base_tags: str = Field(..., description="Comma-separated base character tags to expand")
    spicy: bool = False
    boost: bool = False
    explicit: bool = False
    anima_mode: bool = False
    custom_tags: Optional[List[str]] = None


class SceneExpandRequest(BaseModel):
    """Expand base tags with a natural language scene description. Returns SSE stream."""
    base_tags: str = Field(..., description="Comma-separated base character tags to expand")
    scene_description: str = Field(..., description="Natural language scene description")
    anima_mode: bool = False
    custom_tags: Optional[List[str]] = None


class TagCandidate(BaseModel):
    tag: str
    category: int
    count: int
    match_method: str  # "exact" | "alias" | "fuzzy" | "vector"
    similarity_score: float
    llm_original: str


class GenerateResponse(BaseModel):
    tags: List[TagCandidate]
    raw_llm_tags: List[str]
    prompt_preview: str


class MatchRequest(BaseModel):
    tag: str


class ConfigUpdateRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    temperature: Optional[float] = None


class ConfigResponse(BaseModel):
    provider: str
    model: str
    has_api_key: bool
    ollama_base_url: str
    temperature: float


class HealthResponse(BaseModel):
    status: str
    index_loaded: bool
    tag_count: int
    llm_configured: bool
