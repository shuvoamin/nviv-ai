#!/bin/bash

# 1. Try to find and activate any existing virtual environment
if [ -d "/home/site/wwwroot/antenv" ]; then
    source /home/site/wwwroot/antenv/bin/activate
    echo "Activated Azure antenv"
elif [ -d "/home/site/wwwroot/venv" ]; then
    source /home/site/wwwroot/venv/bin/activate
    echo "Activated local venv"
fi

# 2. Check if uvicorn is available. If not, install it and the requirements.
# This is a fallback in case the Azure build system (Oryx) skipped installation.
if ! python -m uvicorn --version > /dev/null 2>&1; then
    echo "Uvicorn not found. Attempting to install dependencies..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
fi

# 3. Run the application
echo "Starting Nviv Chatbot..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend/src
python -m uvicorn backend.src.api:app --host 0.0.0.0 --port ${PORT:-8000}
