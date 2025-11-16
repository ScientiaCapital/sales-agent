#!/usr/bin/env python3
"""
CSV Retention Cleanup Script

Automatically archives CSV imports older than the retention period (default: 30 days).

This script should be run periodically via cron job:
    # Run daily at 2 AM
    0 2 * * * cd /path/to/sales-agent/backend && python scripts/cleanup_old_csvs.py

Or manually:
    python backend/scripts/cleanup_old_csvs.py --retention-days 30

Features:
- Archives completed/failed CSV imports older than retention period
- Moves files from completed/failed directories to archive
- Updates database status to 'archived'
- Logs all actions for audit trail
- Safe to run multiple times (idempotent)
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import SessionLocal
from app.services.csv_manager import CSVManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "csv_cleanup.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """
    Main cleanup function.

    Parses arguments and runs archival process.
    """
    parser = argparse.ArgumentParser(
        description="Archive old CSV imports based on retention policy"
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=30,
        help='Number of days to keep CSV files before archiving (default: 30)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be archived without making changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 70)
    logger.info("CSV Retention Cleanup Script")
    logger.info("=" * 70)
    logger.info(f"Retention period: {args.retention_days} days")
    logger.info(f"Dry run: {args.dry_run}")

    # Create database session
    db = SessionLocal()

    try:
        # Initialize CSV manager
        csv_manager = CSVManager(db)

        if args.dry_run:
            # TODO: Implement dry-run mode
            logger.warning("Dry-run mode not yet implemented. Skipping archival.")
            return

        # Run archival
        import asyncio
        archived_count = asyncio.run(
            csv_manager.archive_old_imports(retention_days=args.retention_days)
        )

        logger.info("=" * 70)
        logger.info(f"Cleanup completed: {archived_count} imports archived")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
