"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from backend.config_loader import load_config, save_config, LLMConfig, AppConfig
from backend.models import (
    GenerateRequest, GenerateResponse, MatchRequest,
    StreamGenerateRequest, RandomExpandRequest, SceneExpandRequest,
    ConfigUpdateRequest, ConfigResponse, HealthResponse, TagCandidate,
)
from backend.tag_database import TagDatabase
from backend.vector_search import VectorSearch
from backend.tag_matcher import TagMatcher
from backend.llm_service import LLMService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load resources on startup."""
    config = load_config()
    app.state.config = config

    # Load tag database
    merged_path = DATA_DIR / "merged_tags.json"
    if not merged_path.exists():
        logger.error("merged_tags.json not found. Run: python scripts/build_embeddings.py")
        app.state.tag_db = None
        app.state.vector_search = None
        app.state.tag_matcher = None
    else:
        app.state.tag_db = TagDatabase(str(merged_path))
        logger.info(f"Loaded {app.state.tag_db.total_tags} tags")

        # Load vector search
        index_path = str(DATA_DIR / "faiss_index")
        try:
            app.state.vector_search = VectorSearch(index_path)
            logger.info("FAISS index loaded")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            app.state.vector_search = VectorSearch.__new__(VectorSearch)
            app.state.vector_search.vector_store = None

        # Initialize tag matcher
        app.state.tag_matcher = TagMatcher(
            app.state.tag_db,
            app.state.vector_search,
            config.matching,
        )

    # Initialize LLM service
    try:
        app.state.llm_service = LLMService(config.llm)
        logger.info(f"LLM service initialized: {config.llm.provider}/{config.llm.model}")
    except Exception as e:
        logger.warning(f"LLM service not available: {e}")
        app.state.llm_service = None

    yield


app = FastAPI(title="SD Prompt Tag Generator", lifespan=lifespan)


def _sse_error_event(error_msg: str) -> str:
    """Format an SSE error complete event for unexpected exceptions."""
    return (
        f"data: {json.dumps({'type': 'complete', 'data': {'success': False, 'error': error_msg}}, ensure_ascii=False)}\n\n"
    )


# --- API Routes ---

@app.get("/api/health")
async def health() -> HealthResponse:
    tag_db = app.state.tag_db
    vs = app.state.vector_search
    return HealthResponse(
        status="ok",
        index_loaded=vs is not None and getattr(vs, "is_loaded", False),
        tag_count=tag_db.total_tags if tag_db else 0,
        llm_configured=app.state.llm_service is not None,
    )


@app.post("/api/generate")
async def generate_tags(req: GenerateRequest) -> GenerateResponse:
    """Legacy single-turn generation: LLM -> parse -> match via FAISS."""
    if not app.state.llm_service:
        raise HTTPException(status_code=503, detail="LLM service not configured. Check config.yaml and set your API key.")

    if not app.state.tag_matcher:
        raise HTTPException(status_code=503, detail="Tag database not loaded. Run: python scripts/build_embeddings.py")

    # Step 1: Generate raw tags via LLM
    try:
        raw_tags = await app.state.llm_service.generate_tags(
            req.description, req.num_tags,
            include_background=req.include_background,
            style=req.style,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    # Step 2: Match/validate each tag
    matched = app.state.tag_matcher.match_tags_with_alternatives(raw_tags)

    # Filter by requested categories
    if req.include_categories:
        matched = [t for t in matched if t.category in req.include_categories]

    # Build prompt preview from best matches
    best_tags = app.state.tag_matcher.match_tags(raw_tags)
    if req.include_categories:
        best_tags = [t for t in best_tags if t.category in req.include_categories]
    prompt_preview = ", ".join(t.tag for t in best_tags)

    return GenerateResponse(
        tags=matched,
        raw_llm_tags=raw_tags,
        prompt_preview=prompt_preview,
    )


# --- SSE Streaming Endpoints ---

@app.post("/api/generate/stream")
async def generate_tags_stream(req: StreamGenerateRequest):
    """Function-calling mode: LLM calls search_tags/submit_final_tags tools.
    Returns SSE stream with progress logs and final tags."""
    if not app.state.llm_service:
        raise HTTPException(status_code=503, detail="LLM service not configured.")

    tag_db = app.state.tag_db
    vs = app.state.vector_search

    async def event_generator():
        try:
            async for event in app.state.llm_service.generate_tags_with_tools(
                description=req.description,
                tag_db=tag_db,
                vector_search=vs,
                num_tags=req.num_tags,
                include_background=req.include_background,
                style=req.style,
                detailed=req.detailed,
                anima_mode=req.anima_mode,
                custom_tags=req.custom_tags,
            ):
                yield event
        except Exception as e:
            logger.exception("Error in generate stream")
            yield _sse_error_event(f"Unexpected error: {str(e)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/generate/random-expand/stream")
async def random_expand_stream(req: RandomExpandRequest):
    """Expand base character tags with random scene tags.
    Returns SSE stream with progress logs and final tags."""
    if not app.state.llm_service:
        raise HTTPException(status_code=503, detail="LLM service not configured.")

    tag_db = app.state.tag_db
    vs = app.state.vector_search

    async def event_generator():
        try:
            async for event in app.state.llm_service.random_expand_tags(
                base_tags=req.base_tags,
                tag_db=tag_db,
                vector_search=vs,
                spicy=req.spicy,
                boost=req.boost,
                explicit=req.explicit,
                anima_mode=req.anima_mode,
                custom_tags=req.custom_tags,
            ):
                yield event
        except Exception as e:
            logger.exception("Error in random-expand stream")
            yield _sse_error_event(f"Unexpected error: {str(e)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/generate/scene-expand/stream")
async def scene_expand_stream(req: SceneExpandRequest):
    """Expand base tags based on natural language scene description.
    Returns SSE stream with progress logs and final tags."""
    if not app.state.llm_service:
        raise HTTPException(status_code=503, detail="LLM service not configured.")

    tag_db = app.state.tag_db
    vs = app.state.vector_search

    async def event_generator():
        try:
            async for event in app.state.llm_service.scene_expand_tags(
                base_tags=req.base_tags,
                scene_description=req.scene_description,
                tag_db=tag_db,
                vector_search=vs,
                anima_mode=req.anima_mode,
                custom_tags=req.custom_tags,
            ):
                yield event
        except Exception as e:
            logger.exception("Error in scene-expand stream")
            yield _sse_error_event(f"Unexpected error: {str(e)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/match")
async def match_tag(req: MatchRequest) -> List[TagCandidate]:
    if not app.state.tag_matcher:
        raise HTTPException(status_code=503, detail="Tag database not loaded.")
    return app.state.tag_matcher.match_single_tag(req.tag)


@app.get("/api/config")
async def get_config() -> ConfigResponse:
    cfg = app.state.config.llm
    return ConfigResponse(
        provider=cfg.provider,
        model=cfg.model,
        has_api_key=bool(cfg.api_key),
        ollama_base_url=cfg.ollama_base_url,
        temperature=cfg.temperature,
    )


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest) -> ConfigResponse:
    cfg: AppConfig = app.state.config
    llm_cfg = cfg.llm

    if req.provider is not None:
        llm_cfg.provider = req.provider
    if req.model is not None:
        llm_cfg.model = req.model
    if req.api_key is not None:
        llm_cfg.api_key = req.api_key
    if req.ollama_base_url is not None:
        llm_cfg.ollama_base_url = req.ollama_base_url
    if req.temperature is not None:
        llm_cfg.temperature = req.temperature

    # Reinitialize LLM service
    try:
        app.state.llm_service = LLMService(llm_cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize LLM: {str(e)}")

    # Save to disk
    save_config(cfg)

    return ConfigResponse(
        provider=llm_cfg.provider,
        model=llm_cfg.model,
        has_api_key=bool(llm_cfg.api_key),
        ollama_base_url=llm_cfg.ollama_base_url,
        temperature=llm_cfg.temperature,
    )


@app.get("/api/tags/search")
async def search_tags(q: str, limit: int = 10) -> List[dict]:
    if not app.state.tag_db:
        return []
    results = app.state.tag_db.search_prefix(q, limit=limit)
    return [{"tag": r.tag, "category": r.category, "count": r.count} for r in results]


# --- Static Files (Frontend) ---
# Serve index.html for root
@app.get("/")
async def serve_root():
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files for CSS/JS
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
