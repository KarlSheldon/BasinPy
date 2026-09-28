@echo off
setlocal
cd /d "%~dp0"
python BetaBasic.py %*
if errorlevel 1 (
    echo.
    echo BetaBasic exited with error code %errorlevel%.
    pause
)
