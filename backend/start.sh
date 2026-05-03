#!/bin/bash
# Move to the script's directory so it can be run from anywhere
cd "$(dirname "$0")"

echo "Starting FastAPI backend server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
