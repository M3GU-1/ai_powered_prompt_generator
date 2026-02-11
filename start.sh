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

# Install dependencies
echo "[1/3] Checking dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || {
    echo "[WARN] Some packages may have failed. Try: pip3 install -r requirements.txt"
}

# Check if FAISS index exists
if [ ! -f "data/faiss_index/index.faiss" ]; then
    echo ""
    echo "[2/3] Building tag embeddings (first-time setup)..."
    echo "       This may take 10-20 minutes. Please wait."
    echo ""
    python3 scripts/build_embeddings.py
else
    echo "[2/3] Tag embeddings already built. Skipping."
fi

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
