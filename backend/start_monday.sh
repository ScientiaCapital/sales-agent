#!/bin/bash
# Monday 8 AM Launch Script
# Usage: ./start_monday.sh

set -e

cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate

echo "🚀 Starting Sales Agent Platform..."
echo "=================================="

# Create logs directory if not exists
mkdir -p logs

# Start Docker if not running
echo "📦 Starting Docker services..."
docker-compose up -d
sleep 3

# Check services
echo "🔍 Checking services..."
docker-compose ps

# Start FastAPI
echo ""
echo "🌐 Starting FastAPI server..."
nohup python start_server.py > logs/fastapi.log 2>&1 &
echo "   PID: $!"
sleep 2

# Start Celery Worker (default + workflows)
echo "⚙️  Starting Celery Worker (default,workflows)..."
nohup celery -A app.celery_app worker --loglevel=info -Q default,workflows --concurrency=4 > logs/celery_worker.log 2>&1 &
echo "   PID: $!"

# Start Celery Worker (crm_sync)
echo "🔄 Starting Celery Worker (crm_sync)..."
nohup celery -A app.celery_app worker --loglevel=info -Q crm_sync --concurrency=2 > logs/celery_crm.log 2>&1 &
echo "   PID: $!"

# Start Celery Beat
echo "⏰ Starting Celery Beat scheduler..."
nohup celery -A app.celery_app beat --loglevel=info > logs/celery_beat.log 2>&1 &
echo "   PID: $!"

sleep 3

echo ""
echo "=================================="
echo "✅ All services started!"
echo ""
echo "📊 Health check:"
curl -s http://localhost:8001/api/health | python -m json.tool 2>/dev/null || echo "   Waiting for server..."
echo ""
echo "📋 Log files:"
echo "   tail -f logs/fastapi.log"
echo "   tail -f logs/celery_worker.log"
echo "   tail -f logs/celery_crm.log"
echo "   tail -f logs/celery_beat.log"
echo ""
echo "🛑 To stop all: pkill -f 'celery|start_server'"
echo ""
echo "Ready for Claude Code session!"
