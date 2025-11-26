"""
LinkedIn Credential Service

Manages LinkedIn OAuth state and credentials via Supabase.
Provides secure storage, retrieval, and lifecycle management for OAuth tokens.

Features:
- CSRF state management with expiration
- Encrypted credential storage via Supabase RLS
- In-memory caching to reduce database queries
- Token expiration tracking

Tables Required (run linkedin_oauth_schema.sql):
- oauth_state: Temporary CSRF state storage
- linkedin_credentials: Long-term token storage
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import logging
import os

logger = logging.getLogger(__name__)


class LinkedInCredentialService:
    """
    Manages LinkedIn OAuth state and credentials via Supabase.

    Usage:
        service = LinkedInCredentialService()

        # Generate OAuth state
        state = await service.create_oauth_state(user_id="user123")

        # After callback, validate and consume state
        state_data = await service.validate_and_consume_state(state)

        # Store credentials after token exchange
        await service.store_credentials(
            user_id="user123",
            access_token="AQX...",
            expires_in=5184000,  # 60 days
            scope="r_liteprofile r_emailaddress"
        )

        # Retrieve credentials for API calls
        creds = await service.get_credentials(user_id="user123")
    """

    def __init__(self, supabase_client=None):
        """
        Initialize credential service.

        Args:
            supabase_client: Supabase client instance. If None, will attempt
                           to create from environment variables.
        """
        self.supabase = supabase_client
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 300  # 5 minute cache

        # Lazy initialization of Supabase client
        if self.supabase is None:
            self._init_supabase()

    def _init_supabase(self):
        """Initialize Supabase client from environment variables."""
        try:
            from supabase import create_client, Client

            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

            if not url or not key:
                logger.warning(
                    "Supabase credentials not configured. "
                    "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
                )
                return

            self.supabase: Client = create_client(url, key)
            logger.info("LinkedIn credential service initialized with Supabase")

        except ImportError:
            logger.error("supabase-py not installed. Run: pip install supabase")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")

    # =========================================================================
    # OAuth State Management (CSRF Protection)
    # =========================================================================

    async def create_oauth_state(
        self,
        redirect_after: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate and store CSRF state token.

        Args:
            redirect_after: URL to redirect to after OAuth completes
            user_id: Optional user ID to associate with this OAuth flow

        Returns:
            Random state string (32 bytes, URL-safe base64)

        Note:
            State expires after 30 minutes per LinkedIn OAuth requirements.
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        state = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=30)

        try:
            self.supabase.table("oauth_state").insert({
                "state": state,
                "redirect_after": redirect_after,
                "user_id": user_id,
                "expires_at": expires_at.isoformat()
            }).execute()

            logger.debug(f"Created OAuth state, expires at {expires_at}")
            return state

        except Exception as e:
            logger.error(f"Failed to create OAuth state: {e}")
            raise

    async def validate_and_consume_state(self, state: str) -> Optional[Dict[str, Any]]:
        """
        Validate state, return data, then delete (one-time use).

        Args:
            state: State parameter from OAuth callback

        Returns:
            Dict with state data if valid, None if invalid/expired

        Security:
            - Validates state exists and is not expired
            - Deletes state after retrieval (prevents replay attacks)
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        try:
            # Query for valid, non-expired state
            result = self.supabase.table("oauth_state") \
                .select("*") \
                .eq("state", state) \
                .gt("expires_at", datetime.utcnow().isoformat()) \
                .execute()

            if not result.data:
                logger.warning(f"Invalid or expired OAuth state: {state[:8]}...")
                return None

            state_data = result.data[0]

            # Delete consumed state (one-time use)
            self.supabase.table("oauth_state") \
                .delete() \
                .eq("state", state) \
                .execute()

            logger.debug(f"Validated and consumed OAuth state: {state[:8]}...")
            return state_data

        except Exception as e:
            logger.error(f"Failed to validate OAuth state: {e}")
            return None

    async def cleanup_expired_states(self) -> int:
        """
        Remove expired OAuth state entries.

        Returns:
            Number of deleted entries

        Note:
            Call periodically (e.g., daily cron) or use the SQL function:
            SELECT cleanup_expired_oauth_state();
        """
        if not self.supabase:
            return 0

        try:
            result = self.supabase.table("oauth_state") \
                .delete() \
                .lt("expires_at", datetime.utcnow().isoformat()) \
                .execute()

            deleted = len(result.data) if result.data else 0
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired OAuth state entries")
            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup expired states: {e}")
            return 0

    # =========================================================================
    # Credential Storage
    # =========================================================================

    async def store_credentials(
        self,
        user_id: str,
        access_token: str,
        expires_in: int,
        scope: Optional[str] = None,
        id_token: Optional[str] = None,
        linkedin_sub: Optional[str] = None,
        linkedin_email: Optional[str] = None,
        linkedin_name: Optional[str] = None
    ) -> None:
        """
        Store or update LinkedIn credentials.

        Args:
            user_id: Unique user identifier
            access_token: OAuth access token
            expires_in: Token validity in seconds (typically 5184000 = 60 days)
            scope: Granted OAuth scopes
            id_token: OpenID Connect ID token (if using OIDC)
            linkedin_sub: LinkedIn user ID from /userinfo
            linkedin_email: Email from /userinfo
            linkedin_name: Display name from /userinfo

        Note:
            Uses upsert - creates new record or updates existing.
            Invalidates cache for this user_id.
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        try:
            self.supabase.table("linkedin_credentials").upsert({
                "user_id": user_id,
                "access_token": access_token,
                "id_token": id_token,
                "expires_at": expires_at.isoformat(),
                "scope": scope,
                "linkedin_sub": linkedin_sub,
                "linkedin_email": linkedin_email,
                "linkedin_name": linkedin_name,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="user_id").execute()

            # Invalidate cache
            self._cache.pop(user_id, None)

            logger.info(f"Stored LinkedIn credentials for user {user_id}, expires {expires_at}")

        except Exception as e:
            logger.error(f"Failed to store credentials: {e}")
            raise

    async def get_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get credentials with caching.

        Args:
            user_id: User identifier

        Returns:
            Dict with credential data if found and not expired, None otherwise

        Note:
            Results are cached for 5 minutes to reduce database queries.
            Returns None if credentials are expired.
        """
        if not self.supabase:
            return None

        # Check cache first
        if user_id in self._cache:
            cached = self._cache[user_id]
            if cached["cache_expires"] > datetime.utcnow():
                logger.debug(f"Cache hit for user {user_id}")
                return cached["data"]
            else:
                # Cache expired, remove it
                del self._cache[user_id]

        try:
            result = self.supabase.table("linkedin_credentials") \
                .select("*") \
                .eq("user_id", user_id) \
                .gt("expires_at", datetime.utcnow().isoformat()) \
                .execute()

            if not result.data:
                logger.debug(f"No valid credentials found for user {user_id}")
                return None

            credential_data = result.data[0]

            # Cache for 5 minutes
            self._cache[user_id] = {
                "data": credential_data,
                "cache_expires": datetime.utcnow() + timedelta(seconds=self._cache_ttl_seconds)
            }

            logger.debug(f"Loaded credentials for user {user_id}")
            return credential_data

        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")
            return None

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """
        Convenience method to get just the access token.

        Args:
            user_id: User identifier

        Returns:
            Access token string if valid, None otherwise
        """
        creds = await self.get_credentials(user_id)
        return creds.get("access_token") if creds else None

    async def update_credentials(
        self,
        user_id: str,
        access_token: str,
        expires_in: int
    ) -> None:
        """
        Update existing credentials (e.g., after token refresh).

        Args:
            user_id: User identifier
            access_token: New access token
            expires_in: New token validity in seconds
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        try:
            self.supabase.table("linkedin_credentials") \
                .update({
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("user_id", user_id) \
                .execute()

            # Invalidate cache
            self._cache.pop(user_id, None)

            logger.info(f"Updated LinkedIn credentials for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to update credentials: {e}")
            raise

    async def delete_credentials(self, user_id: str) -> None:
        """
        Remove credentials (logout/revoke).

        Args:
            user_id: User identifier
        """
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        try:
            self.supabase.table("linkedin_credentials") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()

            # Clear cache
            self._cache.pop(user_id, None)

            logger.info(f"Deleted LinkedIn credentials for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}")
            raise

    async def is_token_expired(self, user_id: str) -> bool:
        """
        Check if user's token is expired.

        Args:
            user_id: User identifier

        Returns:
            True if expired or not found, False if valid
        """
        creds = await self.get_credentials(user_id)
        if not creds:
            return True

        expires_at = datetime.fromisoformat(creds["expires_at"].replace("Z", "+00:00"))
        return expires_at <= datetime.utcnow()

    async def get_token_expiry(self, user_id: str) -> Optional[datetime]:
        """
        Get token expiration datetime.

        Args:
            user_id: User identifier

        Returns:
            Expiration datetime or None if not found
        """
        creds = await self.get_credentials(user_id)
        if not creds:
            return None

        return datetime.fromisoformat(creds["expires_at"].replace("Z", "+00:00"))

    def clear_cache(self, user_id: Optional[str] = None) -> None:
        """
        Clear credential cache.

        Args:
            user_id: Specific user to clear, or None for all users
        """
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()


# Singleton instance for dependency injection
_credential_service: Optional[LinkedInCredentialService] = None


def get_linkedin_credential_service() -> LinkedInCredentialService:
    """
    Get or create singleton credential service instance.

    Returns:
        LinkedInCredentialService instance

    Usage in FastAPI:
        @router.get("/profile")
        async def profile(
            cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
        ):
            creds = await cred_service.get_credentials(user_id)
    """
    global _credential_service
    if _credential_service is None:
        _credential_service = LinkedInCredentialService()
    return _credential_service
