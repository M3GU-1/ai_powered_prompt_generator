"""
One-time script: Build FAISS indexes for each tag source.

Usage:
    python scripts/build_embeddings.py              # Build all 3 sources
    python scripts/build_embeddings.py --source danbooru   # Build danbooru only
    python scripts/build_embeddings.py --source anima      # Build anima only
    python scripts/build_embeddings.py --source merged     # Build merged only

This will create:
    - data/danbooru/tags.json + faiss_index/
    - data/anima/tags.json + faiss_index/
    - data/merged/tags.json + faiss_index/
    - data/merged_tags.json (legacy compatibility)
    - data/faiss_index/ (legacy compatibility)
"""

import argparse
import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

VALID_SOURCES = ("danbooru", "anima", "merged", "all")


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


def select_tags_for_embedding(tags: list[dict]) -> list[dict]:
    """Select which tags to embed in FAISS index."""
    selected = []
    for t in tags:
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


def save_tags_json(tags: list[dict], path: Path):
    """Save tag list as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tags, f, ensure_ascii=False)
    print(f"  Saved {len(tags)} tags to {path}")


def load_embedding_model():
    """Load embedding model once for reuse across builds."""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        print("Error: Required packages not installed. Run:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    print(f"\nLoading embedding model (all-MiniLM-L6-v2)...")
    print("(First run will download ~80MB model)")
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )


def build_faiss_index(tags_to_embed: list[dict], index_path: str, embeddings_model):
    """Compute embeddings and build FAISS index at the given path."""
    from langchain_community.vectorstores import FAISS

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
    print(f"  Computing embeddings for {total} tags...")

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
        print(f"    [{done:>6}/{total}] {done/total*100:.1f}%  |  {rate:.0f} tags/s  |  ETA: {eta:.0f}s")

    print(f"  Building FAISS index...")
    text_embedding_pairs = list(zip(texts, all_embeddings))
    vector_store = FAISS.from_embeddings(
        text_embedding_pairs,
        embeddings_model,
        metadatas=metadatas,
    )

    os.makedirs(index_path, exist_ok=True)
    vector_store.save_local(index_path)
    print(f"  FAISS index saved to {index_path}/")

    return vector_store


def build_source_set(tags: list[dict], output_dir: Path, label: str, embeddings_model):
    """Build tags.json and FAISS index for a single source."""
    print(f"\n{'─' * 50}")
    print(f"  Building: {label}")
    print(f"{'─' * 50}")

    # Save tags.json
    save_tags_json(tags, output_dir / "tags.json")

    # Select and embed
    tags_to_embed = select_tags_for_embedding(tags)
    cats = {}
    for t in tags_to_embed:
        cats[t["category"]] = cats.get(t["category"], 0) + 1

    cat_names = {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "meta"}
    print(f"  Tags for embedding: {len(tags_to_embed)}")
    for cat, count in sorted(cats.items()):
        print(f"    Category {cat} ({cat_names.get(cat, 'unknown')}): {count}")

    # Build FAISS index
    index_path = str(output_dir / "faiss_index")
    build_faiss_index(tags_to_embed, index_path, embeddings_model)

    return len(tags), len(tags_to_embed)


def main():
    parser = argparse.ArgumentParser(description="Build FAISS indexes for SD Prompt Tag Generator")
    parser.add_argument(
        "--source",
        choices=VALID_SOURCES,
        default="all",
        help="Which source to build (default: all)",
    )
    args = parser.parse_args()

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

    # Load embedding model once
    embeddings_model = load_embedding_model()

    DATA_DIR.mkdir(exist_ok=True)
    build_targets = args.source
    results = {}
    start_total = time.time()

    # Build danbooru-only
    if build_targets in ("danbooru", "all"):
        # Add source field for standalone danbooru tags
        danbooru_with_source = []
        for t in danbooru_tags:
            danbooru_with_source.append({**t, "source": "danbooru_only"})
        danbooru_sorted = sorted(danbooru_with_source, key=lambda x: x["count"], reverse=True)
        tag_count, vec_count = build_source_set(
            danbooru_sorted, DATA_DIR / "danbooru", "Danbooru Only", embeddings_model,
        )
        results["danbooru"] = (tag_count, vec_count)

    # Build anima-only
    if build_targets in ("anima", "all"):
        anima_with_source = []
        for t in anima_tags:
            anima_with_source.append({**t, "source": "anima"})
        anima_sorted = sorted(anima_with_source, key=lambda x: x["count"], reverse=True)
        tag_count, vec_count = build_source_set(
            anima_sorted, DATA_DIR / "anima", "Anima Only", embeddings_model,
        )
        results["anima"] = (tag_count, vec_count)

    # Build merged
    if build_targets in ("merged", "all"):
        print(f"\nMerging tags...")
        merged = merge_tags(danbooru_tags, anima_tags)
        print(f"  Total unique tags: {len(merged)}")

        tag_count, vec_count = build_source_set(
            merged, DATA_DIR / "merged", "Merged (Both)", embeddings_model,
        )
        results["merged"] = (tag_count, vec_count)

        # Legacy compatibility: copy merged outputs to old paths
        legacy_tags = DATA_DIR / "merged_tags.json"
        legacy_index = DATA_DIR / "faiss_index"
        shutil.copy2(DATA_DIR / "merged" / "tags.json", legacy_tags)
        if legacy_index.exists():
            shutil.rmtree(legacy_index)
        shutil.copytree(DATA_DIR / "merged" / "faiss_index", legacy_index)
        print(f"\n  Legacy files updated: {legacy_tags}, {legacy_index}/")

    elapsed = time.time() - start_total
    print(f"\n{'=' * 60}")
    print(f"  Build complete! ({elapsed:.1f}s)")
    for source, (tc, vc) in results.items():
        print(f"  - {source}: {tc} tags, {vc} vectors")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
