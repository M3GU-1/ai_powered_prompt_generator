"""Token usage tracking and persistence."""

import json
import logging
import asyncio
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USAGE_DIR = PROJECT_ROOT / "data" / "usage"
USAGE_FILE = USAGE_DIR / "usage.json"

_lock = asyncio.Lock()


def _empty_totals() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }


def _load_usage() -> dict:
    """Load usage data from JSON file."""
    if not USAGE_FILE.exists():
        return {"daily": {}, "total": _empty_totals()}
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load usage data: {e}")
        return {"daily": {}, "total": _empty_totals()}


def _save_usage(data: dict) -> None:
    """Save usage data to JSON file."""
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def record_usage(usage: dict) -> None:
    """Record a single request's token usage. Thread-safe via asyncio lock."""
    input_t = usage.get("input_tokens", 0)
    output_t = usage.get("output_tokens", 0)
    cache_r = usage.get("cache_read_tokens", 0)
    cache_c = usage.get("cache_creation_tokens", 0)
    total_t = input_t + output_t

    # Skip recording if no tokens were consumed
    if total_t == 0 and usage.get("request_count", 1) == 0:
        return

    async with _lock:
        data = _load_usage()
        today = date.today().isoformat()
        model_key = f"{usage.get('provider', 'unknown')}/{usage.get('model', 'unknown')}"

        # Update daily
        if today not in data["daily"]:
            data["daily"][today] = {**_empty_totals(), "by_model": {}}

        day = data["daily"][today]
        day["input_tokens"] += input_t
        day["output_tokens"] += output_t
        day["cache_read_tokens"] += cache_r
        day["cache_creation_tokens"] += cache_c
        day["total_tokens"] += total_t
        day["request_count"] += 1

        # Update by-model within day
        if model_key not in day["by_model"]:
            day["by_model"][model_key] = _empty_totals()
        m = day["by_model"][model_key]
        m["input_tokens"] += input_t
        m["output_tokens"] += output_t
        m["cache_read_tokens"] += cache_r
        m["cache_creation_tokens"] += cache_c
        m["request_count"] += 1

        # Update grand total
        t = data["total"]
        t["input_tokens"] += input_t
        t["output_tokens"] += output_t
        t["cache_read_tokens"] += cache_r
        t["cache_creation_tokens"] += cache_c
        t["total_tokens"] += total_t
        t["request_count"] += 1

        _save_usage(data)


def get_usage_summary() -> dict:
    """Get full usage data for the API endpoint."""
    return _load_usage()


def reset_usage() -> None:
    """Clear all usage data."""
    _save_usage({"daily": {}, "total": _empty_totals()})
