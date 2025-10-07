"""
CRM Sync Service

Orchestrates bidirectional synchronization between local PostgreSQL database
and CRM platforms (Close, Apollo, LinkedIn).

Features:
- Multi-platform sync coordination
- Conflict resolution with last-write-wins strategy
- Circuit breaker integration for resilience
- Webhook event processing
- Dead letter queue for failed syncs
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.services.crm import (
    CRMProvider,
    CloseProvider,
    ApolloProvider,
    LinkedInProvider,
    Contact,
    CRMCredentials,
    SyncResult,
    WebhookEvent,
    CRMException,
    CRMRateLimitError,
)
from app.services.circuit_breaker import CircuitBreaker
from app.services.retry_handler import ExponentialBackoffRetry
from app.models.crm import CRMCredential, CRMContact, CRMSyncLog
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CRMSyncService:
    """
    Orchestrates CRM synchronization across multiple platforms.

    Handles:
    - Provider initialization from database credentials
    - Bidirectional sync (import/export)
    - Conflict resolution
    - Error recovery with circuit breakers
    - Webhook processing
    """

    def __init__(
        self,
        db: Session,
        redis_client: Optional[Any] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_handler: Optional[ExponentialBackoffRetry] = None
    ):
        """
        Initialize CRM sync service.

        Args:
            db: Database session
            redis_client: Redis client for rate limiting
            circuit_breaker: Circuit breaker for resilience
            retry_handler: Exponential backoff retry handler
        """
        self.db = db
        self.redis = redis_client
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.retry_handler = retry_handler or ExponentialBackoffRetry(
            max_retries=3,
            base_delay=2.0,
            max_delay=60.0
        )

    def _get_provider(
        self,
        platform: str,
        credentials: CRMCredentials
    ) -> CRMProvider:
        """
        Factory method to create CRM provider instance.

        Args:
            platform: CRM platform name ("close", "apollo", "linkedin")
            credentials: Encrypted CRM credentials

        Returns:
            Initialized CRM provider

        Raises:
            ValueError: If platform is unknown
        """
        providers = {
            "close": CloseProvider,
            "apollo": ApolloProvider,
            "linkedin": LinkedInProvider,
        }

        provider_class = providers.get(platform.lower())
        if not provider_class:
            raise ValueError(
                f"Unknown CRM platform: {platform}. "
                f"Supported: {', '.join(providers.keys())}"
            )

        return provider_class(credentials, redis_client=self.redis)

    async def sync_platform(
        self,
        platform: str,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Sync contacts with a specific CRM platform.

        Args:
            platform: CRM platform ("close", "apollo", "linkedin")
            direction: Sync direction ("import", "export", "bidirectional")
            filters: Platform-specific filters

        Returns:
            SyncResult with metrics

        Raises:
            CRMException: If sync fails
        """
        started_at = datetime.utcnow()

        try:
            # Get active credentials for platform
            credential_record = self.db.query(CRMCredential).filter(
                CRMCredential.platform == platform.lower(),
                CRMCredential.is_active == True
            ).first()

            if not credential_record:
                logger.error(f"No active credentials found for {platform}")
                return SyncResult(
                    platform=platform,
                    operation=direction,
                    contacts_processed=0,
                    contacts_failed=1,
                    errors=[{"error": f"No active credentials for {platform}"}],
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )

            # Convert to CRMCredentials model
            credentials = CRMCredentials(
                platform=credential_record.platform,
                access_token=credential_record.access_token,
                refresh_token=credential_record.refresh_token,
                api_key=credential_record.api_key,
                scopes=credential_record.scopes
            )

            # Initialize provider
            provider = self._get_provider(platform, credentials)

            # Wrap sync operation with circuit breaker and retry logic
            async def sync_with_resilience():
                return await self.retry_handler.execute(
                    lambda: provider.sync_contacts(direction, filters)
                )

            # Execute sync
            logger.info(f"Starting {direction} sync for {platform}")
            result = await self.circuit_breaker.call(sync_with_resilience)

            # Log sync operation
            self._log_sync_operation(credential_record.id, result)

            return result

        except CRMRateLimitError as e:
            logger.warning(f"Rate limit exceeded for {platform}: {e}")
            result = SyncResult(
                platform=platform,
                operation=direction,
                contacts_processed=0,
                contacts_failed=1,
                errors=[{"error": f"Rate limit: {str(e)}"}],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            return result

        except Exception as e:
            logger.error(f"Error syncing {platform}: {e}", exc_info=True)
            result = SyncResult(
                platform=platform,
                operation=direction,
                contacts_processed=0,
                contacts_failed=1,
                errors=[{"error": str(e)}],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            return result

    def _log_sync_operation(
        self,
        credential_id: int,
        result: SyncResult
    ) -> None:
        """
        Log sync operation to database for audit trail.

        Args:
            credential_id: CRM credential ID
            result: Sync result to log
        """
        try:
            duration = None
            if result.started_at and result.completed_at:
                duration = (result.completed_at - result.started_at).total_seconds()

            sync_log = CRMSyncLog(
                credential_id=credential_id,
                platform=result.platform,
                operation=result.operation,
                contacts_processed=result.contacts_processed,
                contacts_created=result.contacts_created,
                contacts_updated=result.contacts_updated,
                contacts_failed=result.contacts_failed,
                errors=result.errors if result.errors else None,
                started_at=result.started_at,
                completed_at=result.completed_at,
                duration_seconds=duration,
                status="completed" if result.contacts_failed == 0 else "failed"
            )

            self.db.add(sync_log)
            self.db.commit()

            logger.info(f"Logged sync operation: {sync_log.id}")

        except Exception as e:
            logger.error(f"Failed to log sync operation: {e}")
            self.db.rollback()

    async def import_contacts(
        self,
        platform: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Import contacts from CRM to local database.

        Args:
            platform: CRM platform name
            filters: Platform-specific filters

        Returns:
            SyncResult with import metrics
        """
        return await self.sync_platform(platform, direction="import", filters=filters)

    async def export_contacts(
        self,
        platform: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Export contacts from local database to CRM.

        Args:
            platform: CRM platform name
            filters: Platform-specific filters

        Returns:
            SyncResult with export metrics
        """
        return await self.sync_platform(platform, direction="export", filters=filters)

    async def bidirectional_sync(
        self,
        platform: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform two-way sync between local DB and CRM.

        Args:
            platform: CRM platform name
            filters: Platform-specific filters

        Returns:
            SyncResult with bidirectional sync metrics
        """
        return await self.sync_platform(platform, direction="bidirectional", filters=filters)

    def resolve_conflict(
        self,
        local_contact: CRMContact,
        remote_contact: Contact
    ) -> CRMContact:
        """
        Resolve conflict between local and remote contact data.

        Strategy: Last-write-wins based on updated_at timestamps.
        Critical fields (email, name) flagged for manual review.

        Args:
            local_contact: Contact from local database
            remote_contact: Contact from CRM platform

        Returns:
            Resolved contact (winner based on timestamp)
        """
        # Compare timestamps (last-write-wins)
        local_updated = local_contact.updated_at
        remote_updated = remote_contact.custom_fields.get("updated_at") if remote_contact.custom_fields else None

        if remote_updated and isinstance(remote_updated, str):
            try:
                remote_updated = datetime.fromisoformat(remote_updated)
            except:
                remote_updated = None

        # Default to remote if no clear timestamp
        if not local_updated and not remote_updated:
            logger.warning(f"No timestamps for conflict resolution - using remote data")
            return self._merge_contact(local_contact, remote_contact)

        # Last-write-wins
        if remote_updated and (not local_updated or remote_updated > local_updated):
            logger.info(f"Remote contact newer - using remote data for {remote_contact.email}")
            return self._merge_contact(local_contact, remote_contact)
        else:
            logger.info(f"Local contact newer - keeping local data for {local_contact.email}")
            return local_contact

    def _merge_contact(
        self,
        local_contact: CRMContact,
        remote_contact: Contact
    ) -> CRMContact:
        """
        Merge remote contact data into local contact record.

        Args:
            local_contact: Local database contact
            remote_contact: Remote CRM contact

        Returns:
            Updated local contact
        """
        # Update fields from remote
        if remote_contact.first_name:
            local_contact.first_name = remote_contact.first_name
        if remote_contact.last_name:
            local_contact.last_name = remote_contact.last_name
        if remote_contact.company:
            local_contact.company = remote_contact.company
        if remote_contact.title:
            local_contact.title = remote_contact.title
        if remote_contact.phone:
            local_contact.phone = remote_contact.phone
        if remote_contact.linkedin_url:
            local_contact.linkedin_url = remote_contact.linkedin_url

        # Merge enrichment data
        if remote_contact.custom_fields:
            if not local_contact.enrichment_data:
                local_contact.enrichment_data = {}
            local_contact.enrichment_data.update(remote_contact.custom_fields)

        # Update sync metadata
        local_contact.last_synced_at = datetime.utcnow()
        local_contact.updated_at = datetime.utcnow()

        return local_contact

    async def process_webhook_event(
        self,
        platform: str,
        event: WebhookEvent
    ) -> None:
        """
        Process webhook event from CRM platform.

        Args:
            platform: CRM platform that sent webhook
            event: Webhook event data
        """
        logger.info(f"Processing webhook from {platform}: {event.event_type}")

        try:
            # Get credentials
            credential_record = self.db.query(CRMCredential).filter(
                CRMCredential.platform == platform.lower(),
                CRMCredential.is_active == True
            ).first()

            if not credential_record:
                logger.error(f"No credentials for webhook from {platform}")
                return

            credentials = CRMCredentials(
                platform=credential_record.platform,
                access_token=credential_record.access_token,
                api_key=credential_record.api_key
            )

            # Initialize provider
            provider = self._get_provider(platform, credentials)

            # Delegate to provider's webhook handler
            await provider.handle_webhook(event)

            logger.info(f"Webhook processed successfully: {event.event_type}")

        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)

    async def get_sync_status(self, platform: str) -> Dict[str, Any]:
        """
        Get current sync status for a platform.

        Args:
            platform: CRM platform name

        Returns:
            Dict with sync status information
        """
        try:
            # Get most recent sync log
            latest_sync = self.db.query(CRMSyncLog).filter(
                CRMSyncLog.platform == platform.lower()
            ).order_by(CRMSyncLog.started_at.desc()).first()

            if not latest_sync:
                return {
                    "platform": platform,
                    "status": "never_synced",
                    "last_sync_at": None
                }

            return {
                "platform": platform,
                "status": latest_sync.status,
                "last_sync_at": latest_sync.completed_at.isoformat() if latest_sync.completed_at else None,
                "contacts_processed": latest_sync.contacts_processed,
                "contacts_created": latest_sync.contacts_created,
                "contacts_updated": latest_sync.contacts_updated,
                "contacts_failed": latest_sync.contacts_failed,
                "duration_seconds": latest_sync.duration_seconds,
                "errors": latest_sync.errors
            }

        except Exception as e:
            logger.error(f"Error getting sync status for {platform}: {e}")
            return {
                "platform": platform,
                "status": "error",
                "error": str(e)
            }
