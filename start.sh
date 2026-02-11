#!/bin/bash
set -e

echo "============================================================"
echo "  SD Prompt Tag Generator - Startup"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# ── Step 1: Auto-extract tag index archives ──────────────────────
ARCHIVES_FOUND=0
for archive in tag-index-*.tar.gz; do
    [ -f "$archive" ] || continue
    ARCHIVES_FOUND=1
    SOURCE_NAME=$(echo "$archive" | sed 's/tag-index-\(.*\)\.tar\.gz/\1/')
    echo "[*] Found tag index archive: $archive"
    echo "    Extracting to data/${SOURCE_NAME}/ ..."
    mkdir -p data
    tar -xzf "$archive" -C data/
    echo "    Done. Removing archive."
    rm -f "$archive"
done

if [ "$ARCHIVES_FOUND" -eq 1 ]; then
    echo ""
fi

# ── Step 2: Auto-create config.yaml ──────────────────────────────
if [ ! -f "config.yaml" ]; then
    if [ -f "config.example.yaml" ]; then
        cp config.example.yaml config.yaml
        echo "[*] Created config.yaml from config.example.yaml"
        echo ""
    fi
fi

# ── Step 3: Install dependencies ─────────────────────────────────
echo "[1/3] Checking dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || {
    echo "[WARN] Some packages may have failed. Try: pip3 install -r requirements.txt"
}

# ── Step 4: Check / build FAISS index ────────────────────────────
if [ -f "data/merged/faiss_index/index.faiss" ] || \
   [ -f "data/danbooru/faiss_index/index.faiss" ] || \
   [ -f "data/anima/faiss_index/index.faiss" ] || \
   [ -f "data/faiss_index/index.faiss" ]; then
    echo "[2/3] Tag embeddings found. Skipping build."
else
    echo ""
    echo "[2/3] Building tag embeddings (first-time setup)..."
    echo "       This may take 10-20 minutes. Please wait."
    echo ""
    python3 scripts/build_embeddings.py
fi

# ── Step 5: Start server ─────────────────────────────────────────
echo ""
echo "[3/3] Starting server..."
echo ""
echo "============================================================"
echo "  Server running at: http://127.0.0.1:8000"
echo "  Press Ctrl+C to stop"
echo "============================================================"
echo ""

# Open browser
if command -v open &> /dev/null; then
    open http://127.0.0.1:8000 &
elif command -v xdg-open &> /dev/null; then
    xdg-open http://127.0.0.1:8000 &
fi

# Start server
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
