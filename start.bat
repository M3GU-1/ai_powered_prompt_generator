@echo off
chcp 65001 >nul 2>&1
title SD Prompt Tag Generator

echo ============================================================
echo   SD Prompt Tag Generator - Startup
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo [1/3] Checking dependencies...
pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo [WARN] Some packages may have failed to install.
    echo        Try running: pip install -r requirements.txt
)

REM Check if any FAISS index exists (new per-source or legacy path)
set "INDEX_FOUND=0"
if exist "data\merged\faiss_index\index.faiss" set "INDEX_FOUND=1"
if exist "data\danbooru\faiss_index\index.faiss" set "INDEX_FOUND=1"
if exist "data\anima\faiss_index\index.faiss" set "INDEX_FOUND=1"
if exist "data\faiss_index\index.faiss" set "INDEX_FOUND=1"

if "%INDEX_FOUND%"=="1" (
    echo [2/3] Tag embeddings found. Skipping build.
) else (
    echo.
    echo [2/3] Building tag embeddings (first-time setup)...
    echo        This may take 10-20 minutes. Please wait.
    echo.
    python scripts/build_embeddings.py
    if errorlevel 1 (
        echo [ERROR] Failed to build embeddings.
        pause
        exit /b 1
    )
)

echo.
echo [3/3] Starting server...
echo.
echo ============================================================
echo   Server running at: http://127.0.0.1:8000
echo   Press Ctrl+C to stop
echo ============================================================
echo.

REM Open browser after a short delay
start "" http://127.0.0.1:8000

REM Start server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
