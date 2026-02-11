"""Multi-strategy tag matching pipeline: exact → alias → fuzzy → vector."""

from backend.models import TagCandidate
from backend.tag_database import TagDatabase
from backend.vector_search import VectorSearch
from backend.config_loader import MatchingConfig


class TagMatcher:
    def __init__(self, tag_db: TagDatabase, vector_search: VectorSearch, config: MatchingConfig):
        self.tag_db = tag_db
        self.vector_search = vector_search
        self.config = config

    def match_single_tag(self, llm_tag: str) -> list[TagCandidate]:
        """Run the full 4-stage pipeline for one LLM-generated tag."""
        llm_tag_stripped = llm_tag.strip()

        # Stage 1: Exact match
        exact = self.tag_db.exact_match(llm_tag_stripped)
        if exact:
            return [TagCandidate(
                tag=exact.tag,
                category=exact.category,
                count=exact.count,
                match_method="exact",
                similarity_score=1.0,
                llm_original=llm_tag_stripped,
            )]

        # Stage 2: Alias match
        alias = self.tag_db.alias_match(llm_tag_stripped)
        if alias:
            return [TagCandidate(
                tag=alias.tag,
                category=alias.category,
                count=alias.count,
                match_method="alias",
                similarity_score=1.0,
                llm_original=llm_tag_stripped,
            )]

        # Stage 3: Fuzzy match
        fuzzy_results = self.tag_db.fuzzy_match(
            llm_tag_stripped,
            threshold=80,
            limit=self.config.max_results_per_tag,
        )

        # Stage 4: Vector similarity search
        vector_results = self.vector_search.search(
            llm_tag_stripped,
            k=self.config.vector_search_k,
        )

        # Merge and rank results
        candidates = self._merge_and_rank(llm_tag_stripped, fuzzy_results, vector_results)
        return candidates[:self.config.max_results_per_tag]

    def _merge_and_rank(
        self,
        llm_tag: str,
        fuzzy_results: list,
        vector_results: list[dict],
    ) -> list[TagCandidate]:
        """Merge fuzzy and vector results, deduplicate, and rank."""
        seen: dict[str, TagCandidate] = {}

        # Add fuzzy results
        for entry, score in fuzzy_results:
            if entry.tag not in seen:
                seen[entry.tag] = TagCandidate(
                    tag=entry.tag,
                    category=entry.category,
                    count=entry.count,
                    match_method="fuzzy",
                    similarity_score=score,
                    llm_original=llm_tag,
                )

        # Add vector results
        for vr in vector_results:
            if vr["score"] < self.config.min_similarity_score:
                continue
            tag = vr["tag"]
            if tag in seen:
                # Keep higher score
                if vr["score"] > seen[tag].similarity_score:
                    seen[tag].similarity_score = vr["score"]
                    seen[tag].match_method = "vector"
            else:
                seen[tag] = TagCandidate(
                    tag=tag,
                    category=vr["category"],
                    count=vr["count"],
                    match_method="vector",
                    similarity_score=vr["score"],
                    llm_original=llm_tag,
                )

        # Rank by weighted score
        candidates = list(seen.values())
        weight = self.config.count_weight
        for c in candidates:
            pop = self.tag_db.normalized_popularity(c.count)
            c._rank_score = c.similarity_score * (1 - weight) + pop * weight

        candidates.sort(key=lambda c: c._rank_score, reverse=True)
        return candidates

    def match_tags(self, llm_tags: list[str]) -> list[TagCandidate]:
        """Run pipeline for all LLM-generated tags. Returns best match per tag."""
        all_results = []
        seen_tags = set()

        for llm_tag in llm_tags:
            candidates = self.match_single_tag(llm_tag)
            if candidates:
                # Take the best match that hasn't been seen
                for c in candidates:
                    if c.tag not in seen_tags:
                        all_results.append(c)
                        seen_tags.add(c.tag)
                        break

        return all_results

    def match_tags_with_alternatives(self, llm_tags: list[str]) -> list[TagCandidate]:
        """Run pipeline and return all candidates (including alternatives)."""
        all_results = []
        seen_tags = set()

        for llm_tag in llm_tags:
            candidates = self.match_single_tag(llm_tag)
            for c in candidates:
                if c.tag not in seen_tags:
                    all_results.append(c)
                    seen_tags.add(c.tag)

        return all_results
