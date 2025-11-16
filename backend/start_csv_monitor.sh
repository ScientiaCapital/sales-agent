#!/bin/bash
# Start CSV Folder Monitoring Service

echo "=========================================="
echo "CSV Folder Monitor - Starting"
echo "=========================================="
echo ""
echo "Watching: backend/data/csv/inbox/"
echo "Drop CSV files there for automatic processing"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Activate virtual environment
source ../venv/bin/activate

# Run folder monitor
cd "$(dirname "$0")"
python -m app.services.csv_folder_monitor
