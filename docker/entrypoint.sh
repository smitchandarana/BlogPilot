#!/bin/sh
# Start Xvfb on a fixed display and launch uvicorn
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
export DISPLAY=:99
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
