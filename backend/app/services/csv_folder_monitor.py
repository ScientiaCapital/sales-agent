"""
CSV Folder Monitoring Service

Watches the inbox folder for new CSV files and automatically processes them.

Usage:
    # Start monitoring in background
    python -m app.services.csv_folder_monitor

    # Or integrate into main app
    from app.services.csv_folder_monitor import CSVFolderMonitor

    monitor = CSVFolderMonitor(db)
    await monitor.start()  # Runs indefinitely
"""

import asyncio
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.models.database import SessionLocal
from app.services.csv_manager import CSVManager
from app.api.csv_import import process_csv_import
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CSVFolderMonitor:
    """
    Monitors CSV inbox folder and automatically processes new files.

    Features:
    - Watches inbox folder every 30 seconds
    - Tracks processed files to avoid duplicates
    - Automatically triggers CSV import pipeline
    - Logs all activity for audit trail
    """

    def __init__(
        self,
        inbox_path: str = None,
        poll_interval: int = 30,  # seconds
        db = None
    ):
        """
        Initialize folder monitor.

        Args:
            inbox_path: Path to inbox folder (default: backend/data/csv/inbox/)
            poll_interval: How often to check folder in seconds (default: 30)
            db: Database session (optional, will create if not provided)
        """
        if inbox_path:
            self.inbox_path = Path(inbox_path)
        else:
            # Default: backend/data/csv/inbox/
            self.inbox_path = Path(__file__).parent.parent.parent / "data" / "csv" / "inbox"

        self.poll_interval = poll_interval
        self.db = db
        self.processed_files: Set[str] = set()  # Track processed files
        self.running = False

        logger.info(f"CSV Folder Monitor initialized: watching {self.inbox_path}")

    async def start(self):
        """
        Start monitoring inbox folder (runs indefinitely).

        Call this in a background task or separate process.
        """
        self.running = True
        logger.info(f"Starting CSV folder monitor (poll interval: {self.poll_interval}s)")

        while self.running:
            try:
                await self._check_inbox()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in folder monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)  # Continue despite errors

    def stop(self):
        """Stop monitoring."""
        self.running = False
        logger.info("CSV folder monitor stopped")

    async def _check_inbox(self):
        """
        Check inbox folder for new CSV files and process them.
        """
        # Ensure inbox exists
        if not self.inbox_path.exists():
            logger.warning(f"Inbox folder does not exist: {self.inbox_path}")
            self.inbox_path.mkdir(parents=True, exist_ok=True)
            return

        # Find all CSV files in inbox
        csv_files = list(self.inbox_path.glob("*.csv"))

        if not csv_files:
            return  # No files to process

        logger.info(f"Found {len(csv_files)} CSV file(s) in inbox")

        for csv_file in csv_files:
            # Skip if already processed
            if csv_file.name in self.processed_files:
                continue

            # Skip temporary/system files
            if csv_file.name.startswith(".") or csv_file.name.startswith("~"):
                continue

            logger.info(f"New CSV detected: {csv_file.name}")

            try:
                await self._process_csv_file(csv_file)
                # Mark as processed
                self.processed_files.add(csv_file.name)
            except Exception as e:
                logger.error(f"Failed to process {csv_file.name}: {e}", exc_info=True)
                # Don't mark as processed - will retry next poll

    async def _process_csv_file(self, csv_file_path: Path):
        """
        Process a single CSV file.

        Args:
            csv_file_path: Path to CSV file in inbox
        """
        logger.info(f"Processing CSV file: {csv_file_path.name}")

        # Create database session if not provided
        if not self.db:
            db = SessionLocal()
        else:
            db = self.db

        try:
            # Read file content
            with open(csv_file_path, 'rb') as f:
                file_content = f.read()

            # Initialize CSV manager
            csv_manager = CSVManager(db)

            # Upload and validate CSV (this moves file to inbox with timestamp)
            import_record = await csv_manager.upload_csv(
                file_content=file_content,
                filename=csv_file_path.name,
                max_size_mb=10.0
            )

            logger.info(
                f"CSV uploaded successfully: import_id={import_record.id}, "
                f"filename={import_record.filename}, "
                f"rows={import_record.total_rows}"
            )

            # Delete original file from inbox (already moved to processing)
            if csv_file_path.exists():
                csv_file_path.unlink()
                logger.info(f"Removed original file from inbox: {csv_file_path.name}")

            # Start background processing
            logger.info(f"Starting background processing for import_id={import_record.id}")
            asyncio.create_task(process_csv_import(import_record.id, db))

        except Exception as e:
            logger.error(f"Failed to process CSV {csv_file_path.name}: {e}", exc_info=True)
            raise

        finally:
            # Close database session if we created it
            if not self.db:
                db.close()


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

async def main():
    """
    Main entrypoint for running folder monitor standalone.

    Usage:
        python -m app.services.csv_folder_monitor
    """
    logger.info("=" * 70)
    logger.info("CSV Folder Monitor Service")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Drop CSV files in: backend/data/csv/inbox/")
    logger.info("Files will be automatically processed every 30 seconds")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    monitor = CSVFolderMonitor()

    try:
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("\nStopping folder monitor...")
        monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
