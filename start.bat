@echo off
title StreamHub - Streaming Proxy Server
color 0A
setlocal enabledelayedexpansion

:RESTART
cls
echo ============================================================
echo   StreamHub - Anime ^| Series ^| Movies
echo ============================================================
echo.
echo   Starting server...
echo   Press Ctrl+C to stop
echo ============================================================
echo.

cd /d "%~dp0"

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo   [ERROR] Python not found. Please install Python 3.x
    pause
    exit /b 1
)

REM ---- Install waitress if missing ----
python -c "import waitress" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Installing waitress for stable performance...
    pip install waitress -q
    echo   [INFO] waitress installed.
    echo.
)

REM ---- Run server ----
python server.py 2>&1
set EXIT_CODE=%errorlevel%

REM ---- If user pressed Ctrl+C (code 0) or killed manually, exit cleanly ----
if %EXIT_CODE% == 0 (
    echo.
    echo   Server stopped manually. Goodbye.
    timeout /t 2 /nobreak >nul
    exit /b 0
)

REM ---- Otherwise restart automatically ----
color 0E
echo.
echo ============================================================
echo   [!] Server exited unexpectedly (code: %EXIT_CODE%)
echo   [!] Restarting in 5 seconds...  Press Ctrl+C to cancel.
echo ============================================================
timeout /t 5 /nobreak >nul
color 0A
goto RESTART
