#!/bin/bash
# Activate the virtual environment provided by Azure Oryx
if [ -d "/home/site/wwwroot/antenv" ]; then
    source /home/site/wwwroot/antenv/bin/activate
    echo "Activated virtual environment 'antenv'"
fi

# Run the application
python -m uvicorn backend.src.api:app --host 0.0.0.0 --port ${PORT:-8000}
