#!/usr/bin/env python3
"""
Celery Worker Entry Point

This script launches Celery workers for background task processing.

Usage:
    # Development (single-threaded, easier debugging)
    python celery_worker.py
    
    # Production (multi-process with autoscaling)
    celery -A app.celery_app worker --loglevel=info --concurrency=8 --pool=prefork
    
    # With Flower monitoring
    celery -A app.celery_app flower --port=5555
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


def main():
    """
    Start Celery worker with appropriate configuration
    
    Development settings:
    - Pool: solo (single-threaded for easier debugging)
    - Concurrency: 4 workers
    - Loglevel: info
    
    For production, use CLI with prefork pool:
    celery -A app.celery_app worker --loglevel=info --concurrency=8 --pool=prefork --autoscale=16,4
    """
    logger.info("Starting Celery worker...")
    
    # Verify Redis connection
    try:
        from redis import Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        logger.info(f"Redis connection verified: {redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.error("Make sure Redis is running (docker-compose up -d redis)")
        sys.exit(1)
    
    # Start worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=4",
        "--pool=solo",  # Use solo for development, prefork for production
        "--queues=default,workflows,enrichment",  # Listen to all queues
        "--hostname=worker@sales-agent",
        "--without-gossip",  # Disable gossip protocol for development
        "--without-mingle",  # Disable mingle for faster startup
        "--without-heartbeat",  # Disable heartbeat for development
    ])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)
