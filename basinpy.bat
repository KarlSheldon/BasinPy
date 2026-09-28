@echo off
setlocal
cd /d "%~dp0"
python main.py %*
if errorlevel 1 (
    echo.
    echo BasinPy exited with error code %errorlevel%.
    pause
)
