#!/bin/bash
# Run the SENS web interface

echo "Starting SENS Web Interface..."
echo "Access the UI at http://localhost:8000"
echo ""

# Activate poetry environment and run
poetry run uvicorn sens.web.app:web_app --reload --host 0.0.0.0 --port 8000
