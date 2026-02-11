@echo off
title SD Prompt Tag Generator

REM ================================================================
REM  Crash-proof wrapper pattern:
REM  Re-launches itself with --run flag via "cmd /c".
REM  Even if the inner logic crashes fatally, control returns here
REM  and the window stays open so the user can read the error.
REM ================================================================
if "%~1"=="--run" goto :run

cmd /c ""%~f0" --run"

echo.
if errorlevel 1 (
    echo ============================================================
    echo   [ERROR] Startup failed. Check the messages above.
    echo   A log has been saved to: startup.log
    echo ============================================================
)
echo.
echo Press any key to close this window...
pause >nul
exit

REM ================================================================
:run
REM ================================================================
setlocal

REM Ensure working directory is the script's own folder
cd /d "%~dp0"

REM Log file for debugging (overwrites each run)
set "LOGFILE=startup.log"
echo ============================================ > "%LOGFILE%"
echo  SD Prompt Tag Generator - Startup Log >> "%LOGFILE%"
echo  %date% %time% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"
echo. >> "%LOGFILE%"

echo ============================================================
echo   SD Prompt Tag Generator - Startup
echo ============================================================
echo.

REM -- Detect Python --
set "PYTHON_CMD="

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_ok
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :python_ok
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto :python_ok
)

echo [ERROR] Python is not installed or not in PATH!
echo [ERROR] Python is not installed or not in PATH! >> "%LOGFILE%"
echo.
echo   Please install Python from https://www.python.org/downloads/
echo   IMPORTANT: Check "Add Python to PATH" during install!
echo.
echo   On Windows 10/11, also check:
echo   Settings ^> Apps ^> App execution aliases
echo   and turn OFF "python.exe (App Installer)"
exit /b 1

:python_ok
REM Show Python version and path for debugging
for /f "delims=" %%V in ('%PYTHON_CMD% --version 2^>^&1') do (
    echo [OK] %%V detected
    echo [OK] %%V >> "%LOGFILE%"
)
for /f "delims=" %%P in ('%PYTHON_CMD% -c "import sys; print(sys.executable)" 2^>^&1') do (
    echo     Path: %%P
    echo     Path: %%P >> "%LOGFILE%"
)
echo.

REM -- Auto-extract tag index archives --
for %%F in (tag-index-*.tar.gz) do (
    if exist "%%F" (
        echo [*] Found tag index archive: %%F
        echo     Extracting to data\ ...
        if not exist "data" mkdir data
        tar -xzf "%%F" -C data\
        if not errorlevel 1 (
            echo     Done. Removing archive.
            del /q "%%F"
        ) else (
            echo     [WARN] Extraction failed for %%F
            echo [WARN] Extraction failed: %%F >> "%LOGFILE%"
        )
        echo.
    )
)

REM -- Auto-create config.yaml --
if not exist "config.yaml" (
    if exist "config.example.yaml" (
        copy /y config.example.yaml config.yaml >nul
        echo [*] Created config.yaml from config.example.yaml
        echo.
    )
)

REM -- Step 1: Install dependencies --
echo [1/3] Checking dependencies...
echo [1/3] Checking dependencies... >> "%LOGFILE%"

REM Check pip is available
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available!
    echo [ERROR] pip is not available! >> "%LOGFILE%"
    echo.
    echo   Attempting to install pip...
    %PYTHON_CMD% -m ensurepip --upgrade 2>> "%LOGFILE%"
    if errorlevel 1 (
        echo   [ERROR] Could not install pip.
        echo          Please reinstall Python with pip enabled.
        echo [ERROR] ensurepip failed >> "%LOGFILE%"
        exit /b 1
    )
)

REM Check requirements.txt exists
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in %cd%
    echo [ERROR] requirements.txt not found >> "%LOGFILE%"
    exit /b 1
)

REM Install dependencies (stderr goes to log file for debugging)
%PYTHON_CMD% -m pip install -r requirements.txt --quiet 2>> "%LOGFILE%"
if errorlevel 1 (
    echo.
    echo [WARN] Some packages failed. Retrying with full output...
    echo [WARN] pip install --quiet failed, retrying >> "%LOGFILE%"
    echo.
    REM Retry with full output visible in console
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo         Check startup.log for details.
        echo         Or try manually: %PYTHON_CMD% -m pip install -r requirements.txt
        echo [ERROR] pip install failed >> "%LOGFILE%"
        exit /b 1
    )
)
echo        Done.

REM -- Step 2: Check / build FAISS index --
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
    echo [2/3] Building embeddings... >> "%LOGFILE%"
    echo.
    %PYTHON_CMD% scripts/build_embeddings.py 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to build embeddings.
        echo [ERROR] build_embeddings failed >> "%LOGFILE%"
        exit /b 1
    )
)

REM -- Step 3: Start server --
echo.
echo [3/3] Starting server...
echo [3/3] Starting server... >> "%LOGFILE%"
echo.
echo ============================================================
echo   Server running at: http://127.0.0.1:8000
echo   Press Ctrl+C to stop
echo ============================================================
echo.

REM Open browser (delayed to give server time to start)
start "" http://127.0.0.1:8000

%PYTHON_CMD% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 2>&1
set "SERVER_EXIT=%errorlevel%"
echo Server exited with code %SERVER_EXIT% >> "%LOGFILE%"

if %SERVER_EXIT% neq 0 (
    echo.
    echo [ERROR] Server stopped with an error (code %SERVER_EXIT%).
    echo         Check the messages above or startup.log for details.
    exit /b 1
)

echo.
echo Server stopped.
exit /b 0
