@echo off
title Scribble Frontend (Vite)
setlocal
cd /d "%~dp0"
echo ========================================================
echo  Starting Scribble Frontend (Vite + React)
echo  Port: 1420
echo ========================================================
npm run dev
if %ERRORLEVEL% neq 0 (
    echo.
    echo Frontend encountered an error!
    pause
)
