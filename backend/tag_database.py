"""In-memory tag database with exact, alias, and fuzzy matching."""

import json
import math
import re
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
        self._norm_map: dict[str, str] = {}  # normalized name → original tag name
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

            # Build normalized → original mapping for exact match
            norm = self._normalize(tag)
            if norm not in self._norm_map or entry.count > self.tags[self._norm_map[norm]].count:
                self._norm_map[norm] = tag

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

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split tag name into tokens on underscores and hyphens."""
        return [t for t in re.split(r"[_\-]", text.lower()) if t]

    @staticmethod
    def _token_fuzzy_score(query: str, target: str) -> float:
        """Score based on bidirectional token-level fuzzy matching.

        Handles cases where the query is a fuzzy subset of the target
        (e.g. heart_pupils → heart-shaped_pupils) or vice versa.
        """
        q_tokens = TagDatabase._tokenize(query)
        t_tokens = TagDatabase._tokenize(target)
        if not q_tokens or not t_tokens:
            return 0.0

        match_threshold = 75

        # Query → Target: how well each query token matches a target token
        q_scores = [max(fuzz.ratio(qt, tt) for tt in t_tokens)
                     for qt in q_tokens]
        q_matched = sum(1 for s in q_scores if s >= match_threshold)

        # Target → Query: how well each target token is covered by a query token
        t_scores = [max(fuzz.ratio(qt, tt) for qt in q_tokens)
                     for tt in t_tokens]
        t_matched = sum(1 for s in t_scores if s >= match_threshold)

        # Bidirectional coverage: fraction of all tokens that found a match
        coverage = (q_matched + t_matched) / (len(q_tokens) + len(t_tokens))
        if coverage < 0.7:
            return 0.0

        all_matched = [s for s in q_scores + t_scores if s >= match_threshold]
        if not all_matched:
            return 0.0
        avg = sum(all_matched) / len(all_matched)

        return avg * (0.5 + 0.5 * coverage)

    def exact_match(self, query: str) -> Optional["TagEntry"]:
        normalized = self._normalize(query)
        original = self._norm_map.get(normalized)
        if original:
            return self.tags.get(original)
        return None

    def alias_match(self, query: str) -> Optional["TagEntry"]:
        normalized = self._normalize(query)
        canonical = self.alias_map.get(normalized)
        if canonical:
            return self.tags.get(canonical)
        return None

    def fuzzy_match(self, query: str, threshold: float = 80, limit: int = 5) -> list[tuple[TagEntry, float]]:
        normalized = self._normalize(query)

        # Phase 1: Wide-net candidates with lower threshold using fuzz.ratio
        internal_limit = max(limit * 10, 50)
        candidates = process.extract(
            normalized,
            self.tag_names,
            scorer=fuzz.ratio,
            limit=internal_limit,
            score_cutoff=threshold * 0.7,
        )

        # Phase 2: Re-score with token-level matching and take the best
        matches = []
        for tag_name, ratio_score, _ in candidates:
            token_score = self._token_fuzzy_score(normalized, tag_name)
            best_score = max(ratio_score, token_score)
            if best_score >= threshold:
                entry = self.tags.get(tag_name)
                if entry:
                    matches.append((entry, best_score / 100.0))

        # Sort by score descending and return top results
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    def search_prefix(self, query: str, limit: int = 10) -> list[TagEntry]:
        normalized = self._normalize(query)
        results = []
        for norm, original in self._norm_map.items():
            if norm.startswith(normalized):
                results.append(self.tags[original])
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
