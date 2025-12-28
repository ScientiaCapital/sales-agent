#!/bin/bash
# Run sample lead test with proper environment

cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/pipeline-testing/backend

# Source virtualenv
source /Users/tmkipper/Desktop/tk_projects/sales-agent/venv/bin/activate

# Load .env file
set -a
source /Users/tmkipper/Desktop/tk_projects/sales-agent/.env
set +a

# Run test
python test_sample_leads.py
