@echo off
title TheDilution Control Deck (myCobot 280 Pi)
echo ===================================================
echo     Starting THE DILUTION Control Deck
echo     Autonomous Auto-Discovery Engine Active
echo ===================================================
echo.
echo Dashboard URL:       http://localhost:8000
echo Auto-Discovery:      UDP Port 8888 + Local Subnet Scanner
echo.
echo Opening browser in 2 seconds...
start "" "http://localhost:8000"
echo Starting FastAPI Web Server...
python -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
