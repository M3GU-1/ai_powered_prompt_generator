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
from backend.usage_tracker import record_usage
from backend.prompt_templates import (
    TAG_GENERATION_PROMPT,
    SYSTEM_PROMPT_FUNCTION_CALLING,
    SYSTEM_PROMPT_FUNCTION_CALLING_DETAILED,
    SYSTEM_PROMPT_RANDOM_EXPAND,
    SYSTEM_PROMPT_RANDOM_EXPAND_SPICY,
    SYSTEM_PROMPT_RANDOM_EXPAND_BOOST,
    SYSTEM_PROMPT_RANDOM_EXPAND_EXPLICIT,
    SYSTEM_PROMPT_SCENE_EXPAND,
    SYSTEM_PROMPT_IMAGE_ANALYSIS_FUNCTION_CALLING,
    SYSTEM_PROMPT_IMAGE_ANALYSIS_FUNCTION_CALLING_DETAILED,
    IMAGE_ANALYSIS_CHAT_PRESET_NORMAL,
    IMAGE_ANALYSIS_CHAT_PRESET_DETAILED,
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
        # Indoor locations
        "bedroom", "kitchen", "bathroom", "library", "classroom", "office",
        "cafe", "restaurant", "bar", "bookstore", "gym", "arcade", "studio",
        "workshop", "laboratory", "hospital", "church", "museum", "gallery",
        "theater", "cinema", "hotel room", "locker room", "hallway", "staircase",
        "elevator", "attic", "basement", "greenhouse", "observatory",
        # Outdoor urban
        "city street", "rooftop", "balcony", "alley", "market", "shopping district",
        "train station", "bus stop", "parking lot", "bridge", "plaza", "fountain",
        "amusement park", "festival", "carnival", "stadium", "construction site",
        "harbor", "dock", "lighthouse", "clock tower", "overpass",
        # Outdoor nature
        "beach", "forest", "mountain", "field", "flower field", "river",
        "lake", "ocean", "waterfall", "cliff", "cave", "desert", "snow field",
        "bamboo forest", "meadow", "hill", "valley", "hot spring", "pond",
        "swamp", "vineyard", "orchard", "farm", "countryside",
        # Cultural/fantasy
        "shrine", "temple", "torii gate", "castle", "ruins", "dungeon",
        "throne room", "garden", "park", "cemetery", "pagoda", "palace",
        "courtyard", "veranda", "gazebo", "dojo", "arena",
        # Transport
        "train interior", "bus interior", "car interior", "airplane cabin",
        "ship deck", "submarine",
        # Unusual
        "underwater", "space", "floating island", "cloud top",
        "mirror world", "dream world", "void",
    ],
    "weather": [
        "sunny", "rainy", "snowy", "cloudy", "foggy", "stormy", "windy",
        "clear sky", "overcast", "drizzle", "heavy rain", "blizzard",
        "thunder and lightning", "hail", "misty", "humid",
        "scorching heat", "freezing cold", "gentle breeze",
    ],
    "sky": [
        "blue sky", "sunset", "sunrise", "twilight", "night sky",
        "starry sky", "full moon", "crescent moon", "aurora",
        "orange sky", "red sky", "purple sky", "gradient sky",
        "shooting star", "eclipse", "cloudy sky", "grey sky",
        "moonlight", "golden hour",
    ],
    "moods": [
        "cheerful", "melancholic", "peaceful", "dramatic", "mysterious",
        "romantic", "playful", "serious", "dreamy", "nostalgic", "energetic",
        "calm", "tense", "cozy", "lonely", "warm", "whimsical", "bittersweet",
        "eerie", "hopeful", "triumphant", "contemplative", "carefree",
        "solemn", "mischievous", "ethereal", "gritty", "serene",
        "chaotic", "sentimental", "majestic",
    ],
    "activities": [
        "reading", "cooking", "walking", "sitting", "running", "dancing",
        "singing", "fighting", "sleeping", "eating", "drinking", "shopping",
        "studying", "working", "playing", "painting", "photographing",
        "stretching", "leaning", "looking away", "waving", "holding phone",
        "carrying bag", "swimming", "fishing", "gardening", "cleaning",
        "writing", "drawing", "knitting", "sewing", "playing guitar",
        "playing piano", "playing violin", "skateboarding", "cycling",
        "climbing", "surfing", "meditating", "praying", "stargazing",
        "daydreaming", "whispering", "arguing", "laughing", "crying",
        "smoking", "drinking tea", "drinking coffee", "playing games",
        "feeding animals", "flying a kite", "catching fireflies",
        "picking flowers", "making a snowman", "watching fireworks",
    ],
    "compositions": [
        "portrait", "upper body", "full body", "cowboy shot", "close-up",
        "dutch angle", "bird's eye view", "worm's eye view", "wide shot",
        "over the shoulder", "profile view", "three-quarter view",
        "fisheye lens", "depth of field", "bokeh", "motion blur",
        "split screen", "multiple views", "pov", "selfie",
        "panoramic", "symmetrical composition", "diagonal composition",
    ],
    "lighting": [
        "backlighting", "rim lighting", "sunbeam", "dappled sunlight",
        "candlelight", "neon lights", "lamplight", "firelight",
        "moonlight beam", "spotlight", "lens flare", "light particles",
        "volumetric light", "silhouette", "chiaroscuro",
        "soft lighting", "harsh lighting", "reflected light",
        "underwater caustics", "stained glass light",
    ],
    "nature_effects": [
        "cherry blossoms", "falling petals", "falling leaves", "autumn leaves",
        "snowflakes", "raindrops", "bubbles", "fireflies", "butterflies",
        "dandelion seeds", "feathers floating", "sparks", "embers",
        "ripples on water", "waves", "wind-blown hair", "dust motes",
        "rose petals", "pollen", "spider web with dew",
    ],
    "accessories": [
        "umbrella", "parasol", "sword", "gun", "book", "phone", "camera",
        "guitar", "violin", "headphones", "mask", "crown", "tiara",
        "scarf", "fan", "lantern", "balloon", "flag", "shield", "staff",
        "wand", "wine glass", "teacup", "basket", "flower bouquet",
        "teddy bear", "gift box", "love letter", "birdcage", "pocket watch",
        "locket", "music box", "snow globe", "hand mirror", "ribbon",
    ],
    "themes": [
        "school life", "office worker", "fantasy adventure", "slice of life",
        "military", "cyberpunk", "steampunk", "post-apocalyptic",
        "fairy tale", "mythology", "historical", "modern urban",
        "rural countryside", "pirate", "detective noir", "magical girl",
        "idol performance", "sports", "martial arts", "cooking show",
        "travel", "festival celebration", "graduation", "wedding",
        "birthday party", "summer vacation", "winter holiday",
    ],
    "seasons": ["spring", "summer", "autumn", "winter", "rainy season", "dry season"],
    "time_of_day": [
        "early morning", "morning", "midday", "afternoon",
        "golden hour", "evening", "twilight", "night", "midnight",
        "dawn", "dusk", "witching hour",
    ],
}

SPICY_THEME_POOLS = {
    "settings": [
        "bedroom", "bathroom", "hot spring", "locker room", "beach", "pool",
        "bed", "couch", "shower", "onsen", "sauna", "changing room",
        "hotel room", "balcony at night", "private room", "dimly lit room",
        "massage parlor", "backstage dressing room", "rooftop at night",
        "moonlit garden", "luxury bath", "penthouse", "spa",
        "canopy bed", "jacuzzi", "poolside lounge", "yacht cabin",
        "spring meadow", "secluded beach cove", "forest clearing at dusk",
    ],
    "moods": [
        "seductive", "embarrassed", "shy", "provocative", "sensual",
        "flirtatious", "intimate", "vulnerable", "playful", "bold",
        "bashful", "dreamy", "heated", "teasing", "yearning",
        "coy", "inviting", "breathless", "dazed", "aroused",
        "submissive curiosity", "dominant confidence", "innocent temptation",
        "reluctant attraction", "surprised arousal",
    ],
    "situations": [
        "undressing", "after bath", "waking up", "lying down", "stretching",
        "wardrobe malfunction", "caught off guard", "posing", "leaning forward",
        "sitting on bed", "back view", "looking back", "hand on chest",
        "covering body", "hair down", "towel slipping", "adjusting clothing",
        "bending over to pick up", "trying on clothes", "mirror selfie",
        "wind lifting skirt", "eating seductively", "licking lips",
        "blowing a kiss", "playing with hair", "crossing legs",
        "shoulder peek", "clothes sticking to body from sweat",
        "drying hair", "applying lotion", "sleeping pose",
    ],
    "clothing": [
        "lingerie", "swimsuit", "towel", "oversized shirt", "nightgown",
        "negligee", "off-shoulder", "bare shoulders", "revealing outfit",
        "unbuttoned shirt", "tank top", "sports bra", "crop top", "miniskirt",
        "shorts", "see-through dress", "wet white shirt", "bikini",
        "micro bikini", "string bikini", "bodysuit", "leotard",
        "garter belt with thigh highs", "corset", "halter top",
        "backless dress", "side-slit dress", "naked apron",
        "open-back sweater", "virgin killer sweater", "tube top",
        "fishnet stockings", "lace underwear", "chemise",
    ],
    "camera_angles": [
        "from below", "from above", "close-up on face", "close-up on body",
        "between legs pov", "over shoulder", "voyeuristic angle",
        "mirror reflection", "through window", "peek through door",
    ],
}

BOOST_THEME_POOLS = {
    "settings": [
        "bed", "bathroom", "shower", "hot spring", "dimly lit room",
        "hotel room", "private room", "onsen", "sauna", "bedroom at night",
        "love hotel", "tent interior", "outdoor bath", "moonlit room",
        "candlelit room", "luxury suite", "hidden spring", "steamy bathroom",
        "silk-draped bed", "rooftop under stars", "forest glade",
        "waterfall pool", "beach at night", "windowsill with moonlight",
    ],
    "moods": [
        "intimate", "passionate", "overwhelmed", "submissive", "dominant",
        "desperate", "yearning", "ecstatic", "helpless", "inviting",
        "begging", "trembling", "languid", "abandoned", "surrendered",
        "intoxicated", "entranced", "fever-dream", "delirious",
        "pleading", "worshipful", "melting", "euphoric",
    ],
    "situations": [
        "lying on bed", "pinned down", "on all fours", "straddling",
        "embracing", "restrained", "collared", "blindfolded", "tied up",
        "spread legs", "from behind", "on back", "kneeling", "bending over",
        "wrapped in sheets", "arching back", "legs up", "fetal position",
        "crawling", "presenting", "chained to wall", "sitting on lap",
        "cradling self", "gripping sheets", "writhing", "reaching out",
        "looking over shoulder", "hands above head", "legs intertwined",
    ],
    "states": [
        "fully undressed", "clothes removed", "bare skin", "skin exposed",
        "nothing worn", "stripped", "uncovered", "in the buff", "au naturel",
        "clothes pulled aside", "torn clothes", "clothes falling off",
        "half undressed", "shirt lifted", "skirt pulled up",
        "panties pulled aside", "bra unclasped", "dress sliding off shoulder",
        "strategically covered", "body paint only", "bandage only",
        "flower petals covering", "convenient censoring with hair",
    ],
    "body_emphasis": [
        "back muscles", "collarbone", "spine", "hip bones",
        "shoulder blades", "thigh gap", "waist curve",
        "neck nape", "wrist veins", "ankle", "inner thigh",
        "lower back dimples", "rib outline", "stomach line",
    ],
    "atmosphere": [
        "steam rising", "water droplets on skin", "candlelight flicker",
        "moonbeam through curtain", "silk texture", "flower petals scattered",
        "incense smoke", "morning dew", "rain on window",
        "soft fabric draping", "mirror reflection", "wet floor reflection",
    ],
}

EXPLICIT_THEME_POOLS = {
    "settings": [
        "bed", "love hotel", "dimly lit room", "shower", "hot spring",
        "bedroom at night", "classroom", "office", "onsen", "tent interior",
        "bathroom", "against wall", "alley", "outdoors", "car interior",
        "public restroom", "locker room", "rooftop", "storage room",
        "under desk", "infirmary", "stairwell", "elevator",
        "throne room", "dungeon", "prison cell", "backstage",
        "teacher's desk", "fitting room", "train interior",
    ],
    "moods": [
        "passionate", "rough", "gentle", "desperate", "submissive",
        "dominant", "lustful", "forced", "consensual", "teasing",
        "begging", "reluctant", "aggressive", "tender", "frantic",
        "lazy", "competitive", "worshipful", "degrading", "loving",
        "animalistic", "playful", "vengeful", "obsessive",
    ],
    "acts_solo": [
        "masturbation", "female_masturbation", "fingering", "object_insertion",
        "dildo", "vibrator", "humping", "tentacles", "machine",
        "pillow_humping", "shower_head", "grinding_on_object",
        "self_groping", "nipple_play", "mirror_masturbation",
    ],
    "acts_duo": [
        "sex", "vaginal", "anal", "fellatio", "cunnilingus", "paizuri",
        "handjob", "footjob", "intercrural", "frottage", "deep_throat",
        "irrumatio", "sumata", "thigh_sex", "hotdogging",
        "rimjob", "prostate_massage", "mutual_masturbation",
        "scissoring", "dry_humping", "ear_licking", "nipple_sucking",
        "face_fuck", "armpit_sex",
    ],
    "acts_group": [
        "double_penetration", "spitroast", "gangbang", "orgy", "group_sex",
        "threesome", "train_position", "bukkake", "airtight",
        "daisy_chain", "all_fours_lineup", "sandwich_position",
        "simultaneous_penetration", "audience_participation",
    ],
    "positions_duo": [
        "missionary", "cowgirl_position", "doggystyle", "standing_sex",
        "prone_bone", "mating_press", "suspended_congress", "lotus_position",
        "spooning", "leg_lock", "wheelbarrow_position", "carrying",
        "against_wall", "bent_over", "face_sitting", "sixty-nine",
        "reverse_cowgirl", "amazon_position", "pile_driver",
        "standing_split", "full_nelson", "pretzel", "lazy_dog",
        "anvil_position", "bridge_position", "table_top",
        "folded_legs", "side_by_side", "lap_sex",
    ],
    "expressions": [
        "ahegao", "fucked_silly", "open_mouth", "tongue_out", "rolling_eyes",
        "crying_with_pleasure", "drooling", "heavy_breathing", "panting",
        "screaming", "moaning", "cross-eyed", "vacant_eyes", "tears_of_joy",
        "biting_lip", "gritting_teeth", "smirking", "begging_face",
        "dazed", "twitching", "eye_roll", "half-lidded_euphoria",
        "silent_scream", "whimpering", "gasping",
    ],
    "body_states": [
        "sweat", "cum", "cum_on_body", "cum_in_pussy", "cum_on_face",
        "cum_on_breasts", "trembling", "blush", "wet", "saliva", "tears",
        "bite_mark", "hickey", "cum_in_mouth", "cum_overflow",
        "creampie", "cumdrip", "saliva_trail", "pussy_juice",
        "precum", "female_ejaculation", "dripping", "love_juice",
        "body_writing", "handprint_mark", "rope_marks",
    ],
    "clothing_states": [
        "clothes_aside", "lifted_skirt", "open_shirt", "unbuttoned",
        "panties_aside", "bra_pull", "shirt_lift", "dress_pull",
        "torn_clothes", "ripped_panties", "unzipped", "half_undressed",
        "skirt_around_ankles", "shirt_grab", "collar_pull",
        "stockings_only", "gloves_only", "boots_only",
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
    # --- Base keywords (common to all modes) ---
    setting = _pick_random(THEME_POOLS["settings"], 1)[0]
    weather = _pick_random(THEME_POOLS["weather"], 1)[0]
    sky = _pick_random(THEME_POOLS["sky"], 1)[0]
    mood = _pick_random(THEME_POOLS["moods"], 1)[0]
    activity = _pick_random(THEME_POOLS["activities"], 1)[0]
    composition = _pick_random(THEME_POOLS["compositions"], 1)[0]
    lighting = _pick_random(THEME_POOLS["lighting"], 1)[0]
    nature_effect = _pick_random(THEME_POOLS["nature_effects"], 1)[0]
    accessory = _pick_random(THEME_POOLS["accessories"], 1)[0]
    theme = _pick_random(THEME_POOLS["themes"], 1)[0]
    season = _pick_random(THEME_POOLS["seasons"], 1)[0]
    time_val = _pick_random(THEME_POOLS["time_of_day"], 1)[0]

    all_kw = [
        f"setting: {setting}", f"weather: {weather}", f"sky: {sky}",
        f"mood: {mood}", f"activity: {activity}", f"composition: {composition}",
        f"lighting: {lighting}", f"nature_effect: {nature_effect}",
        f"accessory: {accessory}", f"theme: {theme}",
        f"season: {season}", f"time: {time_val}",
    ]

    if explicit:
        char_type = detect_character_type(base_tags)
        e_setting = _pick_random(EXPLICIT_THEME_POOLS["settings"], 1)[0]
        e_mood = _pick_random(EXPLICIT_THEME_POOLS["moods"], 1)[0]
        e_expression = _pick_random(EXPLICIT_THEME_POOLS["expressions"], 1)[0]
        e_body_state = _pick_random(EXPLICIT_THEME_POOLS["body_states"], 1)[0]
        e_clothing_state = _pick_random(EXPLICIT_THEME_POOLS["clothing_states"], 1)[0]
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
            f"clothing_state: {e_clothing_state}",
        ]
        if char_type != "solo":
            e_position = _pick_random(EXPLICIT_THEME_POOLS["positions_duo"], 1)[0]
            explicit_kw.append(f"position: {e_position}")
        generic_sample = _pick_random(all_kw, 3 + random.randint(0, 2))
        return ", ".join(explicit_kw + generic_sample)

    elif boost:
        b_setting = _pick_random(BOOST_THEME_POOLS["settings"], 1)[0]
        b_mood = _pick_random(BOOST_THEME_POOLS["moods"], 1)[0]
        b_situation = _pick_random(BOOST_THEME_POOLS["situations"], 1)[0]
        b_state = _pick_random(BOOST_THEME_POOLS["states"], 1)[0]
        b_body = _pick_random(BOOST_THEME_POOLS["body_emphasis"], 1)[0]
        b_atmo = _pick_random(BOOST_THEME_POOLS["atmosphere"], 1)[0]
        all_kw.extend([
            f"scene: {b_setting}", f"emotion: {b_mood}",
            f"pose: {b_situation}", f"attire_state: {b_state}",
            f"body_focus: {b_body}", f"atmosphere: {b_atmo}",
        ])

    elif spicy:
        s_setting = _pick_random(SPICY_THEME_POOLS["settings"], 1)[0]
        s_mood = _pick_random(SPICY_THEME_POOLS["moods"], 1)[0]
        s_situation = _pick_random(SPICY_THEME_POOLS["situations"], 1)[0]
        s_clothing = _pick_random(SPICY_THEME_POOLS["clothing"], 1)[0]
        s_angle = _pick_random(SPICY_THEME_POOLS["camera_angles"], 1)[0]
        all_kw.extend([
            f"spicy_setting: {s_setting}", f"spicy_mood: {s_mood}",
            f"spicy_situation: {s_situation}", f"spicy_clothing: {s_clothing}",
            f"camera_angle: {s_angle}",
        ])

    count = 6 + random.randint(0, 3 if not boost else 4)
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


def _enrich_final_tags(tag_strings: list, tag_db) -> list:
    """Look up each tag in tag_db and return enriched dicts with metadata.

    Returns list of dicts compatible with TagCandidate schema:
    {tag, category, count, match_method, similarity_score, llm_original}
    """
    enriched = []
    for raw in tag_strings:
        normalized = raw.strip().lower().replace(" ", "_").replace("-", "_")
        llm_original = raw

        if tag_db:
            # Stage 1: exact match
            entry = tag_db.exact_match(normalized)
            if entry:
                enriched.append({
                    "tag": entry.tag, "category": entry.category,
                    "count": entry.count, "match_method": "exact",
                    "similarity_score": 1.0, "llm_original": llm_original,
                })
                continue

            # Stage 2: alias match
            entry = tag_db.alias_match(normalized)
            if entry:
                enriched.append({
                    "tag": entry.tag, "category": entry.category,
                    "count": entry.count, "match_method": "alias",
                    "similarity_score": 1.0, "llm_original": llm_original,
                })
                continue

        # Not found in DB
        enriched.append({
            "tag": normalized, "category": 0,
            "count": 0, "match_method": "unmatched",
            "similarity_score": 0.0, "llm_original": llm_original,
        })

    return enriched

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
    def submit_final_tags(tags: List[str], reasoning: str = "") -> str:
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
        kwargs: dict = dict(
            model=config.model,
            google_api_key=config.api_key,
            temperature=temp,
        )
        # Gemini 3.x "thinking" models require thought_signature handling
        # that langchain-google-genai ≤2.x does not fully support yet.
        # Disable the thinking budget so function-calling works reliably.
        model_lower = config.model.lower()
        if "gemini-3" in model_lower or "gemini-exp" in model_lower:
            kwargs["thinking_budget"] = 0
        return ChatGoogleGenerativeAI(**kwargs)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.model, base_url=config.ollama_base_url, temperature=temp)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _needs_native_gemini(config: LLMConfig) -> bool:
    """Check if we need the native google-genai SDK path (for Gemini 3.x+).

    langchain-google-genai <=2.x doesn't handle thought_signature for
    Gemini 3 models, so we use the google-genai SDK directly.
    """
    if config.provider.lower() != "gemini":
        return False
    model_lower = config.model.lower()
    return "gemini-3" in model_lower or "gemini-exp" in model_lower


async def _run_tool_loop_native_gemini(
    config: LLMConfig,
    system_prompt: str,
    user_prompt: str,
    tools,
    detailed: bool = False,
    log_ctx: Optional[_LogContext] = None,
    image_url: Optional[str] = None,
    chat_preset: Optional[str] = None,
    tag_db=None,
) -> AsyncGenerator[str, None]:
    """Run the function-calling loop using the native google-genai SDK.

    This bypasses LangChain for Gemini 3.x models where thought_signature
    handling is required and not supported by langchain-google-genai <=2.x.
    The google-genai SDK handles thought_signatures automatically.
    """
    import base64 as b64_mod
    from google import genai
    from google.genai import types

    if log_ctx is None:
        log_ctx = _LogContext()

    client = genai.Client(api_key=config.api_key)

    # Convert LangChain tools to google-genai FunctionDeclarations
    func_declarations = []
    tool_handlers = {}
    for t in tools:
        schema = t.args_schema.model_json_schema()
        # Remove keys that are not valid for Gemini function declarations
        clean_schema = {
            "type": schema.get("type", "object"),
            "properties": schema.get("properties", {}),
        }
        if "required" in schema:
            clean_schema["required"] = schema["required"]
        # Clean property descriptions - remove 'title' fields that confuse Gemini
        for prop_name, prop_val in clean_schema["properties"].items():
            prop_val.pop("title", None)
            prop_val.pop("default", None)
        fd = types.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters_json_schema=clean_schema,
        )
        func_declarations.append(fd)
        tool_handlers[t.name] = t

    genai_tools = [types.Tool(function_declarations=func_declarations)]

    # Build conversation contents
    contents = []

    # Chat preset for censorship evasion
    if chat_preset:
        contents.append(types.Content(role="user", parts=[
            types.Part.from_text(text="I will provide content for analysis using the tag database."),
        ]))
        contents.append(types.Content(role="model", parts=[
            types.Part.from_text(text=chat_preset),
        ]))
        yield _format_sse("log", log_ctx.create_log_entry(
            "model", chat_preset, "Model Initial Response (Chat Preset)"
        ))

    # User message (optionally with image)
    user_parts = [types.Part.from_text(text=user_prompt)]
    if image_url:
        match = re.match(r"data:([^;]+);base64,(.+)", image_url, re.DOTALL)
        if match:
            mime = match.group(1)
            raw = b64_mod.b64decode(match.group(2))
            user_parts.append(types.Part.from_bytes(data=raw, mime_type=mime))
    contents.append(types.Content(role="user", parts=user_parts))

    gen_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=genai_tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=config.temperature,
    )

    max_iterations = 50 if detailed else 5
    max_retries = 3
    retry_count = 0

    # Token usage accumulators
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_creation = 0

    def _build_usage():
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_tokens": total_cache_read,
            "cache_creation_tokens": total_cache_creation,
            "total_tokens": total_input + total_output,
            "provider": config.provider,
            "model": config.model,
        }

    for iteration in range(max_iterations):
        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=contents,
                config=gen_config,
            )
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
            await record_usage(_build_usage())
            yield _format_sse("complete", {"success": False, "error": error_msg, "usage": _build_usage()})
            return

        # Extract token usage from response
        um = getattr(response, "usage_metadata", None)
        if um:
            total_input += getattr(um, "prompt_token_count", 0) or 0
            total_output += getattr(um, "candidates_token_count", 0) or 0
            total_cache_read += getattr(um, "cached_content_token_count", 0) or 0

        # Append model response to conversation (preserves thought_signature)
        model_content = response.candidates[0].content
        contents.append(model_content)

        # Extract text from response (may be None if only function calls)
        text_parts = [p.text for p in model_content.parts if hasattr(p, "text") and p.text]
        text_content = "\n".join(text_parts) if text_parts else ""

        if text_content.strip():
            yield _format_sse("log", log_ctx.create_log_entry(
                "model", text_content, f"Model Response (Iteration {iteration + 1})"
            ))

        # Check for function calls
        func_calls = response.function_calls
        if not func_calls:
            # Try text fallback (tags in braces)
            brace_match = re.search(r"\{\s*([^}]+?)\s*\}", text_content)
            if brace_match:
                tags = [t.strip() for t in brace_match.group(1).split(",") if t.strip()]
                if tags:
                    enriched = _enrich_final_tags(tags, tag_db)
                    tag_names = [t["tag"].replace("_", " ") for t in enriched]
                    await record_usage(_build_usage())
                    yield _format_sse("complete", {
                        "success": True, "tags": enriched, "promptText": ", ".join(tag_names),
                        "usage": _build_usage(),
                    })
                    return
            await record_usage(_build_usage())
            yield _format_sse("complete", {"success": False, "error": "No valid tags generated", "usage": _build_usage()})
            return

        # Process all tool calls
        response_parts = []
        final_result = None

        for fc in func_calls:
            func_name = fc.name
            func_args = dict(fc.args) if fc.args else {}

            yield _format_sse("log", log_ctx.create_log_entry(
                "function_call", "", func_name,
                function_name=func_name, function_args=func_args,
            ))

            if func_name in tool_handlers:
                try:
                    result_str = await tool_handlers[func_name].ainvoke(func_args)
                    result_data = json.loads(result_str)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    result_data = {"error": str(e)}
            else:
                result_data = {"error": f"Unknown function: {func_name}"}

            yield _format_sse("log", log_ctx.create_log_entry(
                "function_result", "", func_name,
                function_name=func_name, function_result=result_data,
            ))

            response_parts.append(types.Part.from_function_response(
                name=func_name, response=result_data,
            ))

            if func_name == "submit_final_tags" and "error" not in result_data:
                final_result = result_data

        # Append tool responses to conversation
        contents.append(types.Content(role="tool", parts=response_parts))

        # Check if submit_final_tags was called
        if final_result is not None:
            raw_tags = final_result.get("tags", [])
            enriched = _enrich_final_tags(raw_tags, tag_db)
            tag_names = [t["tag"].replace("_", " ") for t in enriched]
            yield _format_sse("log", log_ctx.create_log_entry(
                "info", f"Final tags ({len(enriched)}):\n{', '.join(tag_names)}", "Complete"
            ))
            await record_usage(_build_usage())
            yield _format_sse("complete", {
                "success": True, "tags": enriched, "promptText": ", ".join(tag_names),
                "usage": _build_usage(),
            })
            return

    yield _format_sse("log", log_ctx.create_log_entry(
        "error", f"Stopped after {max_iterations} iterations", "Max Iterations Reached"
    ))
    await record_usage(_build_usage())
    yield _format_sse("complete", {"success": False, "error": "Max iterations reached", "usage": _build_usage()})


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
    # Image analysis mode (multimodal)
    # ------------------------------------------------------------------

    async def analyze_image_with_tools(
        self,
        image_base64: str,
        mime_type: str,
        tag_db,
        vector_search,
        detailed: bool = False,
        anima_mode: bool = False,
        custom_tags: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """Analyze an image and extract tags via function calling. Yields SSE events.

        Uses censorship-evasion techniques from the original project:
        1. Expert role framing ("Danbooru tag database expert")
        2. Function calling bypass (structured tool calls, not free text)
        3. Database-first framing ("search, don't create")
        4. Chat history preset (pre-seeded cooperative response)
        """
        log_ctx = _LogContext()

        base_prompt = (
            SYSTEM_PROMPT_IMAGE_ANALYSIS_FUNCTION_CALLING_DETAILED
            if detailed
            else SYSTEM_PROMPT_IMAGE_ANALYSIS_FUNCTION_CALLING
        )
        system_prompt = base_prompt
        if custom_tags:
            system_prompt += build_custom_tags_section(custom_tags)
        if anima_mode:
            system_prompt += build_anima_mode_section()

        chat_preset = (
            IMAGE_ANALYSIS_CHAT_PRESET_DETAILED
            if detailed
            else IMAGE_ANALYSIS_CHAT_PRESET_NORMAL
        )

        yield _format_sse("log", log_ctx.create_log_entry(
            "info",
            f"Model: {self.config.provider}/{self.config.model}\n"
            f"Mode: image_analysis{'_detailed' if detailed else ''}\n"
            f"Image: {mime_type}",
            "Image Analysis Session Started"
        ))

        user_prompt = (
            "Analyze this image and extract Stable Diffusion/Danbooru tags that "
            "accurately describe the image. Search the tag database to validate all tags."
        )

        # Build image data URL for LangChain multimodal
        image_url = f"data:{mime_type};base64,{image_base64}"

        async for event in self._run_tool_loop(
            system_prompt, user_prompt, tag_db, vector_search,
            custom_tags=custom_tags, detailed=detailed, log_ctx=log_ctx,
            image_url=image_url, chat_preset=chat_preset,
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
        image_url: Optional[str] = None,
        chat_preset: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the function calling loop.

        Args:
            image_url: Optional data URL for multimodal image input
                       (e.g. "data:image/png;base64,...")
            chat_preset: Optional pre-seeded AI response for censorship evasion.
                         Inserted before the user message to make the AI
                         "pre-agree" to the task.
        """
        if log_ctx is None:
            log_ctx = _LogContext()

        tools = _build_tools(tag_db, vector_search, custom_tags, detailed)

        # Gemini 3.x requires thought_signature handling not supported by
        # langchain-google-genai <=2.x.  Delegate to native google-genai SDK.
        if _needs_native_gemini(self.config):
            yield _format_sse("log", log_ctx.create_log_entry("system", system_prompt, "System Prompt"))
            if image_url:
                yield _format_sse("log", log_ctx.create_log_entry(
                    "user", "Image uploaded for analysis", "Image Uploaded"
                ))
            else:
                yield _format_sse("log", log_ctx.create_log_entry("user", user_prompt, "User Request"))
            async for event in _run_tool_loop_native_gemini(
                self.config, system_prompt, user_prompt, tools,
                detailed=detailed, log_ctx=log_ctx,
                image_url=image_url, chat_preset=chat_preset,
                tag_db=tag_db,
            ):
                yield event
            return

        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

        llm = _create_llm_instance(self.config, temperature_override)
        llm_with_tools = llm.bind_tools(tools)
        tool_map = {t.name: t for t in tools}

        yield _format_sse("log", log_ctx.create_log_entry("system", system_prompt, "System Prompt"))

        if image_url:
            yield _format_sse("log", log_ctx.create_log_entry(
                "user", "Image uploaded for analysis", "Image Uploaded"
            ))
        else:
            yield _format_sse("log", log_ctx.create_log_entry("user", user_prompt, "User Request"))

        messages = [SystemMessage(content=system_prompt)]

        # Chat history preset: pre-seed cooperative AI response (censorship evasion)
        if chat_preset:
            messages.append(HumanMessage(content="I will provide content for analysis using the tag database."))
            messages.append(AIMessage(content=chat_preset))
            yield _format_sse("log", log_ctx.create_log_entry(
                "model", chat_preset, "Model Initial Response (Chat Preset)"
            ))

        # Build user message (optionally with image)
        if image_url:
            messages.append(HumanMessage(content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]))
        else:
            messages.append(HumanMessage(content=user_prompt))

        max_iterations = 50 if detailed else 5
        max_retries = 3
        retry_count = 0

        # Token usage accumulators
        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_creation = 0

        def _build_usage():
            return {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cache_read_tokens": total_cache_read,
                "cache_creation_tokens": total_cache_creation,
                "total_tokens": total_input + total_output,
                "provider": self.config.provider,
                "model": self.config.model,
            }

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
                await record_usage(_build_usage())
                yield _format_sse("complete", {"success": False, "error": error_msg, "usage": _build_usage()})
                return

            # Extract token usage from LangChain response
            usage_meta = getattr(response, "usage_metadata", None) or {}
            total_input += usage_meta.get("input_tokens", 0)
            total_output += usage_meta.get("output_tokens", 0)
            total_cache_read += usage_meta.get("cache_read_input_tokens", 0)
            total_cache_creation += usage_meta.get("cache_creation_input_tokens", 0)

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
                        enriched = _enrich_final_tags(tags, tag_db)
                        tag_names = [t["tag"].replace("_", " ") for t in enriched]
                        await record_usage(_build_usage())
                        yield _format_sse("complete", {
                            "success": True, "tags": enriched, "promptText": ", ".join(tag_names),
                            "usage": _build_usage(),
                        })
                        return
                await record_usage(_build_usage())
                yield _format_sse("complete", {"success": False, "error": "No valid tags generated", "usage": _build_usage()})
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
                raw_tags = final_result.get("tags", [])
                enriched = _enrich_final_tags(raw_tags, tag_db)
                tag_names = [t["tag"].replace("_", " ") for t in enriched]
                yield _format_sse("log", log_ctx.create_log_entry(
                    "info", f"Final tags ({len(enriched)}):\n{', '.join(tag_names)}", "Complete"
                ))
                await record_usage(_build_usage())
                yield _format_sse("complete", {
                    "success": True, "tags": enriched, "promptText": ", ".join(tag_names),
                    "usage": _build_usage(),
                })
                return

        yield _format_sse("log", log_ctx.create_log_entry(
            "error", f"Stopped after {max_iterations} iterations", "Max Iterations Reached"
        ))
        await record_usage(_build_usage())
        yield _format_sse("complete", {"success": False, "error": "Max iterations reached", "usage": _build_usage()})

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
