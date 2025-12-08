"""
Conflict Resolver
=================

Enterprise conflict resolution strategies for bidirectional sync.
Supports multiple strategies and custom resolution logic.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Built-in conflict resolution strategies"""
    NEWER_WINS = "newer_wins"           # Most recently updated wins
    CLOSE_WINS = "close_wins"           # Close CRM always wins
    SUPABASE_WINS = "supabase_wins"     # Supabase always wins
    MERGE_PREFER_CLOSE = "merge_close"  # Merge, prefer Close on conflicts
    MERGE_PREFER_SUPABASE = "merge_sb"  # Merge, prefer Supabase on conflicts
    FIELD_BY_FIELD = "field_by_field"   # Per-field strategy
    MANUAL = "manual"                    # Require manual resolution


@dataclass
class ConflictRecord:
    """Record of a detected conflict"""
    conflict_id: str
    entity_type: str
    close_id: str
    supabase_id: str
    close_data: Dict[str, Any]
    supabase_data: Dict[str, Any]
    conflicting_fields: List[str]
    close_updated_at: datetime
    supabase_updated_at: datetime
    resolved: bool = False
    resolution: Optional[Dict] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None  # "auto", "manual", user_id


class ConflictResolver:
    """
    Conflict resolver with multiple resolution strategies.
    
    Strategies:
    - NEWER_WINS: Record with more recent update wins
    - CLOSE_WINS: Close CRM data always wins
    - SUPABASE_WINS: Supabase data always wins  
    - MERGE_PREFER_CLOSE: Merge non-conflicting, prefer Close
    - MERGE_PREFER_SUPABASE: Merge non-conflicting, prefer Supabase
    - FIELD_BY_FIELD: Different strategy per field
    - MANUAL: Flag for manual resolution
    """
    
    def __init__(
        self,
        default_strategy: ConflictStrategy = ConflictStrategy.NEWER_WINS,
        field_strategies: Optional[Dict[str, ConflictStrategy]] = None
    ):
        self.default_strategy = default_strategy
        self.field_strategies = field_strategies or {}
        
        # Unresolved conflicts queue
        self.pending_conflicts: List[ConflictRecord] = []
    
    async def resolve(
        self,
        entity_type: str,
        close_data: Dict[str, Any],
        supabase_data: Dict[str, Any],
        field_registry: "FieldRegistry",
        strategy: Optional[ConflictStrategy] = None
    ) -> Dict[str, Any]:
        """
        Resolve a conflict between Close and Supabase data.
        
        Args:
            entity_type: Entity type (lead, contact, activity)
            close_data: Data from Close CRM
            supabase_data: Data from Supabase
            field_registry: Field registry for transforms
            strategy: Override resolution strategy
            
        Returns:
            Dict with resolved data for both systems:
            {
                "close_payload": {...},   # Data to send to Close
                "supabase_row": {...},    # Data to save to Supabase
                "conflicts_resolved": [...],  # List of resolved field conflicts
            }
        """
        strategy = strategy or self.default_strategy
        
        # Detect which fields conflict
        conflicting_fields = self._detect_conflicting_fields(
            entity_type, close_data, supabase_data, field_registry
        )
        
        if not conflicting_fields:
            # No actual conflicts - just merge
            return self._merge_data(
                entity_type, close_data, supabase_data, field_registry
            )
        
        logger.info(f"Resolving {len(conflicting_fields)} conflicts using {strategy.value}")
        
        if strategy == ConflictStrategy.NEWER_WINS:
            return await self._resolve_newer_wins(
                entity_type, close_data, supabase_data, field_registry
            )
        elif strategy == ConflictStrategy.CLOSE_WINS:
            return self._resolve_close_wins(
                entity_type, close_data, supabase_data, field_registry
            )
        elif strategy == ConflictStrategy.SUPABASE_WINS:
            return self._resolve_supabase_wins(
                entity_type, close_data, supabase_data, field_registry
            )
        elif strategy == ConflictStrategy.MERGE_PREFER_CLOSE:
            return self._resolve_merge(
                entity_type, close_data, supabase_data, field_registry,
                prefer="close"
            )
        elif strategy == ConflictStrategy.MERGE_PREFER_SUPABASE:
            return self._resolve_merge(
                entity_type, close_data, supabase_data, field_registry,
                prefer="supabase"
            )
        elif strategy == ConflictStrategy.FIELD_BY_FIELD:
            return await self._resolve_field_by_field(
                entity_type, close_data, supabase_data, field_registry,
                conflicting_fields
            )
        elif strategy == ConflictStrategy.MANUAL:
            return self._flag_for_manual_resolution(
                entity_type, close_data, supabase_data, conflicting_fields
            )
        
        raise ValueError(f"Unknown strategy: {strategy}")
    
    def _detect_conflicting_fields(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry"
    ) -> List[str]:
        """Detect which fields have conflicting values"""
        conflicts = []
        
        entity_mapping = field_registry.get_entity_mapping(entity_type)
        if not entity_mapping:
            return conflicts
        
        for field_mapping in entity_mapping.fields:
            # Only check bidirectional fields for conflicts
            if field_mapping.direction.value != "bidirectional":
                continue
            
            # Get values from both sources
            close_value = field_registry._extract_nested_value(
                close_data, field_mapping.close_field
            )
            supabase_value = supabase_data.get(field_mapping.supabase_column)
            
            # Normalize for comparison
            close_normalized = self._normalize_for_comparison(close_value)
            supabase_normalized = self._normalize_for_comparison(supabase_value)
            
            # Check if different (and neither is null)
            if close_normalized != supabase_normalized:
                if close_normalized is not None and supabase_normalized is not None:
                    conflicts.append(field_mapping.supabase_column)
        
        return conflicts
    
    @staticmethod
    def _normalize_for_comparison(value: Any) -> Any:
        """Normalize value for comparison"""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            return sorted([str(v).lower() for v in value])
        return value
    
    def _merge_data(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry"
    ) -> Dict[str, Any]:
        """Merge data from both sources (no conflicts)"""
        # Transform Close data to Supabase format
        supabase_row = field_registry.transform_close_to_supabase(
            entity_type, close_data
        )
        
        # Update with any Supabase-specific fields
        for key, value in supabase_data.items():
            if key not in supabase_row and value is not None:
                supabase_row[key] = value
        
        # Transform back to Close format
        close_payload = field_registry.transform_supabase_to_close(
            entity_type, supabase_row, close_data
        )
        
        return {
            "close_payload": close_payload,
            "supabase_row": supabase_row,
            "conflicts_resolved": []
        }
    
    async def _resolve_newer_wins(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry"
    ) -> Dict[str, Any]:
        """Newer timestamp wins"""
        # Get timestamps
        close_updated = close_data.get("date_updated")
        supabase_updated = supabase_data.get("updated_at")
        
        if close_updated:
            close_updated = datetime.fromisoformat(
                close_updated.replace('Z', '+00:00')
            )
        if supabase_updated:
            if isinstance(supabase_updated, str):
                supabase_updated = datetime.fromisoformat(
                    supabase_updated.replace('Z', '+00:00')
                )
        
        # Determine winner
        if close_updated and supabase_updated:
            if close_updated >= supabase_updated:
                return self._resolve_close_wins(
                    entity_type, close_data, supabase_data, field_registry
                )
            else:
                return self._resolve_supabase_wins(
                    entity_type, close_data, supabase_data, field_registry
                )
        elif close_updated:
            return self._resolve_close_wins(
                entity_type, close_data, supabase_data, field_registry
            )
        else:
            return self._resolve_supabase_wins(
                entity_type, close_data, supabase_data, field_registry
            )
    
    def _resolve_close_wins(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry"
    ) -> Dict[str, Any]:
        """Close CRM data wins all conflicts"""
        supabase_row = field_registry.transform_close_to_supabase(
            entity_type, close_data
        )
        
        # Preserve Supabase-only fields
        entity_mapping = field_registry.get_entity_mapping(entity_type)
        if entity_mapping:
            supabase_columns = [f.supabase_column for f in entity_mapping.fields]
            for key, value in supabase_data.items():
                if key not in supabase_columns and value is not None:
                    supabase_row[key] = value
        
        return {
            "close_payload": {},  # No changes needed to Close
            "supabase_row": supabase_row,
            "conflicts_resolved": ["close_wins"]
        }
    
    def _resolve_supabase_wins(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry"
    ) -> Dict[str, Any]:
        """Supabase data wins all conflicts"""
        close_payload = field_registry.transform_supabase_to_close(
            entity_type, supabase_data, close_data
        )
        
        return {
            "close_payload": close_payload,
            "supabase_row": {},  # No changes needed to Supabase
            "conflicts_resolved": ["supabase_wins"]
        }
    
    def _resolve_merge(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry",
        prefer: str = "close"
    ) -> Dict[str, Any]:
        """Merge non-conflicting fields, prefer specified source for conflicts"""
        # Start with merged base
        result = self._merge_data(entity_type, close_data, supabase_data, field_registry)
        
        # Detect conflicts and apply preference
        conflicts = self._detect_conflicting_fields(
            entity_type, close_data, supabase_data, field_registry
        )
        
        entity_mapping = field_registry.get_entity_mapping(entity_type)
        if entity_mapping:
            for field in entity_mapping.fields:
                if field.supabase_column in conflicts:
                    if prefer == "close":
                        # Use Close value
                        close_value = field_registry._extract_nested_value(
                            close_data, field.close_field
                        )
                        if field.transform_to_supabase:
                            close_value = field.transform_to_supabase(close_value)
                        result["supabase_row"][field.supabase_column] = close_value
                    else:
                        # Use Supabase value
                        supabase_value = supabase_data.get(field.supabase_column)
                        if field.transform_to_close:
                            close_value = field.transform_to_close(supabase_value)
                            field_registry._set_nested_value(
                                result["close_payload"],
                                field.close_field,
                                close_value
                            )
        
        result["conflicts_resolved"] = conflicts
        return result
    
    async def _resolve_field_by_field(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        field_registry: "FieldRegistry",
        conflicting_fields: List[str]
    ) -> Dict[str, Any]:
        """Apply per-field resolution strategies"""
        result = self._merge_data(entity_type, close_data, supabase_data, field_registry)
        
        entity_mapping = field_registry.get_entity_mapping(entity_type)
        if not entity_mapping:
            return result
        
        for field in entity_mapping.fields:
            if field.supabase_column not in conflicting_fields:
                continue
            
            # Get field-specific strategy
            strategy = self.field_strategies.get(
                field.supabase_column,
                ConflictStrategy.NEWER_WINS
            )
            
            # Get values
            close_value = field_registry._extract_nested_value(
                close_data, field.close_field
            )
            supabase_value = supabase_data.get(field.supabase_column)
            
            # Resolve based on strategy
            if strategy == ConflictStrategy.CLOSE_WINS:
                if field.transform_to_supabase:
                    close_value = field.transform_to_supabase(close_value)
                result["supabase_row"][field.supabase_column] = close_value
            elif strategy == ConflictStrategy.SUPABASE_WINS:
                if field.transform_to_close:
                    supabase_value = field.transform_to_close(supabase_value)
                field_registry._set_nested_value(
                    result["close_payload"],
                    field.close_field,
                    supabase_value
                )
            # NEWER_WINS requires timestamp comparison at record level
        
        result["conflicts_resolved"] = conflicting_fields
        return result
    
    def _flag_for_manual_resolution(
        self,
        entity_type: str,
        close_data: Dict,
        supabase_data: Dict,
        conflicting_fields: List[str]
    ) -> Dict[str, Any]:
        """Flag conflict for manual resolution"""
        import uuid
        
        conflict = ConflictRecord(
            conflict_id=str(uuid.uuid4()),
            entity_type=entity_type,
            close_id=close_data.get("id", "unknown"),
            supabase_id=supabase_data.get("company_id", "unknown"),
            close_data=close_data,
            supabase_data=supabase_data,
            conflicting_fields=conflicting_fields,
            close_updated_at=datetime.fromisoformat(
                close_data.get("date_updated", datetime.utcnow().isoformat()).replace('Z', '+00:00')
            ),
            supabase_updated_at=supabase_data.get("updated_at", datetime.utcnow())
        )
        
        self.pending_conflicts.append(conflict)
        logger.warning(f"Conflict {conflict.conflict_id} flagged for manual resolution")
        
        return {
            "close_payload": {},
            "supabase_row": {},
            "conflicts_resolved": [],
            "requires_manual": True,
            "conflict_id": conflict.conflict_id
        }
    
    def get_pending_conflicts(self) -> List[ConflictRecord]:
        """Get all pending manual conflicts"""
        return [c for c in self.pending_conflicts if not c.resolved]
    
    async def resolve_manual_conflict(
        self,
        conflict_id: str,
        resolution: Dict[str, Any],
        resolved_by: str = "manual"
    ) -> bool:
        """
        Resolve a manual conflict.
        
        Args:
            conflict_id: Conflict ID
            resolution: Resolved data with close_payload and supabase_row
            resolved_by: Who resolved it
            
        Returns:
            True if resolved successfully
        """
        for conflict in self.pending_conflicts:
            if conflict.conflict_id == conflict_id:
                conflict.resolved = True
                conflict.resolution = resolution
                conflict.resolved_at = datetime.utcnow()
                conflict.resolved_by = resolved_by
                logger.info(f"Conflict {conflict_id} resolved by {resolved_by}")
                return True
        
        return False
