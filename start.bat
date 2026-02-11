@echo off
title SD Prompt Tag Generator

echo ============================================================
echo   SD Prompt Tag Generator - Startup
echo ============================================================
echo.

REM ── Detect Python (skip Windows Store alias) ─────────────────
set "PYTHON_CMD="

REM 1) Try py launcher (most reliable on Windows)
py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_found
)

REM 2) Try python command (exclude WindowsApps Store alias)
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PYTHON_CMD=python"
        goto :python_found
    )
)

REM Python not found
echo.
echo ============================================================
echo   [ERROR] Python is not installed!
echo ============================================================
echo.
echo   Please install Python:
echo.
echo   1. Download from https://www.python.org/downloads/
echo      IMPORTANT: Check "Add Python to PATH" during install!
echo.
echo   2. If already installed, make sure Python is in your PATH.
echo.
echo   3. On Windows 10/11, go to:
echo      Settings ^> Apps ^> App execution aliases
echo      and turn OFF "python.exe (App Installer)"
echo.
echo ============================================================
echo.
pause
exit /b 1

:python_found
REM Show detected Python version
for /f "delims=" %%V in ('%PYTHON_CMD% --version 2^>^&1') do echo [OK] %%V detected

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
%PYTHON_CMD% -m pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo [WARN] Some packages may have failed to install.
    echo        Try running: %PYTHON_CMD% -m pip install -r requirements.txt
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
    %PYTHON_CMD% scripts/build_embeddings.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to build embeddings.
        echo.
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

REM Open browser
start "" http://127.0.0.1:8000

REM Start server
%PYTHON_CMD% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

REM ── After server stops ─────────────────────────────────────────
echo.
if errorlevel 1 (
    echo ============================================================
    echo   [ERROR] Server stopped with an error.
    echo   Check the log messages above.
    echo ============================================================
) else (
    echo   Server stopped.
)
echo.
pause
