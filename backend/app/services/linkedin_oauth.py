"""
LinkedIn OAuth 2.0 Integration

Implements OAuth 2.0 authentication and profile API access for LinkedIn.
Follows the same pattern as HubSpot integration with PKCE for enhanced security.

Key Features:
- OAuth 2.0 with PKCE (code_challenge/code_verifier)
- State parameter for CSRF protection
- Token refresh (when available - LinkedIn may not provide refresh tokens for all API types)
- Strict rate limiting (100 requests/day for basic tier)
- Redis-based rate limit tracking
- Profile API access for user information

LinkedIn API Documentation:
- OAuth: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- Profile API: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import httpx
import hashlib
import hmac
import secrets
import base64
from urllib.parse import urlencode
import logging

from app.services.crm.base import (
    CRMProvider,
    Contact,
    CRMCredentials,
    SyncResult,
    WebhookEvent,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMNetworkError,
    CRMWebhookError,
)

logger = logging.getLogger(__name__)


class LinkedInProvider(CRMProvider):
    """
    LinkedIn OAuth 2.0 integration.

    Features:
    - OAuth 2.0 with PKCE for secure authentication
    - Profile retrieval (r_liteprofile, r_emailaddress)
    - Content sharing (w_member_social) - future feature
    - Strict rate limiting (100 requests/day for basic tier)
    - Token refresh with graceful fallback (LinkedIn may not provide refresh tokens)

    Rate Limits:
    - Basic tier: 100 requests per day
    - Need to carefully track all API calls

    Token Validity:
    - Access tokens: 60 days (compliance API: 1 year)
    - Refresh tokens: May not be provided for all API types
    - Re-authentication required when tokens expire without refresh capability
    """

    BASE_URL = "https://api.linkedin.com"
    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

    # Rate limits for basic tier
    RATE_LIMIT_DAILY = 100  # 100 requests per day for basic tier

    # Token expiration (60 days for standard OAuth)
    TOKEN_EXPIRY_DAYS = 60

    def __init__(
        self,
        credentials: CRMCredentials,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize LinkedIn provider.

        Args:
            credentials: CRM credentials with OAuth tokens
            client_id: LinkedIn app client ID
            client_secret: LinkedIn app client secret
            redirect_uri: OAuth redirect URI
            redis_client: Redis client for rate limiting and state storage (optional)
        """
        super().__init__(credentials)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.redis = redis_client

        # Decrypt access token if present
        self.access_token = None
        if credentials.access_token:
            self.access_token = self.decrypt_credential(credentials.access_token)

    # ========================================================================
    # OAUTH 2.0 AUTHENTICATION
    # ========================================================================

    def generate_authorization_url(self, scopes: List[str]) -> tuple[str, str, str]:
        """
        Generate OAuth authorization URL with PKCE and state parameter.

        Args:
            scopes: List of OAuth scopes (e.g., ['r_liteprofile', 'r_emailaddress'])

        Returns:
            Tuple of (authorization_url, code_verifier, state)

        Note:
            Store code_verifier and state securely (e.g., in Redis with short TTL)
            for callback verification.
        """
        # Generate PKCE code verifier and challenge (S256 method)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode('utf-8').rstrip('=')

        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state and code_verifier in Redis for callback verification (10 min TTL)
        if self.redis:
            state_key = f"linkedin:oauth:state:{state}"
            self.redis.setex(state_key, 600, code_verifier)  # 10 minutes

        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }

        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        return auth_url, code_verifier, state

    async def exchange_code_for_token(
        self,
        authorization_code: str,
        code_verifier: str,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            authorization_code: Code from OAuth callback
            code_verifier: PKCE code verifier
            state: State parameter for verification (optional but recommended)

        Returns:
            Token response with access_token, expires_in, and optionally refresh_token

        Raises:
            CRMAuthenticationError: If token exchange fails or state verification fails

        Note:
            LinkedIn may not provide refresh_token for all API types.
            The response will indicate token expiry time (typically 60 days).
        """
        # Verify state parameter if provided
        if state and self.redis:
            state_key = f"linkedin:oauth:state:{state}"
            stored_verifier = self.redis.get(state_key)

            if not stored_verifier or stored_verifier.decode() != code_verifier:
                raise CRMAuthenticationError(
                    "State verification failed - possible CSRF attack",
                    context={'state': state}
                )

            # Delete used state
            self.redis.delete(state_key)

        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code_verifier': code_verifier,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                token_data = response.json()

                # Update credentials
                self.access_token = token_data['access_token']
                self.credentials.access_token = self.encrypt_credential(self.access_token)

                # LinkedIn may not provide refresh_token for all API types
                if 'refresh_token' in token_data:
                    self.credentials.refresh_token = self.encrypt_credential(token_data['refresh_token'])
                    logger.info("LinkedIn refresh token received")
                else:
                    logger.warning(
                        "LinkedIn did not provide refresh token - "
                        "re-authentication will be required after token expiry"
                    )
                    self.credentials.refresh_token = None

                # Calculate token expiration (default 60 days if not specified)
                expires_in = token_data.get('expires_in', self.TOKEN_EXPIRY_DAYS * 86400)
                self.credentials.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                logger.info(
                    f"LinkedIn token obtained - expires at {self.credentials.token_expires_at}"
                )

                return token_data

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise CRMAuthenticationError(
                f"LinkedIn token exchange failed: {error_detail}",
                context={'status_code': e.response.status_code, 'error': error_detail}
            )
        except Exception as e:
            raise CRMNetworkError(f"LinkedIn token exchange error: {str(e)}")

    async def authenticate(self) -> bool:
        """
        Verify authentication by making a test API call to get profile.

        Returns:
            True if authenticated successfully

        Raises:
            CRMAuthenticationError: If authentication fails
        """
        if not self.access_token:
            raise CRMAuthenticationError("No access token available")

        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/v2/me",
                    headers=headers
                )
                response.raise_for_status()
                return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise CRMAuthenticationError(
                    "LinkedIn authentication failed: Invalid or expired access token"
                )
            raise

    async def refresh_access_token(self) -> str:
        """
        Refresh OAuth access token using refresh token.

        Returns:
            New access token

        Raises:
            CRMAuthenticationError: If refresh fails or refresh token not available

        Note:
            LinkedIn may not provide refresh tokens for all API types.
            If refresh token is not available, this will raise an error indicating
            that re-authentication is required.
        """
        if not self.credentials.refresh_token:
            raise CRMAuthenticationError(
                "No refresh token available - LinkedIn did not provide refresh capability. "
                "Please re-authenticate via OAuth flow.",
                context={'requires_reauth': True}
            )

        refresh_token = self.decrypt_credential(self.credentials.refresh_token)

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                token_data = response.json()

                # Update credentials
                self.access_token = token_data['access_token']
                self.credentials.access_token = self.encrypt_credential(self.access_token)

                # Update refresh token if provided
                if 'refresh_token' in token_data:
                    self.credentials.refresh_token = self.encrypt_credential(token_data['refresh_token'])

                # Calculate token expiration
                expires_in = token_data.get('expires_in', self.TOKEN_EXPIRY_DAYS * 86400)
                self.credentials.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                logger.info(f"LinkedIn token refreshed - expires at {self.credentials.token_expires_at}")

                return self.access_token

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise CRMAuthenticationError(
                f"LinkedIn token refresh failed: {error_detail}. Re-authentication required.",
                context={'status_code': e.response.status_code, 'requires_reauth': True}
            )
        except Exception as e:
            raise CRMNetworkError(f"LinkedIn token refresh error: {str(e)}")

    # ========================================================================
    # PROFILE OPERATIONS
    # ========================================================================

    async def get_profile(self) -> Dict[str, Any]:
        """
        Get authenticated user's LinkedIn profile.

        Returns:
            Profile data including id, firstName, lastName, profilePicture

        Requires scopes:
            - r_liteprofile (basic profile info)

        Raises:
            CRMAuthenticationError: If not authenticated
            CRMRateLimitError: If rate limit exceeded
        """
        await self._check_rate_limit()

        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/v2/me",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise CRMAuthenticationError("LinkedIn authentication failed")
            elif e.response.status_code == 429:
                raise CRMRateLimitError("LinkedIn rate limit exceeded")
            raise

    async def get_email_address(self) -> str:
        """
        Get authenticated user's email address.

        Returns:
            Primary email address

        Requires scopes:
            - r_emailaddress

        Raises:
            CRMAuthenticationError: If not authenticated or scope missing
            CRMRateLimitError: If rate limit exceeded
        """
        await self._check_rate_limit()

        headers = {'Authorization': f'Bearer {self.access_token}'}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/v2/emailAddress?q=members&projection=(elements*(handle~))",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                # Extract primary email
                elements = data.get('elements', [])
                if elements and 'handle~' in elements[0]:
                    return elements[0]['handle~'].get('emailAddress', '')

                return ''

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise CRMAuthenticationError("LinkedIn authentication failed or missing r_emailaddress scope")
            elif e.response.status_code == 429:
                raise CRMRateLimitError("LinkedIn rate limit exceeded")
            raise

    # ========================================================================
    # CONTACT OPERATIONS (Required by CRMProvider)
    # ========================================================================

    async def get_contact(self, contact_id: str) -> Contact:
        """
        LinkedIn doesn't provide direct contact management like HubSpot.
        This method retrieves the authenticated user's profile as a Contact.

        Args:
            contact_id: LinkedIn member ID (or 'me' for authenticated user)

        Returns:
            Contact object
        """
        profile = await self.get_profile()
        email = await self.get_email_address()

        # Extract name from profile
        first_name = profile.get('localizedFirstName', '')
        last_name = profile.get('localizedLastName', '')

        return Contact(
            email=email or 'unknown@linkedin.com',
            first_name=first_name,
            last_name=last_name,
            linkedin_url=f"https://linkedin.com/in/{contact_id}" if contact_id != 'me' else None,
            external_ids={'linkedin': profile.get('id', contact_id)},
            source_platform='linkedin',
            last_synced_at=datetime.utcnow(),
        )

    async def create_contact(self, contact: Contact) -> Contact:
        """
        LinkedIn doesn't support creating contacts via API.

        Raises:
            CRMValidationError: Always - operation not supported
        """
        raise CRMValidationError(
            "LinkedIn API does not support creating contacts. "
            "Use connection requests or messaging APIs instead."
        )

    async def update_contact(self, contact_id: str, contact: Contact) -> Contact:
        """
        LinkedIn doesn't support updating contacts via API.

        Raises:
            CRMValidationError: Always - operation not supported
        """
        raise CRMValidationError(
            "LinkedIn API does not support updating contacts. "
            "Use profile update APIs for the authenticated user only."
        )

    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        LinkedIn doesn't provide contact enrichment.
        Use Apollo or other enrichment providers instead.

        Returns:
            None (not supported)
        """
        logger.info("LinkedIn does not support contact enrichment. Use Apollo provider.")
        return None

    # ========================================================================
    # SYNC OPERATIONS (Required by CRMProvider)
    # ========================================================================

    async def sync_contacts(
        self,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        LinkedIn doesn't support bulk contact sync.

        Returns:
            Empty sync result
        """
        result = SyncResult(
            platform='linkedin',
            operation=direction,
            started_at=datetime.utcnow()
        )
        result.completed_at = datetime.utcnow()
        result.duration_seconds = 0

        logger.info("LinkedIn does not support contact sync operations")
        return result

    async def get_updated_contacts(self, since: datetime) -> List[Contact]:
        """
        LinkedIn doesn't support querying updated contacts.

        Returns:
            Empty list
        """
        return []

    # ========================================================================
    # WEBHOOK HANDLING (Required by CRMProvider)
    # ========================================================================

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify LinkedIn webhook signature.

        Note: LinkedIn webhook verification depends on the specific webhook type.
        Implement based on LinkedIn's webhook documentation for your use case.

        Args:
            payload: Raw webhook payload bytes
            signature: Signature from webhook headers

        Returns:
            True if signature is valid
        """
        try:
            expected_signature = hmac.new(
                self.client_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(expected_signature, signature)

            if not is_valid:
                raise CRMWebhookError(
                    "LinkedIn webhook signature verification failed",
                    context={'provided': signature, 'expected': expected_signature}
                )

            return is_valid

        except Exception as e:
            raise CRMWebhookError(f"Webhook verification error: {str(e)}")

    async def handle_webhook(self, event: WebhookEvent) -> None:
        """
        Process LinkedIn webhook event.

        Args:
            event: Webhook event data
        """
        logger.info(f"LinkedIn webhook received: {event.event_type}")
        # Implement based on specific webhook types needed

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    async def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limits using Redis.

        LinkedIn basic tier: 100 requests per day

        Raises:
            CRMRateLimitError: If rate limit exceeded
        """
        if not self.redis:
            logger.warning("Redis not available - rate limiting disabled")
            return

        user_id = self.credentials.user_id or 'default'

        # Check daily limit (100 requests/day)
        key_daily = f"linkedin:ratelimit:daily:{user_id}"
        count_daily = await self.redis.incr(key_daily)

        if count_daily == 1:
            # Set expiry for 24 hours
            await self.redis.expire(key_daily, 86400)

        if count_daily > self.RATE_LIMIT_DAILY:
            raise CRMRateLimitError(
                f"LinkedIn daily limit exceeded: {self.RATE_LIMIT_DAILY} requests per day",
                retry_after=86400,
                context={'requests_made': count_daily, 'limit': self.RATE_LIMIT_DAILY}
            )

        logger.debug(f"LinkedIn API calls today: {count_daily}/{self.RATE_LIMIT_DAILY}")

    async def check_rate_limit(self) -> Dict[str, Any]:
        """
        Check current rate limit status.

        Returns:
            Dict with rate limit info
        """
        if not self.redis:
            return {
                'remaining': self.RATE_LIMIT_DAILY,
                'limit': self.RATE_LIMIT_DAILY,
                'reset_at': None,
                'retry_after': 0
            }

        user_id = self.credentials.user_id or 'default'
        key_daily = f"linkedin:ratelimit:daily:{user_id}"

        count_daily = await self.redis.get(key_daily) or 0
        ttl = await self.redis.ttl(key_daily)

        return {
            'remaining': max(0, self.RATE_LIMIT_DAILY - int(count_daily)),
            'limit': self.RATE_LIMIT_DAILY,
            'reset_at': datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None,
            'retry_after': ttl if int(count_daily) >= self.RATE_LIMIT_DAILY else 0,
            'requests_today': int(count_daily)
        }
