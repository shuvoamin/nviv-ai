#!/bin/bash
# Direct path to the module since we are in the root
python3 -m uvicorn backend.src.api:app --host 0.0.0.0 --port ${PORT:-8000}
