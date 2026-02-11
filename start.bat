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

REM ── Step 1: Auto-extract tag index archives ────────────────────
set "ARCHIVES_FOUND=0"
for %%F in (tag-index-*.tar.gz) do (
    if exist "%%F" (
        set "ARCHIVES_FOUND=1"
        echo [*] Found tag index archive: %%F
        echo     Extracting to data\ ...
        if not exist "data" mkdir data
        tar -xzf "%%F" -C data\
        if not errorlevel 1 (
            echo     Done. Removing archive.
            del /q "%%F"
        ) else (
            echo     [WARN] Extraction failed for %%F
        )
    )
)

if "%ARCHIVES_FOUND%"=="1" echo.

REM ── Step 2: Auto-create config.yaml ────────────────────────────
if not exist "config.yaml" (
    if exist "config.example.yaml" (
        copy /y config.example.yaml config.yaml >nul
        echo [*] Created config.yaml from config.example.yaml
        echo.
    )
)

REM ── Step 3: Install dependencies ───────────────────────────────
echo [1/3] Checking dependencies...
pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo [WARN] Some packages may have failed to install.
    echo        Try running: pip install -r requirements.txt
)

REM ── Step 4: Check / build FAISS index ──────────────────────────
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

REM ── Step 5: Start server ───────────────────────────────────────
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
