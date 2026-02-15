#!/bin/bash
# Activate the native Azure virtual environment (Oryx)
# This folder is created automatically if SCM_DO_BUILD_DURING_DEPLOYMENT=true
if [ -d "/home/site/wwwroot/antenv" ]; then
    source /home/site/wwwroot/antenv/bin/activate
    echo "Activated Azure native virtual environment 'antenv'"
fi

# Run the application
python -m uvicorn backend.src.api:app --host 0.0.0.0 --port ${PORT:-8000}
