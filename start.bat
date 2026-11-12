@echo off
setlocal
echo ========================================================
echo   Khoi dong Scribble AI Meeting Assistant (BE + FE)
echo ========================================================
echo.
echo [1/2] Dang khoi dong Backend tren port 8765...
start "Scribble Backend" "%~dp0run-backend.bat"

echo [2/2] Dang cho Backend san sang (3 giay)...
timeout /t 3 /nobreak >nul

echo Dang khoi dong Frontend tren port 1420...
start "Scribble Frontend" "%~dp0run-frontend.bat"

echo.
echo ========================================================
echo  Khoi dong hoan tat!
echo  Truy cap trinh duyet: http://localhost:1420
echo ========================================================
echo.
