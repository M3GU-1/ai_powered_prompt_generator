"""
One-time script: Merge danbooru CSVs, compute embeddings, and build FAISS index.

Usage:
    python scripts/build_embeddings.py

This will create:
    - data/merged_tags.json   (merged tag database)
    - data/faiss_index/       (FAISS vector index)
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_csv(filepath: str) -> list[dict]:
    """Load a danbooru tag CSV file."""
    tags = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aliases = [a.strip() for a in row["alias"].split(",") if a.strip()] if row.get("alias") else []
            tags.append({
                "tag": row["tag"].strip(),
                "category": int(row["category"]),
                "count": int(row["count"]),
                "aliases": aliases,
            })
    return tags


def merge_tags(danbooru_tags: list[dict], anima_tags: list[dict]) -> list[dict]:
    """Merge two tag lists, deduplicating and combining aliases."""
    tag_map: dict[str, dict] = {}

    # Load anima_danbooru as base (larger dataset)
    for t in anima_tags:
        tag_map[t["tag"]] = {
            "tag": t["tag"],
            "category": t["category"],
            "count": t["count"],
            "aliases": list(set(t["aliases"])),
            "source": "anima",
        }

    # Merge danbooru_tags
    for t in danbooru_tags:
        if t["tag"] in tag_map:
            existing = tag_map[t["tag"]]
            existing["count"] = max(existing["count"], t["count"])
            # Merge aliases (union)
            combined = set(existing["aliases"]) | set(t["aliases"])
            existing["aliases"] = list(combined)
            existing["source"] = "both"
        else:
            tag_map[t["tag"]] = {
                "tag": t["tag"],
                "category": t["category"],
                "count": t["count"],
                "aliases": list(set(t["aliases"])),
                "source": "danbooru_only",
            }

    merged = sorted(tag_map.values(), key=lambda x: x["count"], reverse=True)
    return merged


def select_tags_for_embedding(merged: list[dict]) -> list[dict]:
    """Select which tags to embed in FAISS index."""
    selected = []
    for t in merged:
        cat = t["category"]
        # General tags (cat 0): all
        if cat == 0:
            selected.append(t)
        # Copyright (cat 3) and Character (cat 4): count >= 100
        elif cat in (3, 4) and t["count"] >= 100:
            selected.append(t)
        # Meta tags (cat 5): count >= 1000
        elif cat == 5 and t["count"] >= 1000:
            selected.append(t)
        # Artist tags (cat 1): skip (exact match only)
    return selected


def _is_english_alias(alias: str) -> bool:
    """Check if an alias is primarily English/ASCII."""
    return all(ord(c) < 128 for c in alias)


def build_embedding_text(tag: dict) -> str:
    """Create text representation for embedding a tag.
    Only includes English aliases to avoid multilingual noise in the embedding."""
    name = tag["tag"].replace("_", " ")
    if tag["aliases"]:
        english_aliases = [a.replace("_", " ") for a in tag["aliases"] if _is_english_alias(a)]
        if english_aliases:
            alias_str = ", ".join(english_aliases[:5])
            return f"{name}, {alias_str}"
    return name


def build_faiss_index(tags_to_embed: list[dict]):
    """Compute embeddings and build FAISS index."""
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        print("Error: Required packages not installed. Run:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    print(f"\nLoading embedding model (all-MiniLM-L6-v2)...")
    print("(First run will download ~80MB model)")
    embeddings_model = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )

    texts = []
    metadatas = []
    for t in tags_to_embed:
        texts.append(build_embedding_text(t))
        metadatas.append({
            "tag": t["tag"],
            "category": t["category"],
            "count": t["count"],
        })

    total = len(texts)
    print(f"\nComputing embeddings for {total} tags...")
    print("This may take 10-20 minutes on CPU.\n")

    # Process in batches for progress reporting
    BATCH_SIZE = 500
    all_embeddings = []
    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        batch_embeddings = embeddings_model.embed_documents(batch)
        all_embeddings.extend(batch_embeddings)

        done = min(i + BATCH_SIZE, total)
        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"  [{done:>6}/{total}] {done/total*100:.1f}%  |  {rate:.0f} tags/s  |  ETA: {eta:.0f}s")

    print(f"\nBuilding FAISS index...")
    # Build FAISS from precomputed embeddings
    text_embedding_pairs = list(zip(texts, all_embeddings))
    vector_store = FAISS.from_embeddings(
        text_embedding_pairs,
        embeddings_model,
        metadatas=metadatas,
    )

    index_path = str(DATA_DIR / "faiss_index")
    vector_store.save_local(index_path)
    print(f"FAISS index saved to {index_path}/")

    return vector_store


def main():
    print("=" * 60)
    print("  SD Prompt Tag Generator - Embedding Builder")
    print("=" * 60)

    # Load CSVs
    danbooru_path = PROJECT_ROOT / "danbooru_tags.csv"
    anima_path = PROJECT_ROOT / "anima_danbooru.csv"

    if not danbooru_path.exists() or not anima_path.exists():
        print(f"Error: CSV files not found in {PROJECT_ROOT}")
        print("Expected: danbooru_tags.csv, anima_danbooru.csv")
        sys.exit(1)

    print(f"\nLoading danbooru_tags.csv...")
    danbooru_tags = load_csv(str(danbooru_path))
    print(f"  Loaded {len(danbooru_tags)} tags")

    print(f"Loading anima_danbooru.csv...")
    anima_tags = load_csv(str(anima_path))
    print(f"  Loaded {len(anima_tags)} tags")

    # Merge
    print(f"\nMerging tags...")
    merged = merge_tags(danbooru_tags, anima_tags)
    print(f"  Total unique tags: {len(merged)}")

    # Save merged database
    DATA_DIR.mkdir(exist_ok=True)
    merged_path = DATA_DIR / "merged_tags.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"  Saved to {merged_path}")

    # Select tags for embedding
    tags_to_embed = select_tags_for_embedding(merged)
    cats = {}
    for t in tags_to_embed:
        cats[t["category"]] = cats.get(t["category"], 0) + 1
    print(f"\nTags selected for embedding: {len(tags_to_embed)}")
    cat_names = {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "meta"}
    for cat, count in sorted(cats.items()):
        print(f"  Category {cat} ({cat_names.get(cat, 'unknown')}): {count}")

    # Build FAISS index
    build_faiss_index(tags_to_embed)

    elapsed_total = time.time()
    print(f"\n{'=' * 60}")
    print(f"  Build complete!")
    print(f"  - merged_tags.json: {len(merged)} tags")
    print(f"  - faiss_index: {len(tags_to_embed)} vectors")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
