#!/bin/bash
# Production launcher script for Sales Agent CLI
# 
# Usage:
#   ./scripts/run_agent_cli.sh                    # Interactive mode
#   ./scripts/run_agent_cli.sh --agent qualify    # Direct agent invocation
#   ./scripts/run_agent_cli.sh --trace            # Enable LangSmith tracing

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r backend/requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create one with required environment variables:"
    echo "   CEREBRAS_API_KEY=your_key"
    echo "   ANTHROPIC_API_KEY=your_key"
    echo "   OPENROUTER_API_KEY=your_key"
    echo "   DATABASE_URL=postgresql://..."
    echo "   REDIS_URL=redis://localhost:6379/0"
    exit 1
fi

# Load environment variables
echo "🔧 Loading environment variables..."
export $(cat .env | grep -v '^#' | xargs)

# Check if required services are running
echo "🔍 Checking required services..."

# Check PostgreSQL
if ! pg_isready -h localhost -p 5433 >/dev/null 2>&1; then
    echo "⚠️  PostgreSQL not running on port 5433. Starting with Docker..."
    docker-compose up -d postgres
    sleep 5
fi

# Check Redis
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
    echo "⚠️  Redis not running on port 6379. Starting with Docker..."
    docker-compose up -d redis
    sleep 3
fi

# Check if required Python packages are installed
echo "🔍 Checking Python dependencies..."
python -c "import rich, click" 2>/dev/null || {
    echo "❌ Missing required packages. Installing..."
    pip install -r backend/requirements.txt
}

# Check if agents can be imported
echo "🔍 Checking agent imports..."
python -c "
import sys
sys.path.insert(0, 'backend')
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.langgraph.agents.conversation_agent import ConversationAgent
print('✅ All agents imported successfully')
" || {
    echo "❌ Agent import failed. Please check your backend setup."
    exit 1
}

# Run the CLI
echo "🚀 Starting Sales Agent CLI..."
echo ""

# Pass all arguments to the Python script
python agent_cli.py "$@"
