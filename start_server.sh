#!/bin/bash
# Start the sales-agent server with all environment variables loaded

cd "$(dirname "$0")"

# Load environment variables from .env file
set -a
source .env
set +a

# Activate virtual environment
source venv/bin/activate

# Start the server
cd backend
exec uvicorn app.main:app --reload --port 8001
