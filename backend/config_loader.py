"""Load and validate config.yaml."""

import shutil
from pathlib import Path
from pydantic import BaseModel
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config.example.yaml"


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    temperature: float = 0.7


class MatchingConfig(BaseModel):
    max_results_per_tag: int = 5
    vector_search_k: int = 10
    min_similarity_score: float = 0.3
    count_weight: float = 0.1


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    matching: MatchingConfig = MatchingConfig()
    server: ServerConfig = ServerConfig()


def load_config() -> AppConfig:
    """Load config from config.yaml, creating from example if needed."""
    if not CONFIG_PATH.exists():
        if CONFIG_EXAMPLE_PATH.exists():
            shutil.copy(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
        else:
            return AppConfig()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return AppConfig(**raw)


def save_config(config: AppConfig):
    """Save config to config.yaml."""
    data = config.model_dump()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
