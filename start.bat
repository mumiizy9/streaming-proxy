@echo off
title StreamHub - Streaming Proxy Server
color 0A
echo ============================================================
echo   StreamHub - Anime ^| Series ^| Movies
echo ============================================================
echo.
echo   Starting server...
echo.
cd /d "%~dp0"
python server.py
pause
