"""
CSV Import model for tracking uploaded CSV files and their processing status
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, Index
from sqlalchemy.sql import func
from .database import Base


class CSVImport(Base):
    """
    Tracks CSV file imports and their processing lifecycle.

    Lifecycle states:
    - uploaded: File received in inbox
    - processing: Currently being processed
    - completed: Successfully processed
    - failed: Processing failed
    - archived: Moved to archive after retention period
    """
    __tablename__ = "csv_imports"

    # Table-level indexes
    __table_args__ = (
        Index('idx_csv_imports_status', 'status'),
        Index('idx_csv_imports_uploaded_at', 'uploaded_at'),
    )

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # File Information
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)

    # Processing Status
    status = Column(
        String(20),
        nullable=False,
        default='uploaded'
    )  # uploaded | processing | completed | failed | archived

    # Row Counts
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)

    # Cost Tracking
    total_cost_usd = Column(
        Numeric(precision=10, scale=6),
        nullable=False,
        default=0.0
    )

    # Timestamps
    uploaded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    started_processing_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Error Tracking
    error_message = Column(Text, nullable=True)

    # Archival
    archived_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<CSVImport(id={self.id}, "
            f"filename='{self.filename}', "
            f"status='{self.status}', "
            f"rows={self.processed_rows}/{self.total_rows})>"
        )

    @property
    def is_complete(self) -> bool:
        """Check if import has finished (completed or failed)"""
        return self.status in ['completed', 'failed', 'archived']

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_rows == 0:
            return 0.0
        return (self.processed_rows / self.total_rows) * 100
