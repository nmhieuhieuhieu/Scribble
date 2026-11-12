@echo off
title Scribble Backend (FastAPI)
setlocal
set "VOICESCRIBE_DATA=%~dp0.voicescribe_data"
cd /d "%~dp0src-python"
echo ========================================================
echo  Starting Scribble Backend (FastAPI)
echo  Port: 8765
echo  Data Directory: %VOICESCRIBE_DATA%
echo ========================================================
python main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Backend encountered an error!
    pause
)
