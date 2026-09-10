@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.8 or later and make sure "python" works from a
    echo command prompt, then run this file again.
    pause
    exit /b 1
)

if not exist ".installed" (
    echo Installing required packages, this can take 1-2 minutes...
    python -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Package installation failed. Check your internet connection
        echo and try again.
        pause
        exit /b 1
    )
    echo done> .installed
)

echo Starting server...
python launcher.py

endlocal
