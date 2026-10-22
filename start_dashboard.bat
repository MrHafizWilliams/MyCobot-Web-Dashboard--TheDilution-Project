@echo off
title TheDilution Control Deck (myCobot 280 Pi)
echo ===================================================
echo     THE DILUTION - Smart Cleanroom Controller
echo     CAT403 Autonomous Robotic Control Deck
echo ===================================================
echo.

:: 1. Verify Python Installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Auto-Check and Install Dependencies if missing
echo [*] Checking dependencies (FastAPI, uvicorn, requests, pydantic)...
python -c "import fastapi, uvicorn, requests, pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Required packages not found. Installing from requirements.txt...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Please check your internet connection.
        echo.
        pause
        exit /b 1
    )
)

echo [*] Dependencies verified.
echo.
echo ===================================================
echo  DASHBOARD ACCESS URLS:
echo  - This Device (Localhost):  http://localhost:8000
echo.
echo  REMOTE ACCESS (From Phone / Tablet / Another PC):
echo  - Step 1: Make sure both devices are on the same Wi-Fi or Tailscale.
echo  - Step 2: Open browser on the other device and visit:
echo            http://^<THIS_PC_IP^>:8000
echo.
echo  [CRITICAL] DO NOT CLOSE THIS BLACK TERMINAL WINDOW!
echo  Closing this window will immediately shut down the dashboard.
echo ===================================================
echo.

:: 3. Open local browser
start "" "http://localhost:8000"

:: 4. Start Server on 0.0.0.0 (all network interfaces)
echo [*] Starting FastAPI Web Server on port 8000...
python -m uvicorn server:app --host 0.0.0.0 --port 8000
echo.
echo Server stopped.
pause
