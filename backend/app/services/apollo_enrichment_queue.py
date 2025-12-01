"""
Apollo Enrichment Queue - Queue leads for batch enrichment when Apollo credits available

This module tracks leads that need Apollo enrichment (contact discovery from company name).
When Apollo credits are purchased, run `apollo_batch_enrich.py` to process the queue.

Queue Entry Structure:
    - company_name: str (required)
    - company_website: str (optional but preferred)
    - company_phone: str (optional - for phone-based lookup)
    - priority: int (1=high, 2=medium, 3=low)
    - source: str (where lead came from)
    - existing_contacts: list (contacts found by other methods, need email)
    - queued_at: datetime
    - status: pending | processing | completed | failed

Usage:
    # During qualification (when Apollo disabled)
    queue = get_apollo_queue()
    await queue.add_to_queue(
        company_name="ABC Corp",
        company_website="abccorp.com",
        priority=1,  # Hot lead
        source="hunter_incomplete",
        existing_contacts=[{"name": "John Smith", "title": "CEO", "needs_email": True}]
    )

    # When Apollo credits purchased
    python apollo_batch_enrich.py --process-queue
"""
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class QueuePriority(int, Enum):
    """Lead priority for enrichment queue."""
    HIGH = 1      # Hot ATL leads, high qualification score
    MEDIUM = 2    # Warm leads, partial contact info
    LOW = 3       # Cold leads, company name only


class QueueStatus(str, Enum):
    """Status of queue entry."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Already enriched elsewhere


@dataclass
class ApolloQueueEntry:
    """Single entry in the Apollo enrichment queue."""
    company_name: str
    company_website: Optional[str] = None
    company_phone: Optional[str] = None
    priority: int = QueuePriority.MEDIUM
    source: str = "unknown"
    existing_contacts: List[Dict[str, Any]] = field(default_factory=list)
    queued_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = QueueStatus.PENDING
    error_message: Optional[str] = None
    enriched_contacts: List[Dict[str, Any]] = field(default_factory=list)
    processed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApolloQueueEntry":
        return cls(**data)


class ApolloEnrichmentQueue:
    """
    Queue manager for leads awaiting Apollo enrichment.

    Stores queue in JSON file for simplicity (can migrate to DB later).
    """

    def __init__(self, queue_file: Optional[str] = None):
        """Initialize queue with file path."""
        if queue_file is None:
            # Default to data directory
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            queue_file = str(data_dir / "apollo_enrichment_queue.json")

        self.queue_file = queue_file
        self._queue: List[ApolloQueueEntry] = []
        self._load_queue()

    def _load_queue(self) -> None:
        """Load queue from JSON file."""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self._queue = [ApolloQueueEntry.from_dict(entry) for entry in data]
                logger.info(f"Loaded {len(self._queue)} entries from Apollo queue")
            except Exception as e:
                logger.error(f"Failed to load Apollo queue: {e}")
                self._queue = []
        else:
            self._queue = []

    def _save_queue(self) -> None:
        """Save queue to JSON file."""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump([entry.to_dict() for entry in self._queue], f, indent=2)
            logger.debug(f"Saved {len(self._queue)} entries to Apollo queue")
        except Exception as e:
            logger.error(f"Failed to save Apollo queue: {e}")

    async def add_to_queue(
        self,
        company_name: str,
        company_website: Optional[str] = None,
        company_phone: Optional[str] = None,
        priority: int = QueuePriority.MEDIUM,
        source: str = "unknown",
        existing_contacts: Optional[List[Dict]] = None
    ) -> bool:
        """
        Add a lead to the Apollo enrichment queue.

        Args:
            company_name: Company name (required)
            company_website: Company website for domain search
            company_phone: Company phone for phone-based lookup
            priority: 1=high, 2=medium, 3=low
            source: Where this lead came from (e.g., "hunter_incomplete")
            existing_contacts: Contacts found by other methods that need email

        Returns:
            True if added, False if already in queue
        """
        # Check if already in queue
        for entry in self._queue:
            if entry.company_name.lower() == company_name.lower():
                if entry.status == QueueStatus.PENDING:
                    logger.info(f"Company already in queue: {company_name}")
                    return False
                # If previously failed/completed, allow re-queue
                if entry.status in [QueueStatus.FAILED, QueueStatus.COMPLETED]:
                    self._queue.remove(entry)
                    break

        entry = ApolloQueueEntry(
            company_name=company_name,
            company_website=company_website,
            company_phone=company_phone,
            priority=priority,
            source=source,
            existing_contacts=existing_contacts or []
        )

        self._queue.append(entry)
        self._save_queue()

        logger.info(
            f"Added to Apollo queue: {company_name} "
            f"(priority={priority}, contacts_needing_email={len(existing_contacts or [])})"
        )
        return True

    def get_pending_entries(self, limit: Optional[int] = None) -> List[ApolloQueueEntry]:
        """Get pending entries sorted by priority."""
        pending = [e for e in self._queue if e.status == QueueStatus.PENDING]
        pending.sort(key=lambda x: (x.priority, x.queued_at))
        if limit:
            return pending[:limit]
        return pending

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {
            "total": len(self._queue),
            "pending": 0,
            "completed": 0,
            "failed": 0,
            "by_priority": {1: 0, 2: 0, 3: 0},
            "contacts_needing_email": 0
        }

        for entry in self._queue:
            if entry.status == QueueStatus.PENDING:
                stats["pending"] += 1
                stats["by_priority"][entry.priority] = stats["by_priority"].get(entry.priority, 0) + 1
                stats["contacts_needing_email"] += len(entry.existing_contacts)
            elif entry.status == QueueStatus.COMPLETED:
                stats["completed"] += 1
            elif entry.status == QueueStatus.FAILED:
                stats["failed"] += 1

        return stats

    def mark_processing(self, company_name: str) -> bool:
        """Mark entry as processing."""
        for entry in self._queue:
            if entry.company_name.lower() == company_name.lower():
                entry.status = QueueStatus.PROCESSING
                self._save_queue()
                return True
        return False

    def mark_completed(
        self,
        company_name: str,
        enriched_contacts: List[Dict[str, Any]]
    ) -> bool:
        """Mark entry as completed with enriched contacts."""
        for entry in self._queue:
            if entry.company_name.lower() == company_name.lower():
                entry.status = QueueStatus.COMPLETED
                entry.enriched_contacts = enriched_contacts
                entry.processed_at = datetime.utcnow().isoformat()
                self._save_queue()
                logger.info(f"Apollo enrichment completed: {company_name} ({len(enriched_contacts)} contacts)")
                return True
        return False

    def mark_failed(self, company_name: str, error: str) -> bool:
        """Mark entry as failed with error message."""
        for entry in self._queue:
            if entry.company_name.lower() == company_name.lower():
                entry.status = QueueStatus.FAILED
                entry.error_message = error
                entry.processed_at = datetime.utcnow().isoformat()
                self._save_queue()
                logger.warning(f"Apollo enrichment failed: {company_name} - {error}")
                return True
        return False

    def export_for_enrichment(self, output_file: Optional[str] = None) -> str:
        """
        Export pending entries to CSV for manual Apollo enrichment.

        Returns path to exported CSV.
        """
        import csv

        if output_file is None:
            data_dir = Path(self.queue_file).parent
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_file = str(data_dir / f"apollo_enrichment_batch_{timestamp}.csv")

        pending = self.get_pending_entries()

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'company_name', 'company_website', 'company_phone',
                'priority', 'source', 'contacts_needing_email', 'queued_at'
            ])
            writer.writeheader()

            for entry in pending:
                writer.writerow({
                    'company_name': entry.company_name,
                    'company_website': entry.company_website or '',
                    'company_phone': entry.company_phone or '',
                    'priority': entry.priority,
                    'source': entry.source,
                    'contacts_needing_email': len(entry.existing_contacts),
                    'queued_at': entry.queued_at
                })

        logger.info(f"Exported {len(pending)} entries to {output_file}")
        return output_file


# Singleton instance
_queue_instance: Optional[ApolloEnrichmentQueue] = None


def get_apollo_queue() -> ApolloEnrichmentQueue:
    """Get or create Apollo enrichment queue singleton."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = ApolloEnrichmentQueue()
    return _queue_instance


def clear_queue_instance():
    """Clear singleton (for testing)."""
    global _queue_instance
    _queue_instance = None
