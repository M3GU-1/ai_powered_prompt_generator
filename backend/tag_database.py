"""In-memory tag database with exact, alias, and fuzzy matching."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process


@dataclass
class TagEntry:
    tag: str
    category: int
    count: int
    aliases: list[str]


class TagDatabase:
    def __init__(self, json_path: str):
        self.tags: dict[str, TagEntry] = {}
        self.alias_map: dict[str, str] = {}
        self.tag_names: list[str] = []
        self.max_count: int = 1
        self._load(json_path)

    def _load(self, json_path: str):
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Tag database not found: {json_path}")

        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        for item in raw:
            tag = item["tag"]
            entry = TagEntry(
                tag=tag,
                category=item["category"],
                count=item["count"],
                aliases=item.get("aliases", []),
            )
            self.tags[tag] = entry
            self.tag_names.append(tag)

            # Build alias map
            for alias in entry.aliases:
                normalized = self._normalize(alias)
                if normalized and normalized not in self.alias_map:
                    self.alias_map[normalized] = tag

        if self.tags:
            self.max_count = max(e.count for e in self.tags.values())

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower().replace(" ", "_").replace("-", "_")

    def exact_match(self, query: str) -> Optional["TagEntry"]:
        normalized = self._normalize(query)
        return self.tags.get(normalized)

    def alias_match(self, query: str) -> Optional["TagEntry"]:
        normalized = self._normalize(query)
        canonical = self.alias_map.get(normalized)
        if canonical:
            return self.tags.get(canonical)
        return None

    def fuzzy_match(self, query: str, threshold: float = 80, limit: int = 5) -> list[tuple[TagEntry, float]]:
        normalized = self._normalize(query)
        results = process.extract(
            normalized,
            self.tag_names,
            scorer=fuzz.ratio,
            limit=limit,
            score_cutoff=threshold,
        )
        matches = []
        for tag_name, score, _ in results:
            entry = self.tags.get(tag_name)
            if entry:
                matches.append((entry, score / 100.0))
        return matches

    def search_prefix(self, query: str, limit: int = 10) -> list[TagEntry]:
        normalized = self._normalize(query)
        results = []
        for name in self.tag_names:
            if name.startswith(normalized):
                results.append(self.tags[name])
                if len(results) >= limit:
                    break
        return results

    def normalized_popularity(self, count: int) -> float:
        if self.max_count <= 1:
            return 0.0
        return math.log10(max(count, 1)) / math.log10(self.max_count)

    @property
    def total_tags(self) -> int:
        return len(self.tags)
