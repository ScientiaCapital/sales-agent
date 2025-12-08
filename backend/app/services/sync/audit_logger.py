"""
Sync Audit Logger
=================

Enterprise audit logging for sync operations with:
- Complete audit trail
- Compliance reporting
- Change tracking
- Anomaly detection
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import hashlib

logger = logging.getLogger(__name__)


class SyncOperation(Enum):
    """Types of sync operations"""
    SYNC_ENTITY = "sync_entity"
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    ROLLBACK = "rollback"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    ERROR = "error"
    SECURITY_EVENT = "security_event"


@dataclass
class AuditEntry:
    """Single audit log entry"""
    entry_id: str
    operation: SyncOperation
    entity_type: str
    direction: str
    close_id: Optional[str] = None
    supabase_id: Optional[str] = None
    user_id: Optional[str] = None
    before_data_hash: Optional[str] = None
    after_data_hash: Optional[str] = None
    changed_fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SyncAuditLogger:
    """
    Enterprise audit logger for sync operations.
    
    Features:
    - Complete audit trail in Supabase
    - Data change hashing for integrity
    - Compliance reporting
    - Anomaly detection
    - Rate tracking
    """
    
    AUDIT_TABLE = "sync_audit_log"
    
    def __init__(
        self,
        supabase_client,
        enable_detailed_logging: bool = True,
        retention_days: int = 90
    ):
        self.supabase = supabase_client
        self.detailed_logging = enable_detailed_logging
        self.retention_days = retention_days
        
        # In-memory buffer for batch writes
        self._buffer: List[AuditEntry] = []
        self._buffer_size = 100
    
    async def log_sync_operation(
        self,
        operation: SyncOperation,
        entity_type: str,
        direction: str,
        result: "SyncResult",
        **kwargs
    ) -> str:
        """Log a sync operation"""
        import uuid
        
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            operation=operation,
            entity_type=entity_type,
            direction=direction,
            metadata={
                "records_processed": result.records_processed,
                "records_created": result.records_created,
                "records_updated": result.records_updated,
                "records_failed": result.records_failed,
                "conflicts_detected": result.conflicts_detected,
                "conflicts_resolved": result.conflicts_resolved,
                "duration_seconds": result.duration_seconds,
                "checkpoint_id": result.checkpoint_id
            },
            status=result.status.value,
            error_message="; ".join(result.errors) if result.errors else None,
            **kwargs
        )
        
        await self._write_entry(entry)
        return entry.entry_id
    
    async def log_record_change(
        self,
        operation: SyncOperation,
        entity_type: str,
        close_id: Optional[str],
        supabase_id: Optional[str],
        before_data: Optional[Dict] = None,
        after_data: Optional[Dict] = None,
        changed_fields: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Log a single record change"""
        import uuid
        
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            operation=operation,
            entity_type=entity_type,
            direction=kwargs.get("direction", "bidirectional"),
            close_id=close_id,
            supabase_id=supabase_id,
            user_id=user_id,
            before_data_hash=self._hash_data(before_data) if before_data else None,
            after_data_hash=self._hash_data(after_data) if after_data else None,
            changed_fields=changed_fields or [],
            metadata={
                "before_snapshot": before_data if self.detailed_logging else None,
                "after_snapshot": after_data if self.detailed_logging else None
            },
            **{k: v for k, v in kwargs.items() if k not in ["direction"]}
        )
        
        await self._write_entry(entry)
        return entry.entry_id
    
    async def log_conflict(
        self,
        entity_type: str,
        close_id: str,
        supabase_id: str,
        close_data: Dict,
        supabase_data: Dict,
        conflicting_fields: List[str],
        resolution_strategy: Optional[str] = None,
        resolved: bool = False,
        **kwargs
    ) -> str:
        """Log a conflict event"""
        import uuid
        
        operation = (
            SyncOperation.CONFLICT_RESOLVED if resolved 
            else SyncOperation.CONFLICT_DETECTED
        )
        
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            operation=operation,
            entity_type=entity_type,
            direction="bidirectional",
            close_id=close_id,
            supabase_id=supabase_id,
            changed_fields=conflicting_fields,
            metadata={
                "close_data_hash": self._hash_data(close_data),
                "supabase_data_hash": self._hash_data(supabase_data),
                "resolution_strategy": resolution_strategy,
                "resolved": resolved
            },
            **kwargs
        )
        
        await self._write_entry(entry)
        return entry.entry_id
    
    async def log_error(
        self,
        entity_type: str,
        error_message: str,
        close_id: Optional[str] = None,
        supabase_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Log an error"""
        import uuid
        
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            operation=SyncOperation.ERROR,
            entity_type=entity_type,
            direction=kwargs.get("direction", "unknown"),
            close_id=close_id,
            supabase_id=supabase_id,
            status="error",
            error_message=error_message,
            **{k: v for k, v in kwargs.items() if k not in ["direction"]}
        )
        
        await self._write_entry(entry)
        logger.error(f"Sync error logged: {error_message}")
        return entry.entry_id
    
    async def log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ) -> str:
        """Log a security-related event"""
        import uuid
        
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            operation=SyncOperation.SECURITY_EVENT,
            entity_type="security",
            direction="internal",
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "event_type": event_type,
                "description": description,
                "severity": severity,
                **kwargs
            },
            status=severity
        )
        
        await self._write_entry(entry)
        
        if severity in ["warning", "error", "critical"]:
            logger.warning(f"Security event: {event_type} - {description}")
        
        return entry.entry_id
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    async def get_sync_history(
        self,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get sync operation history"""
        query = self.supabase.table(self.AUDIT_TABLE).select("*")
        
        if entity_type:
            query = query.eq("entity_type", entity_type)
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        
        query = query.order("timestamp", desc=True).limit(limit)
        
        response = await query.execute()
        return response.data or []
    
    async def get_conflict_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate conflict report"""
        query = self.supabase.table(self.AUDIT_TABLE).select("*")
        query = query.in_("operation", [
            SyncOperation.CONFLICT_DETECTED.value,
            SyncOperation.CONFLICT_RESOLVED.value
        ])
        
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        
        response = await query.execute()
        entries = response.data or []
        
        detected = [e for e in entries if e["operation"] == "conflict_detected"]
        resolved = [e for e in entries if e["operation"] == "conflict_resolved"]
        
        # Group by entity type
        by_entity = {}
        for entry in detected:
            entity = entry["entity_type"]
            if entity not in by_entity:
                by_entity[entity] = {"detected": 0, "resolved": 0}
            by_entity[entity]["detected"] += 1
        
        for entry in resolved:
            entity = entry["entity_type"]
            if entity not in by_entity:
                by_entity[entity] = {"detected": 0, "resolved": 0}
            by_entity[entity]["resolved"] += 1
        
        return {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "total_detected": len(detected),
            "total_resolved": len(resolved),
            "resolution_rate": round(len(resolved) / len(detected) * 100, 1) if detected else 100,
            "by_entity_type": by_entity
        }
    
    async def get_error_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate error report"""
        query = self.supabase.table(self.AUDIT_TABLE).select("*")
        query = query.eq("operation", SyncOperation.ERROR.value)
        
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        
        response = await query.execute()
        errors = response.data or []
        
        # Group by entity type
        by_entity = {}
        error_messages = {}
        
        for error in errors:
            entity = error["entity_type"]
            message = error.get("error_message", "Unknown")
            
            if entity not in by_entity:
                by_entity[entity] = 0
            by_entity[entity] += 1
            
            if message not in error_messages:
                error_messages[message] = 0
            error_messages[message] += 1
        
        return {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "total_errors": len(errors),
            "by_entity_type": by_entity,
            "common_errors": dict(sorted(
                error_messages.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10])
        }
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    async def _write_entry(self, entry: AuditEntry) -> None:
        """Write audit entry to storage"""
        self._buffer.append(entry)
        
        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush buffer to Supabase"""
        if not self._buffer:
            return
        
        rows = []
        for entry in self._buffer:
            rows.append({
                "entry_id": entry.entry_id,
                "operation": entry.operation.value,
                "entity_type": entry.entity_type,
                "direction": entry.direction,
                "close_id": entry.close_id,
                "supabase_id": entry.supabase_id,
                "user_id": entry.user_id,
                "before_data_hash": entry.before_data_hash,
                "after_data_hash": entry.after_data_hash,
                "changed_fields": entry.changed_fields,
                "metadata": entry.metadata,
                "status": entry.status,
                "error_message": entry.error_message,
                "timestamp": entry.timestamp.isoformat(),
                "ip_address": entry.ip_address,
                "user_agent": entry.user_agent
            })
        
        try:
            await self.supabase.table(self.AUDIT_TABLE).insert(rows).execute()
            self._buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {e}")
    
    @staticmethod
    def _hash_data(data: Dict) -> str:
        """Create SHA-256 hash of data for integrity verification"""
        if not data:
            return ""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
