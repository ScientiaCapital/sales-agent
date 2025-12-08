#!/bin/bash
# Live Agent Monitoring Dashboard
# Run this to watch your agents work in real-time

echo "========================================="
echo "🤖 SALES AGENT TEAM - LIVE MONITORING"
echo "========================================="
echo ""
echo "📊 AGENTS RUNNING:"
echo "  • Lead Scout (every 30 min)"
echo "  • ICP Checker (every 15 min)"
echo "  • Prediction Market (every 5 min)"
echo "  • Sales Intel (hourly)"
echo "  • BDR Outreach (hourly)"
echo "  • Growth Campaigns (10 AM daily)"
echo ""
echo "========================================="
echo ""

# Tail both logs with color coding
tail -f celery_worker.log celery_beat.log | grep --line-buffered -i "enrich\|apollo\|linkedin\|scout\|task\|error"
