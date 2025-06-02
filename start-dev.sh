#!/bin/bash
set -m # Enable Job Control

echo "Starting FastAPI backend (port 8000) with auto-reload..."
cd /app/server/src
# Your main.py is in /app/server/src/main.py and the FastAPI instance is 'app'
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/server/src &

echo "Starting Vite frontend dev server (port 5173)..."
cd /app/client
# npm run dev will use vite.config.js which sets host 0.0.0.0 and port 5173
# The --host flag here ensures Vite listens on all interfaces within the container.
npm run dev

# When the foreground process (npm run dev) exits (e.g., Ctrl+C),
# this script will terminate. Docker will then stop the container,
# which will also stop the background Uvicorn process.