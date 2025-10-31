"""
Smart Data Merger for CRM Contacts

Intelligently merges duplicate contact data using rules-based logic:
- Most complete data wins (non-null fields preferred)
- Most recent data wins for timestamp conflicts
- Enrichment data (JSON) is merged (no overwrite)
- Audit trail tracks all merges with before/after snapshots

Usage:
    ```python
    from app.services.crm.data_merger import DataMerger, MergeStrategy
    from app.models.crm import CRMContact

    merger = DataMerger(strategy=MergeStrategy.MOST_RECENT)

    # Merge two contacts
    result = merger.merge_contacts(
        existing=existing_contact,
        incoming=new_contact_data
    )

    print(f"Merged contact: {result.merged_contact.email}")
    print(f"Changes: {result.changes}")
    ```
"""

import logging
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.models.crm import CRMContact
from app.services.crm.base import Contact
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Enums ==========

class MergeStrategy(str, Enum):
    """Strategy for resolving conflicts during merge"""
    MOST_RECENT = "most_recent"  # Use most recently updated data
    MOST_COMPLETE = "most_complete"  # Use most complete data (non-null fields)
    PREFER_EXISTING = "prefer_existing"  # Keep existing data unless null
    PREFER_INCOMING = "prefer_incoming"  # Use incoming data unless null


class ChangeType(str, Enum):
    """Type of change made during merge"""
    ADDED = "added"  # Field was null, now has value
    UPDATED = "updated"  # Field value changed
    MERGED = "merged"  # JSON fields merged
    UNCHANGED = "unchanged"  # Field stayed the same


# ========== Data Models ==========

@dataclass
class FieldChange:
    """Details of a single field change"""
    field_name: str
    old_value: Any
    new_value: Any
    change_type: ChangeType
    reason: str  # Why this change was made


@dataclass
class MergeResult:
    """Result of merging two contacts"""
    merged_contact: CRMContact
    changes: List[FieldChange]
    merge_strategy: MergeStrategy
    merged_at: datetime

    def has_changes(self) -> bool:
        """Check if any fields changed"""
        return any(c.change_type != ChangeType.UNCHANGED for c in self.changes)

    def get_summary(self) -> str:
        """Get human-readable summary of changes"""
        if not self.has_changes():
            return "No changes made"

        change_counts = {}
        for change in self.changes:
            change_counts[change.change_type.value] = change_counts.get(change.change_type.value, 0) + 1

        parts = []
        for change_type, count in change_counts.items():
            if change_type != "unchanged":
                parts.append(f"{count} {change_type}")

        return ", ".join(parts)


# ========== Data Merger ==========

class DataMerger:
    """
    Smart data merger for CRM contacts.

    Merges duplicate contact data using configurable strategies while
    preserving the most complete and accurate information.
    """

    # Fields that should be merged (not overwritten)
    JSON_MERGE_FIELDS = ["enrichment_data", "external_ids"]

    # Fields to track in merge audit
    TRACKED_FIELDS = [
        "email", "first_name", "last_name", "company", "title",
        "phone", "linkedin_url", "enrichment_data", "external_ids"
    ]

    def __init__(self, strategy: MergeStrategy = MergeStrategy.MOST_COMPLETE):
        """
        Initialize data merger.

        Args:
            strategy: Default merge strategy for conflict resolution
        """
        self.strategy = strategy

    def merge_contacts(
        self,
        existing: CRMContact,
        incoming: Contact,
        strategy: Optional[MergeStrategy] = None
    ) -> MergeResult:
        """
        Merge incoming contact data into existing contact.

        Args:
            existing: Existing contact in database
            incoming: Incoming contact data (from enrichment/import)
            strategy: Override default merge strategy (optional)

        Returns:
            MergeResult with merged contact and change details
        """
        merge_strategy = strategy or self.strategy
        changes: List[FieldChange] = []
        merged_at = datetime.utcnow()

        logger.info(
            f"Merging contacts: existing={existing.email}, "
            f"incoming={incoming.email}, strategy={merge_strategy.value}"
        )

        # Simple field merges
        simple_fields = [
            ("email", incoming.email),
            ("first_name", incoming.first_name),
            ("last_name", incoming.last_name),
            ("company", incoming.company),
            ("title", incoming.title),
            ("phone", incoming.phone),
            ("linkedin_url", incoming.linkedin_url),
        ]

        for field_name, incoming_value in simple_fields:
            existing_value = getattr(existing, field_name)
            new_value, change = self._merge_field(
                field_name=field_name,
                existing_value=existing_value,
                incoming_value=incoming_value,
                strategy=merge_strategy,
                existing_updated_at=existing.updated_at,
                incoming_updated_at=incoming.updated_at
            )

            if change:
                changes.append(change)
                setattr(existing, field_name, new_value)

        # Merge enrichment_data (JSON field)
        if incoming.enrichment_data:
            enrichment_change = self._merge_json_field(
                field_name="enrichment_data",
                existing_json=existing.enrichment_data or {},
                incoming_json=incoming.enrichment_data
            )
            if enrichment_change:
                changes.append(enrichment_change)
                existing.enrichment_data = enrichment_change.new_value

        # Merge external_ids (JSON field)
        if incoming.external_ids:
            external_ids_change = self._merge_json_field(
                field_name="external_ids",
                existing_json=existing.external_ids or {},
                incoming_json=incoming.external_ids
            )
            if external_ids_change:
                changes.append(external_ids_change)
                existing.external_ids = external_ids_change.new_value

        # Update metadata
        if changes:
            existing.updated_at = merged_at
            existing.last_synced_at = merged_at

        logger.info(f"Merge complete: {len(changes)} changes made")

        return MergeResult(
            merged_contact=existing,
            changes=changes,
            merge_strategy=merge_strategy,
            merged_at=merged_at
        )

    def _merge_field(
        self,
        field_name: str,
        existing_value: Any,
        incoming_value: Any,
        strategy: MergeStrategy,
        existing_updated_at: Optional[datetime],
        incoming_updated_at: Optional[datetime]
    ) -> tuple[Any, Optional[FieldChange]]:
        """
        Merge a single field using the specified strategy.

        Returns:
            (new_value, change_details) tuple
        """
        # Both null - no change
        if existing_value is None and incoming_value is None:
            return existing_value, FieldChange(
                field_name=field_name,
                old_value=None,
                new_value=None,
                change_type=ChangeType.UNCHANGED,
                reason="Both values are null"
            )

        # Existing null, incoming has value - always take incoming
        if existing_value is None and incoming_value is not None:
            return incoming_value, FieldChange(
                field_name=field_name,
                old_value=None,
                new_value=incoming_value,
                change_type=ChangeType.ADDED,
                reason="Added new value (existing was null)"
            )

        # Incoming null, existing has value - keep existing
        if incoming_value is None and existing_value is not None:
            return existing_value, FieldChange(
                field_name=field_name,
                old_value=existing_value,
                new_value=existing_value,
                change_type=ChangeType.UNCHANGED,
                reason="Kept existing value (incoming was null)"
            )

        # Both have values - apply strategy
        if existing_value == incoming_value:
            return existing_value, FieldChange(
                field_name=field_name,
                old_value=existing_value,
                new_value=existing_value,
                change_type=ChangeType.UNCHANGED,
                reason="Values are identical"
            )

        # Conflict resolution based on strategy
        if strategy == MergeStrategy.MOST_RECENT:
            # Use timestamp to determine which is newer
            if incoming_updated_at and existing_updated_at:
                if incoming_updated_at > existing_updated_at:
                    return incoming_value, FieldChange(
                        field_name=field_name,
                        old_value=existing_value,
                        new_value=incoming_value,
                        change_type=ChangeType.UPDATED,
                        reason=f"Incoming value is more recent ({incoming_updated_at})"
                    )
                else:
                    return existing_value, FieldChange(
                        field_name=field_name,
                        old_value=existing_value,
                        new_value=existing_value,
                        change_type=ChangeType.UNCHANGED,
                        reason=f"Existing value is more recent ({existing_updated_at})"
                    )
            # Fallback to most complete if no timestamps
            return self._most_complete_value(field_name, existing_value, incoming_value)

        elif strategy == MergeStrategy.MOST_COMPLETE:
            return self._most_complete_value(field_name, existing_value, incoming_value)

        elif strategy == MergeStrategy.PREFER_EXISTING:
            return existing_value, FieldChange(
                field_name=field_name,
                old_value=existing_value,
                new_value=existing_value,
                change_type=ChangeType.UNCHANGED,
                reason="PREFER_EXISTING strategy - kept existing value"
            )

        elif strategy == MergeStrategy.PREFER_INCOMING:
            return incoming_value, FieldChange(
                field_name=field_name,
                old_value=existing_value,
                new_value=incoming_value,
                change_type=ChangeType.UPDATED,
                reason="PREFER_INCOMING strategy - used incoming value"
            )

        # Default: keep existing
        return existing_value, FieldChange(
            field_name=field_name,
            old_value=existing_value,
            new_value=existing_value,
            change_type=ChangeType.UNCHANGED,
            reason="Default behavior - kept existing value"
        )

    def _most_complete_value(
        self,
        field_name: str,
        existing_value: Any,
        incoming_value: Any
    ) -> tuple[Any, FieldChange]:
        """
        Choose the most complete value (longer string, more data).

        Returns:
            (selected_value, change_details) tuple
        """
        # For strings, prefer longer non-empty value
        if isinstance(existing_value, str) and isinstance(incoming_value, str):
            existing_len = len(existing_value.strip())
            incoming_len = len(incoming_value.strip())

            if incoming_len > existing_len:
                return incoming_value, FieldChange(
                    field_name=field_name,
                    old_value=existing_value,
                    new_value=incoming_value,
                    change_type=ChangeType.UPDATED,
                    reason=f"Incoming value is more complete ({incoming_len} vs {existing_len} chars)"
                )
            else:
                return existing_value, FieldChange(
                    field_name=field_name,
                    old_value=existing_value,
                    new_value=existing_value,
                    change_type=ChangeType.UNCHANGED,
                    reason=f"Existing value is more complete ({existing_len} vs {incoming_len} chars)"
                )

        # For non-strings, default to existing
        return existing_value, FieldChange(
            field_name=field_name,
            old_value=existing_value,
            new_value=existing_value,
            change_type=ChangeType.UNCHANGED,
            reason="Non-string values - kept existing"
        )

    def _merge_json_field(
        self,
        field_name: str,
        existing_json: Dict[str, Any],
        incoming_json: Dict[str, Any]
    ) -> Optional[FieldChange]:
        """
        Merge JSON fields (enrichment_data, external_ids) without overwriting.

        Args:
            field_name: Name of JSON field
            existing_json: Existing JSON data
            incoming_json: Incoming JSON data to merge

        Returns:
            FieldChange if data was merged, None otherwise
        """
        if not incoming_json:
            return FieldChange(
                field_name=field_name,
                old_value=existing_json,
                new_value=existing_json,
                change_type=ChangeType.UNCHANGED,
                reason="No incoming JSON data to merge"
            )

        # Deep merge: incoming updates existing, but doesn't remove keys
        merged = {**existing_json, **incoming_json}

        # Check if anything actually changed
        if merged == existing_json:
            return FieldChange(
                field_name=field_name,
                old_value=existing_json,
                new_value=existing_json,
                change_type=ChangeType.UNCHANGED,
                reason="JSON fields are identical"
            )

        return FieldChange(
            field_name=field_name,
            old_value=existing_json,
            new_value=merged,
            change_type=ChangeType.MERGED,
            reason=f"Merged {len(incoming_json)} incoming fields into existing JSON"
        )

    def create_audit_log(self, merge_result: MergeResult) -> Dict[str, Any]:
        """
        Create audit log entry for merge operation.

        Args:
            merge_result: Result of merge operation

        Returns:
            Dict with audit log data
        """
        return {
            "merged_at": merge_result.merged_at.isoformat(),
            "merge_strategy": merge_result.merge_strategy.value,
            "contact_id": merge_result.merged_contact.id,
            "contact_email": merge_result.merged_contact.email,
            "has_changes": merge_result.has_changes(),
            "change_summary": merge_result.get_summary(),
            "changes": [
                {
                    "field": change.field_name,
                    "old_value": str(change.old_value)[:100] if change.old_value else None,
                    "new_value": str(change.new_value)[:100] if change.new_value else None,
                    "change_type": change.change_type.value,
                    "reason": change.reason
                }
                for change in merge_result.changes
                if change.change_type != ChangeType.UNCHANGED
            ]
        }


# ========== Factory Function ==========

def get_data_merger(strategy: MergeStrategy = MergeStrategy.MOST_COMPLETE) -> DataMerger:
    """
    Factory function to create data merger instance.

    Args:
        strategy: Merge strategy to use (default: MOST_COMPLETE)

    Returns:
        Configured DataMerger instance
    """
    return DataMerger(strategy=strategy)
