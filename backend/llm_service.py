"""LangChain multi-LLM abstraction for tag generation.

Supports two modes:
1. Legacy mode: single-turn LLM → parse → match
2. Function calling mode: LLM calls search_tags/submit_final_tags tools
"""

import re
import json
import random
import logging
import asyncio
import time
from typing import Optional, AsyncGenerator, List

from backend.config_loader import LLMConfig
from backend.prompt_templates import (
    TAG_GENERATION_PROMPT,
    SYSTEM_PROMPT_FUNCTION_CALLING,
    SYSTEM_PROMPT_FUNCTION_CALLING_DETAILED,
    SYSTEM_PROMPT_RANDOM_EXPAND,
    SYSTEM_PROMPT_RANDOM_EXPAND_SPICY,
    SYSTEM_PROMPT_RANDOM_EXPAND_BOOST,
    SYSTEM_PROMPT_RANDOM_EXPAND_EXPLICIT,
    SYSTEM_PROMPT_SCENE_EXPAND,
    build_anima_mode_section,
    build_custom_tags_section,
    build_generate_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Theme pools for random inspiration keywords
# ---------------------------------------------------------------------------

THEME_POOLS = {
    "settings": [
        "beach", "forest", "city street", "rooftop", "cafe", "library",
        "train station", "garden", "classroom", "bedroom", "kitchen", "park",
        "shrine", "temple", "bridge", "alley", "market", "balcony", "bath",
        "pool", "mountain", "field", "river", "lake", "ocean", "desert",
        "snow field", "castle", "ruins", "laboratory", "office", "hospital",
        "church", "bar", "restaurant", "arcade", "bookstore", "gym", "stage",
        "concert",
    ],
    "weather": [
        "sunny", "rainy", "snowy", "cloudy", "foggy", "stormy", "windy",
        "clear sky", "sunset", "sunrise", "twilight", "night", "moonlight",
        "starry night", "aurora", "overcast",
    ],
    "moods": [
        "cheerful", "melancholic", "peaceful", "dramatic", "mysterious",
        "romantic", "playful", "serious", "dreamy", "nostalgic", "energetic",
        "calm", "tense", "cozy", "lonely", "warm",
    ],
    "activities": [
        "reading", "cooking", "walking", "sitting", "running", "dancing",
        "singing", "fighting", "sleeping", "eating", "drinking", "shopping",
        "studying", "working", "playing", "painting", "photographing",
        "stretching", "leaning", "looking away", "waving", "holding phone",
        "carrying bag",
    ],
    "seasons": ["spring", "summer", "autumn", "winter"],
    "time_of_day": ["morning", "afternoon", "evening", "night", "dawn", "dusk"],
}

SPICY_THEME_POOLS = {
    "settings": [
        "bedroom", "bathroom", "hot spring", "locker room", "beach", "pool",
        "bed", "couch", "shower", "onsen", "sauna", "changing room",
        "hotel room", "balcony at night", "private room", "dimly lit room",
    ],
    "moods": [
        "seductive", "embarrassed", "shy", "provocative", "sensual",
        "flirtatious", "intimate", "vulnerable", "playful", "bold",
        "bashful", "dreamy", "heated", "teasing",
    ],
    "situations": [
        "undressing", "after bath", "waking up", "lying down", "stretching",
        "wardrobe malfunction", "caught off guard", "posing", "leaning forward",
        "sitting on bed", "back view", "looking back", "hand on chest",
        "covering body", "hair down",
    ],
    "clothing": [
        "lingerie", "swimsuit", "towel", "oversized shirt", "nightgown",
        "negligee", "off-shoulder", "bare shoulders", "revealing outfit",
        "unbuttoned shirt", "tank top", "sports bra", "crop top", "miniskirt",
        "shorts",
    ],
}

BOOST_THEME_POOLS = {
    "settings": [
        "bed", "bathroom", "shower", "hot spring", "dimly lit room",
        "hotel room", "private room", "onsen", "sauna", "bedroom at night",
        "love hotel", "tent interior",
    ],
    "moods": [
        "intimate", "passionate", "overwhelmed", "submissive", "dominant",
        "desperate", "yearning", "ecstatic", "helpless", "inviting",
        "begging", "trembling",
    ],
    "situations": [
        "lying on bed", "pinned down", "on all fours", "straddling",
        "embracing", "restrained", "collared", "blindfolded", "tied up",
        "spread legs", "from behind", "on back", "kneeling", "bending over",
    ],
    "states": [
        "fully undressed", "clothes removed", "bare skin", "skin exposed",
        "nothing worn", "stripped", "uncovered", "in the buff", "au naturel",
        "clothes pulled aside", "torn clothes", "clothes falling off",
    ],
}

EXPLICIT_THEME_POOLS = {
    "settings": [
        "bed", "love hotel", "dimly lit room", "shower", "hot spring",
        "bedroom at night", "classroom", "office", "onsen", "tent interior",
        "bathroom", "against wall", "alley", "outdoors", "car interior",
        "public restroom",
    ],
    "moods": [
        "passionate", "rough", "gentle", "desperate", "submissive",
        "dominant", "lustful", "forced", "consensual", "teasing",
        "begging", "reluctant",
    ],
    "acts_solo": [
        "masturbation", "female_masturbation", "fingering", "object_insertion",
        "dildo", "vibrator", "humping", "tentacles", "machine",
    ],
    "acts_duo": [
        "sex", "vaginal", "anal", "fellatio", "cunnilingus", "paizuri",
        "handjob", "footjob", "intercrural", "frottage", "deep_throat",
        "irrumatio",
    ],
    "acts_group": [
        "double_penetration", "spitroast", "gangbang", "orgy", "group_sex",
        "threesome", "train_position", "bukkake",
    ],
    "positions_duo": [
        "missionary", "cowgirl_position", "doggystyle", "standing_sex",
        "prone_bone", "mating_press", "suspended_congress", "lotus_position",
        "spooning", "leg_lock", "wheelbarrow_position", "carrying",
        "against_wall", "bent_over", "face_sitting", "sixty-nine",
    ],
    "expressions": [
        "ahegao", "fucked_silly", "open_mouth", "tongue_out", "rolling_eyes",
        "crying_with_pleasure", "drooling", "heavy_breathing", "panting",
        "screaming", "moaning", "cross-eyed",
    ],
    "body_states": [
        "sweat", "cum", "cum_on_body", "cum_in_pussy", "cum_on_face",
        "cum_on_breasts", "trembling", "blush", "wet", "saliva", "tears",
        "bite_mark", "hickey",
    ],
}


def _pick_random(arr: list, count: int) -> list:
    if count >= len(arr):
        return list(arr)
    return random.sample(arr, count)


def detect_character_type(base_tags: str) -> str:
    """Detect character type from base tags: solo, duo, or group."""
    tags = base_tags.lower().replace(" ", "")
    counts = []
    for m in re.finditer(r"(\d+)(girl|boy|other)s?", tags):
        counts.append(int(m.group(1)))
    total = sum(counts)
    if total >= 3:
        return "group"
    if total == 2 or len(counts) >= 2:
        return "duo"
    return "solo"


def generate_inspiration_keywords(
    spicy: bool = False,
    boost: bool = False,
    explicit: bool = False,
    base_tags: str = "",
) -> str:
    """Generate random inspiration keywords for scene expansion."""
    setting = _pick_random(THEME_POOLS["settings"], 1)[0]
    weather = _pick_random(THEME_POOLS["weather"], 1)[0]
    mood = _pick_random(THEME_POOLS["moods"], 1)[0]
    activity = _pick_random(THEME_POOLS["activities"], 1)[0]
    season = _pick_random(THEME_POOLS["seasons"], 1)[0]
    time_val = _pick_random(THEME_POOLS["time_of_day"], 1)[0]

    all_kw = [
        f"setting: {setting}", f"weather: {weather}", f"mood: {mood}",
        f"activity: {activity}", f"season: {season}", f"time: {time_val}",
    ]

    if explicit:
        char_type = detect_character_type(base_tags)
        e_setting = _pick_random(EXPLICIT_THEME_POOLS["settings"], 1)[0]
        e_mood = _pick_random(EXPLICIT_THEME_POOLS["moods"], 1)[0]
        e_expression = _pick_random(EXPLICIT_THEME_POOLS["expressions"], 1)[0]
        e_body_state = _pick_random(EXPLICIT_THEME_POOLS["body_states"], 1)[0]
        act_pool = (
            EXPLICIT_THEME_POOLS["acts_solo"] if char_type == "solo"
            else EXPLICIT_THEME_POOLS["acts_group"] if char_type == "group"
            else EXPLICIT_THEME_POOLS["acts_duo"]
        )
        e_act = _pick_random(act_pool, 1)[0]
        explicit_kw = [
            f"character_type: {char_type}", f"sex_act: {e_act}",
            f"scene: {e_setting}", f"emotion: {e_mood}",
            f"expression: {e_expression}", f"body_state: {e_body_state}",
        ]
        if char_type != "solo":
            e_position = _pick_random(EXPLICIT_THEME_POOLS["positions_duo"], 1)[0]
            explicit_kw.append(f"position: {e_position}")
        generic_sample = _pick_random(all_kw, 2 + random.randint(0, 1))
        return ", ".join(explicit_kw + generic_sample)

    elif boost:
        b_setting = _pick_random(BOOST_THEME_POOLS["settings"], 1)[0]
        b_mood = _pick_random(BOOST_THEME_POOLS["moods"], 1)[0]
        b_situation = _pick_random(BOOST_THEME_POOLS["situations"], 1)[0]
        b_state = _pick_random(BOOST_THEME_POOLS["states"], 1)[0]
        all_kw.extend([
            f"scene: {b_setting}", f"emotion: {b_mood}",
            f"pose: {b_situation}", f"attire_state: {b_state}",
        ])

    elif spicy:
        s_setting = _pick_random(SPICY_THEME_POOLS["settings"], 1)[0]
        s_mood = _pick_random(SPICY_THEME_POOLS["moods"], 1)[0]
        s_situation = _pick_random(SPICY_THEME_POOLS["situations"], 1)[0]
        s_clothing = _pick_random(SPICY_THEME_POOLS["clothing"], 1)[0]
        all_kw.extend([
            f"spicy_setting: {s_setting}", f"spicy_mood: {s_mood}",
            f"spicy_situation: {s_situation}", f"spicy_clothing: {s_clothing}",
        ])

    count = 4 + random.randint(0, 2 if not boost else 3)
    return ", ".join(_pick_random(all_kw, min(count, len(all_kw))))


# ---------------------------------------------------------------------------
# SSE log entry helper (per-request context to avoid race conditions)
# ---------------------------------------------------------------------------

class _LogContext:
    """Per-request log context to avoid global mutable state."""

    def __init__(self):
        self._counter = 0

    def create_log_entry(
        self,
        log_type: str,
        content: str,
        title: Optional[str] = None,
        function_name: Optional[str] = None,
        function_args: Optional[dict] = None,
        function_result: Optional[dict] = None,
    ) -> dict:
        self._counter += 1
        return {
            "id": f"log-{self._counter}-{int(time.time() * 1000)}",
            "timestamp": int(time.time() * 1000),
            "type": log_type,
            "title": title,
            "content": content,
            "functionName": function_name,
            "functionArgs": function_args,
            "functionResult": function_result,
        }


def _format_sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Tool builder: creates search_tags / submit_final_tags tools for LangChain
# ---------------------------------------------------------------------------

def _build_tools(tag_db, vector_search, custom_tags: Optional[List[str]] = None, detailed: bool = False):
    """Build LangChain tools for function calling mode."""
    from langchain_core.tools import tool as langchain_tool

    @langchain_tool
    def search_tags(query: str, category: Optional[int] = None, limit: int = 20) -> str:
        """Search for valid Danbooru tags in the database by semantic similarity.
        Returns matching tags with their category and usage count.

        Args:
            query: Search query - a partial tag name, concept, or keyword.
            category: Optional category filter. 0=general, 1=artist, 3=copyright, 4=character, 5=meta.
            limit: Maximum number of results to return (default: 20, max: 50).
        """
        limit = min(limit or 20, 50)
        results = []

        # Vector search
        if vector_search and vector_search.is_loaded:
            vr = vector_search.search(query, k=limit)
            for item in vr:
                if category is not None and item["category"] != category:
                    continue
                results.append({
                    "tag": item["tag"], "category": item["category"],
                    "count": item["count"], "similarity": float(item["score"]),
                })

        # Prefix search
        if tag_db:
            normalized = query.strip().lower().replace(" ", "_").replace("-", "_")
            prefix_results = tag_db.search_prefix(normalized, limit=limit)
            existing = {r["tag"] for r in results}
            for entry in prefix_results:
                if entry.tag not in existing:
                    if category is not None and entry.category != category:
                        continue
                    results.append({
                        "tag": entry.tag, "category": entry.category,
                        "count": entry.count, "similarity": 0.8,
                    })

        # Custom tags
        if custom_tags:
            q_lower = query.lower().replace(" ", "_")
            for ct in custom_tags:
                if ct in {r["tag"] for r in results}:
                    continue
                if q_lower in ct or ct in q_lower:
                    results.append({"tag": ct, "category": 0, "count": 0, "similarity": 0.7})

        results.sort(key=lambda x: x["count"], reverse=True)
        return json.dumps({"tags": results[:limit], "totalFound": len(results)})

    @langchain_tool
    def submit_final_tags(tags: list, reasoning: str = "") -> str:
        """Submit the final list of selected tags. Call this when you have finished selecting all appropriate tags.

        Args:
            tags: Array of validated tag names to use for the image prompt.
            reasoning: Brief explanation of why these tags were selected (optional).
        """
        normalized = [t.strip().lower().replace(" ", "_") for t in tags]
        return json.dumps({"accepted": True, "tags": normalized, "count": len(normalized)})

    tools = [search_tags, submit_final_tags]

    if detailed:
        @langchain_tool
        def validate_tag(tag: str) -> str:
            """Check if a specific tag exists in the database.

            Args:
                tag: The exact tag name with underscores (e.g., "long_hair").
            """
            normalized = tag.strip().lower().replace(" ", "_")
            valid = False
            if tag_db:
                entry = tag_db.exact_match(normalized)
                if entry:
                    valid = True
                elif tag_db.alias_match(normalized):
                    valid = True
            if custom_tags and normalized in custom_tags:
                valid = True
            return json.dumps({"valid": valid, "tag": tag, "normalizedTag": normalized})

        @langchain_tool
        def get_similar_tags(tag: str, limit: int = 10) -> str:
            """Find tags similar to a given tag.

            Args:
                tag: The tag to find similar tags for.
                limit: Maximum number of similar tags to return (default: 10).
            """
            limit = min(limit or 10, 30)
            results = []
            if vector_search and vector_search.is_loaded:
                vr = vector_search.search(tag, k=limit)
                for item in vr:
                    results.append({
                        "tag": item["tag"], "category": item["category"],
                        "count": item["count"],
                    })
            return json.dumps({"originalTag": tag, "similarTags": results})

        tools = [search_tags, validate_tag, get_similar_tags, submit_final_tags]

    return tools


def _create_llm_instance(config: LLMConfig, temperature_override: Optional[float] = None):
    """Create a LangChain LLM instance."""
    temp = temperature_override if temperature_override is not None else config.temperature
    provider = config.provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model, api_key=config.api_key, temperature=temp)
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=config.model, google_api_key=config.api_key, temperature=temp)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.model, base_url=config.ollama_base_url, temperature=temp)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ---------------------------------------------------------------------------
# LLM Service
# ---------------------------------------------------------------------------

class LLMService:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm = None
        self.chain = None
        self._init_llm()

    def _init_llm(self):
        self.llm = _create_llm_instance(self.config)
        self.chain = TAG_GENERATION_PROMPT | self.llm

    def update_config(self, config: LLMConfig):
        """Update LLM configuration at runtime."""
        self.config = config
        self._init_llm()

    # ------------------------------------------------------------------
    # Legacy mode: single-turn generation
    # ------------------------------------------------------------------

    async def generate_tags(
        self,
        description: str,
        num_tags: int = 20,
        include_background: bool = True,
        style: str = "",
    ) -> List[str]:
        """Generate raw tags from natural language description (legacy mode)."""
        user_prompt = build_generate_prompt(description, include_background, style)
        response = await self.chain.ainvoke({
            "description": user_prompt,
            "num_tags": num_tags,
        })
        return self._parse_tags(response.content)

    # ------------------------------------------------------------------
    # Function calling mode: multi-turn with tool use
    # ------------------------------------------------------------------

    async def generate_tags_with_tools(
        self,
        description: str,
        tag_db,
        vector_search,
        num_tags: int = 20,
        include_background: bool = True,
        style: str = "",
        detailed: bool = False,
        anima_mode: bool = False,
        custom_tags: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """Function calling mode. Yields SSE events."""
        log_ctx = _LogContext()

        base_prompt = SYSTEM_PROMPT_FUNCTION_CALLING_DETAILED if detailed else SYSTEM_PROMPT_FUNCTION_CALLING
        system_prompt = base_prompt
        if custom_tags:
            system_prompt += build_custom_tags_section(custom_tags)
        if anima_mode:
            system_prompt += build_anima_mode_section()

        user_prompt = build_generate_prompt(description, include_background, style)
        user_prompt += f"\n\nGenerate approximately {num_tags} tags."

        yield _format_sse("log", log_ctx.create_log_entry(
            "info",
            f"Model: {self.config.provider}/{self.config.model}\n"
            f"Mode: function_calling{'_detailed' if detailed else ''}",
            "Session Started"
        ))

        async for event in self._run_tool_loop(
            system_prompt, user_prompt, tag_db, vector_search,
            custom_tags=custom_tags, detailed=detailed, log_ctx=log_ctx,
        ):
            yield event

    # ------------------------------------------------------------------
    # Random expand mode
    # ------------------------------------------------------------------

    async def random_expand_tags(
        self,
        base_tags: str,
        tag_db,
        vector_search,
        spicy: bool = False,
        boost: bool = False,
        explicit: bool = False,
        anima_mode: bool = False,
        custom_tags: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """Expand base character tags with random scene tags. Yields SSE events."""
        log_ctx = _LogContext()

        if explicit:
            system_prompt_base = SYSTEM_PROMPT_RANDOM_EXPAND_EXPLICIT
            mode_name = "explicit"
        elif boost:
            system_prompt_base = SYSTEM_PROMPT_RANDOM_EXPAND_BOOST
            mode_name = "boost"
        elif spicy:
            system_prompt_base = SYSTEM_PROMPT_RANDOM_EXPAND_SPICY
            mode_name = "spicy"
        else:
            system_prompt_base = SYSTEM_PROMPT_RANDOM_EXPAND
            mode_name = "normal"

        system_prompt = system_prompt_base
        if custom_tags:
            system_prompt += build_custom_tags_section(custom_tags)
        if anima_mode:
            system_prompt += build_anima_mode_section()

        inspiration = generate_inspiration_keywords(spicy, boost, explicit, base_tags)
        seed = random.randint(0, 9999)

        yield _format_sse("log", log_ctx.create_log_entry(
            "info",
            f"Model: {self.config.provider}/{self.config.model}\n"
            f"Mode: random_expand ({mode_name})\nInspiration: {inspiration}\nSeed: {seed}",
            "Random Expand Session Started"
        ))

        char_type_label = ""
        if explicit:
            char_type = detect_character_type(base_tags)
            char_type_label = f"\nCharacter type: {char_type} (STRICTLY follow {char_type} rules)"

        user_prompt = (
            f"Base character tags (keep ALL of these exactly as-is):\n{base_tags}"
            f"{char_type_label}\n\n"
            f"Inspiration keywords (use these as creative direction):\n{inspiration}\n\n"
            f"Random seed: {seed}\n\n"
            f"Expand these base tags into a complete scene prompt. "
            f"Remember: keep all base tags, add composition, expression, situation, "
            f"and background tags that form a coherent scene."
        )

        async for event in self._run_tool_loop(
            system_prompt, user_prompt, tag_db, vector_search,
            custom_tags=custom_tags, temperature_override=0.9, log_ctx=log_ctx,
        ):
            yield event

    # ------------------------------------------------------------------
    # Scene expand mode
    # ------------------------------------------------------------------

    async def scene_expand_tags(
        self,
        base_tags: str,
        scene_description: str,
        tag_db,
        vector_search,
        anima_mode: bool = False,
        custom_tags: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """Expand base tags based on scene description. Yields SSE events."""
        log_ctx = _LogContext()

        system_prompt = SYSTEM_PROMPT_SCENE_EXPAND
        if custom_tags:
            system_prompt += build_custom_tags_section(custom_tags)
        if anima_mode:
            system_prompt += build_anima_mode_section()

        yield _format_sse("log", log_ctx.create_log_entry(
            "info",
            f"Model: {self.config.provider}/{self.config.model}\n"
            f"Mode: scene_expand\nScene: {scene_description}",
            "Scene Expand Session Started"
        ))

        user_prompt = (
            f"Base character tags (keep ALL of these exactly as-is):\n{base_tags}\n\n"
            f"Scene description:\n{scene_description}\n\n"
            f"Expand these base tags into a complete scene prompt that matches the description."
        )

        async for event in self._run_tool_loop(
            system_prompt, user_prompt, tag_db, vector_search,
            custom_tags=custom_tags, temperature_override=0.8, log_ctx=log_ctx,
        ):
            yield event

    # ------------------------------------------------------------------
    # Shared tool-calling loop
    # ------------------------------------------------------------------

    async def _run_tool_loop(
        self,
        system_prompt: str,
        user_prompt: str,
        tag_db,
        vector_search,
        custom_tags: Optional[List[str]] = None,
        detailed: bool = False,
        temperature_override: Optional[float] = None,
        log_ctx: Optional[_LogContext] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the function calling loop."""
        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

        if log_ctx is None:
            log_ctx = _LogContext()

        tools = _build_tools(tag_db, vector_search, custom_tags, detailed)
        llm = _create_llm_instance(self.config, temperature_override)
        llm_with_tools = llm.bind_tools(tools)
        tool_map = {t.name: t for t in tools}

        yield _format_sse("log", log_ctx.create_log_entry("system", system_prompt, "System Prompt"))
        yield _format_sse("log", log_ctx.create_log_entry("user", user_prompt, "User Request"))

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        max_iterations = 50 if detailed else 5
        max_retries = 3
        retry_count = 0

        for iteration in range(max_iterations):
            try:
                response = await llm_with_tools.ainvoke(messages)
                retry_count = 0
            except Exception as e:
                error_msg = str(e)
                if ("429" in error_msg or "Too Many Requests" in error_msg) and retry_count < max_retries:
                    retry_count += 1
                    delay = retry_count * 5
                    yield _format_sse("log", log_ctx.create_log_entry(
                        "info", f"Rate limited. Retrying in {delay}s... ({retry_count}/{max_retries})",
                        "Rate Limit Retry"
                    ))
                    await asyncio.sleep(delay)
                    continue
                yield _format_sse("log", log_ctx.create_log_entry("error", error_msg, "LLM Error"))
                yield _format_sse("complete", {"success": False, "error": error_msg})
                return

            messages.append(response)

            # Log text content
            if response.content:
                text_content = response.content if isinstance(response.content, str) else str(response.content)
                if text_content.strip():
                    yield _format_sse("log", log_ctx.create_log_entry(
                        "model", text_content, f"Model Response (Iteration {iteration + 1})"
                    ))

            # No tool calls → try text fallback
            if not response.tool_calls:
                text = response.content if isinstance(response.content, str) else str(response.content)
                brace_match = re.search(r"\{\s*([^}]+?)\s*\}", text)
                if brace_match:
                    tags = [t.strip() for t in brace_match.group(1).split(",") if t.strip()]
                    if tags:
                        final = [t.replace("_", " ") for t in tags]
                        yield _format_sse("complete", {
                            "success": True, "tags": final, "promptText": ", ".join(final),
                        })
                        return
                yield _format_sse("complete", {"success": False, "error": "No valid tags generated"})
                return

            # Process ALL tool calls first, then check for termination
            final_result = None
            for tc in response.tool_calls:
                func_name = tc["name"]
                func_args = tc["args"]

                yield _format_sse("log", log_ctx.create_log_entry(
                    "function_call", "", func_name,
                    function_name=func_name, function_args=func_args,
                ))

                if func_name in tool_map:
                    try:
                        result_str = await tool_map[func_name].ainvoke(func_args)
                        result_data = json.loads(result_str)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})
                        result_data = {"error": str(e)}
                else:
                    result_str = json.dumps({"error": f"Unknown function: {func_name}"})
                    result_data = {"error": f"Unknown function: {func_name}"}

                yield _format_sse("log", log_ctx.create_log_entry(
                    "function_result", "", func_name,
                    function_name=func_name, function_result=result_data,
                ))

                messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))

                if func_name == "submit_final_tags" and "error" not in result_data:
                    final_result = result_data

            # Check if submit_final_tags was called
            if final_result is not None:
                final = [t.replace("_", " ") for t in final_result.get("tags", [])]
                yield _format_sse("log", log_ctx.create_log_entry(
                    "info", f"Final tags ({len(final)}):\n{', '.join(final)}", "Complete"
                ))
                yield _format_sse("complete", {
                    "success": True, "tags": final, "promptText": ", ".join(final),
                })
                return

        yield _format_sse("log", log_ctx.create_log_entry(
            "error", f"Stopped after {max_iterations} iterations", "Max Iterations Reached"
        ))
        yield _format_sse("complete", {"success": False, "error": "Max iterations reached"})

    # ------------------------------------------------------------------
    # Tag parsing (for legacy mode)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tags(raw_text: str) -> List[str]:
        """Parse LLM output into individual tag strings."""
        text = re.sub(r"```[a-z]*\n?", "", raw_text).strip()

        # Try curly braces format first
        brace_match = re.search(r"\{\s*([^}]+?)\s*\}", text)
        if brace_match:
            text = brace_match.group(1)

        text = re.sub(r"^\s*[\d]+[.)]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.MULTILINE)

        if "," in text:
            tags = [t.strip() for t in text.split(",")]
        else:
            tags = [t.strip() for t in text.split("\n")]

        cleaned = []
        for tag in tags:
            tag = tag.strip().strip("\"'`")
            tag = re.sub(r"\s+", "_", tag.lower())
            tag = re.sub(r"[^a-z0-9_()\-:/]", "", tag)
            if tag:
                cleaned.append(tag)

        return cleaned
