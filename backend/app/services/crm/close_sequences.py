"""
Close CRM Sequences Integration

Enables sequence management for automated multi-step email campaigns.
Sequences are Close's built-in drip campaign feature.

API Documentation: https://developer.close.com/resources/sequences

Sequence Flow:
1. Create sequence with steps (email templates + delays)
2. Subscribe contacts to sequence
3. Monitor/pause/resume subscriptions
4. Auto-stop on reply (configurable)

Key Concepts:
- Sequence: The campaign definition (steps, delays, settings)
- Sequence Subscription: A contact enrolled in a sequence
- Sequence Step: Individual email template + delay configuration
"""

from typing import Optional, Dict, List, Any
import httpx
import logging
import base64
import os

logger = logging.getLogger(__name__)


class CloseSequencesClient:
    """
    Close CRM sequences client for multi-step email campaigns.

    Features:
    - Create and manage sequences
    - Subscribe/unsubscribe contacts
    - Pause/resume/stop subscriptions
    - Get subscription status and progress
    - List active sequences and subscribers

    Subscription Statuses:
    - active: Currently progressing through sequence
    - paused: Temporarily halted (e.g., OOO detected)
    - finished: Completed all steps
    - stopped: Manually stopped or triggered by reply
    - failed: Error during execution
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Subscription statuses
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_FINISHED = "finished"
    STATUS_STOPPED = "stopped"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize Close sequences client.

        Args:
            api_key: Close API key (falls back to CLOSE_API_KEY env var)
            redis_client: Redis client for rate limiting (optional)
        """
        self.api_key = api_key or os.getenv("CLOSE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Close API key required. Set CLOSE_API_KEY env var."
            )

        self.redis = redis_client
        self.write_enabled = os.getenv(
            "CLOSE_WRITE_DISABLED", "True"
        ).lower() not in ("true", "1", "yes")

        # Close uses Basic auth with format "api_key:"
        auth_string = f"{self.api_key}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        self.auth_header = f"Basic {auth_b64}"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }

    # ========== Sequence Management ==========

    async def list_sequences(
        self,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List all sequences in Close CRM.

        Args:
            active_only: Only return active sequences (default True)

        Returns:
            List of sequence objects
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/sequence/",
                    headers=self._get_headers(),
                )

                if response.status_code == 200:
                    data = response.json()
                    sequences = data.get("data", [])

                    if active_only:
                        sequences = [
                            s for s in sequences
                            if s.get("status") == "active"
                        ]

                    logger.info(f"Found {len(sequences)} sequences")
                    return sequences
                else:
                    logger.error(
                        f"Failed to list sequences: {response.status_code}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error listing sequences: {e}")
            return []

    async def get_sequence(self, sequence_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific sequence by ID.

        Args:
            sequence_id: Close sequence ID (seq_xxx)

        Returns:
            Sequence object or None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/sequence/{sequence_id}/",
                    headers=self._get_headers(),
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to get sequence {sequence_id}: "
                        f"{response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting sequence: {e}")
            return None

    async def get_sequence_by_name(
        self,
        name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a sequence by name.

        Args:
            name: Sequence name to search for

        Returns:
            Sequence object or None
        """
        sequences = await self.list_sequences(active_only=False)
        for seq in sequences:
            if seq.get("name", "").lower() == name.lower():
                return seq
        return None

    # ========== Subscription Management ==========

    async def subscribe_contact(
        self,
        sequence_id: str,
        contact_id: str,
        sender_account_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Subscribe a contact to a sequence.

        Args:
            sequence_id: Close sequence ID (seq_xxx)
            contact_id: Close contact ID (cont_xxx)
            sender_account_id: Connected account ID (optional)
            sender_name: Override sender name (optional)
            sender_email: Override sender email (optional)

        Returns:
            Subscription object or None if failed
        """
        if not self.write_enabled:
            logger.warning(
                "Close writes disabled. Would subscribe contact "
                f"{contact_id} to sequence {sequence_id}"
            )
            return {
                "id": "mock_sub_xxx",
                "status": "active",
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "mock": True
            }

        try:
            payload = {
                "sequence_id": sequence_id,
                "contact_id": contact_id,
            }

            if sender_account_id:
                payload["sender_account_id"] = sender_account_id
            if sender_name:
                payload["sender_name"] = sender_name
            if sender_email:
                payload["sender_email"] = sender_email

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/sequence_subscription/",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    logger.info(
                        f"Subscribed contact {contact_id} to sequence "
                        f"{sequence_id}: {result.get('id')}"
                    )
                    return result
                else:
                    logger.error(
                        f"Failed to subscribe: {response.status_code} - "
                        f"{response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error subscribing contact: {e}")
            return None

    async def unsubscribe_contact(
        self,
        subscription_id: str
    ) -> bool:
        """
        Unsubscribe (stop) a contact from a sequence.

        Args:
            subscription_id: Close subscription ID (sub_xxx)

        Returns:
            True if successful
        """
        if not self.write_enabled:
            logger.warning(
                f"Close writes disabled. Would unsubscribe {subscription_id}"
            )
            return True

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.BASE_URL}/sequence_subscription/{subscription_id}/",
                    headers=self._get_headers(),
                )

                if response.status_code in (200, 204):
                    logger.info(f"Unsubscribed {subscription_id}")
                    return True
                else:
                    logger.error(
                        f"Failed to unsubscribe: {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            return False

    async def pause_subscription(
        self,
        subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Pause a sequence subscription.

        Args:
            subscription_id: Close subscription ID (sub_xxx)

        Returns:
            Updated subscription object or None
        """
        if not self.write_enabled:
            logger.warning(
                f"Close writes disabled. Would pause {subscription_id}"
            )
            return {"id": subscription_id, "status": "paused", "mock": True}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.BASE_URL}/sequence_subscription/{subscription_id}/",
                    headers=self._get_headers(),
                    json={"status": self.STATUS_PAUSED},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Paused subscription {subscription_id}")
                    return result
                else:
                    logger.error(
                        f"Failed to pause: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error pausing subscription: {e}")
            return None

    async def resume_subscription(
        self,
        subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resume a paused sequence subscription.

        Args:
            subscription_id: Close subscription ID (sub_xxx)

        Returns:
            Updated subscription object or None
        """
        if not self.write_enabled:
            logger.warning(
                f"Close writes disabled. Would resume {subscription_id}"
            )
            return {"id": subscription_id, "status": "active", "mock": True}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.BASE_URL}/sequence_subscription/{subscription_id}/",
                    headers=self._get_headers(),
                    json={"status": self.STATUS_ACTIVE},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Resumed subscription {subscription_id}")
                    return result
                else:
                    logger.error(
                        f"Failed to resume: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error resuming subscription: {e}")
            return None

    async def get_subscription(
        self,
        subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific subscription by ID.

        Args:
            subscription_id: Close subscription ID (sub_xxx)

        Returns:
            Subscription object or None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/sequence_subscription/{subscription_id}/",
                    headers=self._get_headers(),
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to get subscription: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None

    async def get_contact_subscriptions(
        self,
        contact_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all sequence subscriptions for a contact.

        Args:
            contact_id: Close contact ID (cont_xxx)
            active_only: Only return active subscriptions

        Returns:
            List of subscription objects
        """
        try:
            params = {"contact_id": contact_id}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/sequence_subscription/",
                    headers=self._get_headers(),
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    subs = data.get("data", [])

                    if active_only:
                        subs = [
                            s for s in subs
                            if s.get("status") == self.STATUS_ACTIVE
                        ]

                    return subs
                else:
                    logger.error(
                        f"Failed to get subscriptions: {response.status_code}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error getting subscriptions: {e}")
            return []

    async def stop_all_sequences_for_contact(
        self,
        contact_id: str
    ) -> int:
        """
        Stop all active sequences for a contact.

        Useful when contact unsubscribes or marks not interested.

        Args:
            contact_id: Close contact ID (cont_xxx)

        Returns:
            Number of sequences stopped
        """
        subscriptions = await self.get_contact_subscriptions(
            contact_id, active_only=True
        )

        stopped = 0
        for sub in subscriptions:
            sub_id = sub.get("id")
            if sub_id and await self.unsubscribe_contact(sub_id):
                stopped += 1

        logger.info(f"Stopped {stopped} sequences for contact {contact_id}")
        return stopped

    async def bulk_subscribe(
        self,
        contact_ids: List[str],
        sequence_id: str,
        sender_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_account_id: Optional[str] = None,
        skip_already_subscribed: bool = True
    ) -> Dict[str, Any]:
        """
        Subscribe multiple contacts to a sequence.

        Args:
            contact_ids: List of Close contact IDs (cont_xxx)
            sequence_id: Close sequence ID (seq_xxx)
            sender_email: Override sender email (optional)
            sender_name: Override sender name (optional)
            sender_account_id: Connected account ID (optional)
            skip_already_subscribed: Skip contacts already in sequence (default True)

        Returns:
            Dict with:
                - subscribed_count: Number of contacts newly subscribed
                - already_subscribed: Number skipped (already in sequence)
                - failed_count: Number of failed subscriptions
                - errors: List of error messages
                - subscriptions: List of subscription objects created
        """
        result = {
            "subscribed_count": 0,
            "already_subscribed": 0,
            "failed_count": 0,
            "errors": [],
            "subscriptions": []
        }

        # Handle empty input
        if not contact_ids:
            return result

        for contact_id in contact_ids:
            try:
                # Check if already subscribed (if skip enabled)
                if skip_already_subscribed:
                    existing_subs = await self.get_contact_subscriptions(
                        contact_id=contact_id,
                        active_only=True
                    )
                    # Check if already in this specific sequence
                    in_sequence = any(
                        sub.get("sequence_id") == sequence_id
                        for sub in existing_subs
                    )
                    if in_sequence:
                        result["already_subscribed"] += 1
                        logger.debug(
                            f"Contact {contact_id} already subscribed to {sequence_id}"
                        )
                        continue

                # Subscribe the contact
                subscription = await self.subscribe_contact(
                    sequence_id=sequence_id,
                    contact_id=contact_id,
                    sender_account_id=sender_account_id,
                    sender_name=sender_name,
                    sender_email=sender_email
                )

                if subscription:
                    result["subscribed_count"] += 1
                    result["subscriptions"].append(subscription)
                else:
                    result["failed_count"] += 1
                    result["errors"].append(
                        f"Failed to subscribe contact {contact_id} - no response"
                    )

            except Exception as e:
                result["failed_count"] += 1
                error_msg = f"Failed to subscribe contact {contact_id}: {str(e)}"
                result["errors"].append(error_msg)
                logger.error(error_msg)

        logger.info(
            f"Bulk subscribe complete: {result['subscribed_count']} subscribed, "
            f"{result['already_subscribed']} already subscribed, "
            f"{result['failed_count']} failed"
        )

        return result

    # ========== Subscription Queries ==========

    async def list_active_subscriptions(
        self,
        sequence_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List active sequence subscriptions.

        Args:
            sequence_id: Filter by sequence ID (optional)
            limit: Maximum results to return

        Returns:
            List of active subscription objects
        """
        try:
            params = {"_limit": limit}
            if sequence_id:
                params["sequence_id"] = sequence_id

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/sequence_subscription/",
                    headers=self._get_headers(),
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    subs = data.get("data", [])
                    # Filter to active only
                    return [
                        s for s in subs
                        if s.get("status") == self.STATUS_ACTIVE
                    ]
                else:
                    return []

        except Exception as e:
            logger.error(f"Error listing subscriptions: {e}")
            return []


# Convenience function for getting client instance
_client_instance: Optional[CloseSequencesClient] = None


def get_close_sequences_client() -> CloseSequencesClient:
    """Get or create singleton CloseSequencesClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = CloseSequencesClient()
    return _client_instance


__all__ = ["CloseSequencesClient", "get_close_sequences_client"]
