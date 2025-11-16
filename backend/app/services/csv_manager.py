"""
CSV Manager Service

Handles the complete lifecycle of CSV file imports:
1. Upload and validation
2. State transitions (inbox → processing → completed/failed)
3. Database tracking
4. Cost tracking
5. Archival

Usage:
    from app.services.csv_manager import CSVManager
    from app.models.database import get_db

    db = next(get_db())
    manager = CSVManager(db)

    # Upload CSV
    import_record = await manager.upload_csv(
        file_content=file_bytes,
        filename="leads_2024.csv"
    )

    # Start processing
    await manager.start_processing(import_record.id)

    # Mark as completed
    await manager.complete_processing(
        import_id=import_record.id,
        processed_rows=150,
        failed_rows=0,
        total_cost=0.05
    )
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.security import SecurityValidator
from app.core.exceptions import (
    InvalidInputError,
    InvalidFileFormatError,
    FileSizeExceededError,
    DatabaseError,
)
from app.models.csv_import import CSVImport

logger = logging.getLogger(__name__)


class CSVManager:
    """
    Manages CSV file lifecycle and database tracking.

    Attributes:
        db: SQLAlchemy database session
        base_path: Base directory for CSV files
        inbox_path: Directory for uploaded files
        processing_path: Directory for files being processed
        completed_path: Directory for successfully processed files
        failed_path: Directory for failed files
        archive_path: Directory for archived files
    """

    def __init__(self, db: Session):
        """
        Initialize CSV manager with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

        # Define directory structure
        # Navigate from app/services/ to backend/data/csv/
        self.base_path = Path(__file__).parent.parent.parent / "data" / "csv"
        self.inbox_path = self.base_path / "inbox"
        self.processing_path = self.base_path / "processing"
        self.completed_path = self.base_path / "completed"
        self.failed_path = self.base_path / "failed"
        self.archive_path = self.base_path / "archive"

        # Ensure all directories exist
        for path in [
            self.inbox_path,
            self.processing_path,
            self.completed_path,
            self.failed_path,
            self.archive_path
        ]:
            path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # UPLOAD & VALIDATION
    # ========================================================================

    async def upload_csv(
        self,
        file_content: bytes,
        filename: str,
        max_size_mb: Optional[float] = None
    ) -> CSVImport:
        """
        Upload and validate CSV file, create database record.

        Steps:
        1. Sanitize filename
        2. Save to inbox directory
        3. Validate CSV format and size
        4. Create database record with status='uploaded'

        Args:
            file_content: Raw file bytes
            filename: Original filename
            max_size_mb: Maximum file size in MB (default: 10)

        Returns:
            CSVImport record

        Raises:
            InvalidFileFormatError: If file is not valid CSV
            FileSizeExceededError: If file exceeds size limit
            DatabaseError: If database insert fails
        """
        # Sanitize filename
        safe_filename = SecurityValidator.sanitize_filename(filename)

        # Make filename unique by appending timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name_parts = safe_filename.rsplit(".", 1)
        unique_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"

        # Save to inbox
        inbox_file_path = self.inbox_path / unique_filename

        try:
            with open(inbox_file_path, 'wb') as f:
                f.write(file_content)

            logger.info(f"CSV file saved to inbox: {inbox_file_path}")

            # Validate CSV file
            validation_result = SecurityValidator.validate_csv_file(
                str(inbox_file_path),
                max_size_mb=max_size_mb,
                check_columns=False  # Don't enforce columns yet
            )

            # Create database record
            csv_import = CSVImport(
                filename=unique_filename,
                file_path=str(inbox_file_path),
                status='uploaded',
                total_rows=validation_result['row_count'],
                processed_rows=0,
                failed_rows=0,
                total_cost_usd=0.0
            )

            self.db.add(csv_import)
            self.db.commit()
            self.db.refresh(csv_import)

            logger.info(
                f"CSV import created: ID={csv_import.id}, "
                f"rows={csv_import.total_rows}, "
                f"size={validation_result['file_size_mb']} MB"
            )

            return csv_import

        except (InvalidFileFormatError, FileSizeExceededError) as e:
            # Clean up file if validation failed
            if inbox_file_path.exists():
                inbox_file_path.unlink()
            logger.error(f"CSV validation failed: {e}")
            raise

        except Exception as e:
            # Clean up file if database insert failed
            if inbox_file_path.exists():
                inbox_file_path.unlink()
            logger.error(f"Failed to create CSV import record: {e}")
            raise DatabaseError(
                f"Failed to create import record: {str(e)}",
                context={"filename": unique_filename}
            )

    # ========================================================================
    # STATE TRANSITIONS
    # ========================================================================

    async def start_processing(self, import_id: int) -> CSVImport:
        """
        Move CSV from inbox to processing, update status.

        Args:
            import_id: CSV import record ID

        Returns:
            Updated CSVImport record

        Raises:
            InvalidInputError: If import not found or not in 'uploaded' status
        """
        csv_import = self.db.query(CSVImport).filter(CSVImport.id == import_id).first()

        if not csv_import:
            raise InvalidInputError(
                f"CSV import {import_id} not found",
                context={"import_id": import_id}
            )

        if csv_import.status != 'uploaded':
            raise InvalidInputError(
                f"CSV import {import_id} is not in 'uploaded' status (current: {csv_import.status})",
                context={"import_id": import_id, "status": csv_import.status}
            )

        # Move file from inbox to processing
        old_path = Path(csv_import.file_path)
        new_path = self.processing_path / old_path.name

        try:
            shutil.move(str(old_path), str(new_path))

            # Update database record
            csv_import.file_path = str(new_path)
            csv_import.status = 'processing'
            csv_import.started_processing_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(csv_import)

            logger.info(f"CSV import {import_id} moved to processing")
            return csv_import

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to move CSV to processing: {e}")
            raise DatabaseError(
                f"Failed to start processing: {str(e)}",
                context={"import_id": import_id}
            )

    async def complete_processing(
        self,
        import_id: int,
        processed_rows: int,
        failed_rows: int = 0,
        total_cost: float = 0.0
    ) -> CSVImport:
        """
        Move CSV from processing to completed, update metrics.

        Args:
            import_id: CSV import record ID
            processed_rows: Number of successfully processed rows
            failed_rows: Number of failed rows
            total_cost: Total cost in USD

        Returns:
            Updated CSVImport record

        Raises:
            InvalidInputError: If import not found or not in 'processing' status
        """
        csv_import = self.db.query(CSVImport).filter(CSVImport.id == import_id).first()

        if not csv_import:
            raise InvalidInputError(
                f"CSV import {import_id} not found",
                context={"import_id": import_id}
            )

        if csv_import.status != 'processing':
            raise InvalidInputError(
                f"CSV import {import_id} is not in 'processing' status (current: {csv_import.status})",
                context={"import_id": import_id, "status": csv_import.status}
            )

        # Move file from processing to completed
        old_path = Path(csv_import.file_path)
        new_path = self.completed_path / old_path.name

        try:
            shutil.move(str(old_path), str(new_path))

            # Update database record
            csv_import.file_path = str(new_path)
            csv_import.status = 'completed'
            csv_import.processed_rows = processed_rows
            csv_import.failed_rows = failed_rows
            csv_import.total_cost_usd = total_cost
            csv_import.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(csv_import)

            logger.info(
                f"CSV import {import_id} completed: "
                f"{processed_rows} processed, {failed_rows} failed, "
                f"${total_cost:.4f} cost"
            )
            return csv_import

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to complete CSV processing: {e}")
            raise DatabaseError(
                f"Failed to complete processing: {str(e)}",
                context={"import_id": import_id}
            )

    async def fail_processing(
        self,
        import_id: int,
        error_message: str,
        processed_rows: int = 0,
        failed_rows: int = 0
    ) -> CSVImport:
        """
        Move CSV from processing to failed, record error.

        Args:
            import_id: CSV import record ID
            error_message: Error message describing failure
            processed_rows: Number of rows processed before failure
            failed_rows: Number of failed rows

        Returns:
            Updated CSVImport record

        Raises:
            InvalidInputError: If import not found
        """
        csv_import = self.db.query(CSVImport).filter(CSVImport.id == import_id).first()

        if not csv_import:
            raise InvalidInputError(
                f"CSV import {import_id} not found",
                context={"import_id": import_id}
            )

        # Move file from processing to failed
        old_path = Path(csv_import.file_path)
        new_path = self.failed_path / old_path.name

        try:
            shutil.move(str(old_path), str(new_path))

            # Update database record
            csv_import.file_path = str(new_path)
            csv_import.status = 'failed'
            csv_import.processed_rows = processed_rows
            csv_import.failed_rows = failed_rows
            csv_import.error_message = error_message
            csv_import.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(csv_import)

            logger.error(
                f"CSV import {import_id} failed: {error_message} "
                f"({processed_rows} processed, {failed_rows} failed)"
            )
            return csv_import

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark CSV as failed: {e}")
            raise DatabaseError(
                f"Failed to mark as failed: {str(e)}",
                context={"import_id": import_id}
            )

    # ========================================================================
    # ARCHIVAL
    # ========================================================================

    async def archive_old_imports(self, retention_days: int = 30) -> int:
        """
        Archive CSV imports older than retention period.

        Moves completed/failed files to archive directory and updates status.

        Args:
            retention_days: Number of days to keep files before archiving (default: 30)

        Returns:
            Number of imports archived
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Find old completed/failed imports
        old_imports = self.db.query(CSVImport).filter(
            CSVImport.status.in_(['completed', 'failed']),
            CSVImport.completed_at < cutoff_date,
            CSVImport.archived_at.is_(None)
        ).all()

        archived_count = 0

        for csv_import in old_imports:
            try:
                old_path = Path(csv_import.file_path)
                new_path = self.archive_path / old_path.name

                # Move file to archive
                if old_path.exists():
                    shutil.move(str(old_path), str(new_path))
                    csv_import.file_path = str(new_path)

                # Update status
                csv_import.status = 'archived'
                csv_import.archived_at = datetime.utcnow()

                self.db.commit()
                archived_count += 1

                logger.info(f"Archived CSV import {csv_import.id}")

            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to archive import {csv_import.id}: {e}")

        logger.info(f"Archived {archived_count} CSV imports")
        return archived_count

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_import_by_id(self, import_id: int) -> Optional[CSVImport]:
        """Get CSV import by ID."""
        return self.db.query(CSVImport).filter(CSVImport.id == import_id).first()

    def get_imports_by_status(self, status: str) -> list[CSVImport]:
        """Get all imports with given status."""
        return self.db.query(CSVImport).filter(CSVImport.status == status).all()

    def get_recent_imports(self, limit: int = 10) -> list[CSVImport]:
        """Get most recent imports."""
        return (
            self.db.query(CSVImport)
            .order_by(CSVImport.uploaded_at.desc())
            .limit(limit)
            .all()
        )
