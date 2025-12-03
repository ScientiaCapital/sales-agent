#!/bin/bash
# Start Celery Worker + Beat for autonomous agent scheduling
#
# Usage:
#   ./start_celery.sh        # Start both worker and beat
#   ./start_celery.sh stop   # Stop all celery processes
#
# Scheduled Tasks:
#   - Lead Scout: Every 30 minutes (10 leads per run)
#   - Morning Report: 9 AM EST (14:00 UTC) with email/SMS/call drafts
#   - Close CRM Sync: Every 2 hours
#   - Apollo Sync: Daily at 2 AM
#   - LinkedIn Sync: Daily at 3 AM

cd "$(dirname "$0")"
source ../venv/bin/activate

if [ "$1" == "stop" ]; then
    echo "🛑 Stopping Celery processes..."
    pkill -f "celery.*worker" 2>/dev/null
    pkill -f "celery.*beat" 2>/dev/null
    rm -f /tmp/celery_worker.pid /tmp/celery_beat.pid
    echo "✅ Celery stopped"
    exit 0
fi

echo "🚀 Starting Celery Worker..."
celery -A app.celery_app worker --loglevel=info &
echo $! > /tmp/celery_worker.pid
sleep 2

echo "📅 Starting Celery Beat (scheduler)..."
celery -A app.celery_app beat --loglevel=info &
echo $! > /tmp/celery_beat.pid
sleep 2

echo ""
echo "✅ Celery is running!"
echo ""
echo "📊 Scheduled Tasks:"
echo "   • Lead Scout: Every 30 min (scouts 10 leads)"
echo "   • Morning Report: 9 AM EST (email/SMS/call drafts)"
echo "   • Close CRM Sync: Every 2 hours"
echo ""
echo "🔍 Monitor with: tail -f /tmp/celery_worker.log"
echo "🛑 Stop with: ./start_celery.sh stop"
echo ""
echo "💡 TIP: Keep your Mac awake for overnight runs, or deploy to a server."
