"""
LinkedIn CRM Integration

Implements OAuth 2.0 authentication, profile API access, and contact enrichment
for LinkedIn using the v2 API and Browserbase scraping.

Key Features:
- OAuth 2.0 with PKCE (code_challenge/code_verifier)
- State parameter for CSRF protection
- Token refresh (when available - LinkedIn may not provide refresh tokens for all API types)
- Strict rate limiting (100 requests/day for basic tier)
- Redis-based rate limit tracking
- Profile API access for user information
- Contact enrichment via Browserbase scraping
- Outreach automation (stubbed - requires LinkedIn partnership)

IMPORTANT API LIMITATIONS:
⚠️ LinkedIn's official APIs have severe restrictions:
- ❌ No automated connection requests (requires Marketing Developer Platform partnership)
- ❌ No automated messaging (requires Sales Navigator or partnership)
- ❌ No bulk contact sync
- ✅ OAuth profile retrieval (r_liteprofile, r_emailaddress)
- ✅ Contact enrichment via scraping (Browserbase)
- ✅ Company employee discovery via scraping

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
from app.services.linkedin_scraper import LinkedInScraper

logger = logging.getLogger(__name__)


class LinkedInProvider(CRMProvider):
    """
    LinkedIn CRM integration with OAuth 2.0 and contact enrichment.

    Features:
    - OAuth 2.0 with PKCE for secure authentication
    - Profile retrieval (r_liteprofile, r_emailaddress)
    - Contact enrichment via Browserbase scraping
    - Company employee discovery
    - Strict rate limiting (100 requests/day for basic tier)
    - Token refresh with graceful fallback (LinkedIn may not provide refresh tokens)
    - Outreach automation (stubbed - requires partnership)

    Rate Limits:
    - Basic tier: 100 requests per day
    - Need to carefully track all API calls

    Token Validity:
    - Access tokens: 60 days (compliance API: 1 year)
    - Refresh tokens: May not be provided for all API types
    - Re-authentication required when tokens expire without refresh capability

    API Restrictions:
    - Connection requests: NOT SUPPORTED (requires partnership)
    - Messaging: NOT SUPPORTED (requires Sales Navigator/partnership)
    - Bulk sync: NOT SUPPORTED
    - Profile enrichment: Supported via scraping
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

        # Initialize scraper for contact enrichment
        self.scraper = LinkedInScraper()

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
            "Use connection requests or messaging APIs instead (requires partnership)."
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
        Enrich contact using LinkedIn scraper if profile URL available.

        Note: LinkedIn official API doesn't provide contact enrichment.
        This method uses Browserbase scraping for enrichment.

        Args:
            email: Contact email (not directly used - LinkedIn doesn't support email lookup)

        Returns:
            None - Use enrich_contact_from_profile() with profile URL instead
        """
        logger.info(
            "LinkedIn does not support email-based enrichment. "
            "Use enrich_contact_from_profile() with profile URL instead, "
            "or use Apollo provider for email enrichment."
        )
        return None

    # ========================================================================
    # ENHANCED CONTACT ENRICHMENT (Browserbase Scraping)
    # ========================================================================

    async def enrich_contact_from_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Enrich contact data by scraping LinkedIn profile.

        Uses Browserbase automation to extract rich profile data including:
        - Full name, headline, location
        - Current position and company
        - Work experience history
        - Education background
        - Skills and endorsements

        Args:
            profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)

        Returns:
            Enrichment data with profile details

        Example:
            enrichment = await provider.enrich_contact_from_profile(
                "https://linkedin.com/in/johndoe"
            )
        """
        try:
            profile_data = self.scraper.scrape_profile(profile_url)

            if profile_data.get('error'):
                logger.warning(f"Profile scraping failed: {profile_data.get('error')}")
                return None

            return {
                'source': 'linkedin_scraping',
                'profile_url': profile_url,
                'name': profile_data.get('name'),
                'headline': profile_data.get('headline'),
                'location': profile_data.get('location'),
                'current_company': profile_data.get('current_company'),
                'current_title': profile_data.get('current_title'),
                'experience': profile_data.get('experience', []),
                'education': profile_data.get('education', []),
                'skills': profile_data.get('skills', []),
                'connections': profile_data.get('connections'),
                'scraped_at': profile_data.get('scraped_at')
            }

        except Exception as e:
            logger.error(f"Profile enrichment error: {e}")
            return None

    async def discover_company_contacts(
        self,
        company_linkedin_url: str,
        job_titles: Optional[List[str]] = None,
        max_contacts: int = 50
    ) -> List[Contact]:
        """
        Discover contacts at a company using LinkedIn scraping.

        Uses Browserbase to scrape company employee directory and identify
        decision makers based on job titles.

        Args:
            company_linkedin_url: LinkedIn company page URL
            job_titles: Optional filter for specific titles (e.g., ["CEO", "CTO", "VP Sales"])
            max_contacts: Maximum number of contacts to return

        Returns:
            List of Contact objects with enriched data

        Example:
            contacts = await provider.discover_company_contacts(
                "https://linkedin.com/company/techcorp",
                job_titles=["CEO", "CTO", "VP"],
                max_contacts=25
            )
        """
        try:
            # Discover employees using scraper
            employees = self.scraper.discover_employees(
                company_linkedin_url,
                job_titles=job_titles,
                max_employees=max_contacts
            )

            contacts = []
            for emp in employees:
                # Map scraped data to Contact object
                contact = Contact(
                    email=f"unknown@{emp.get('profile_url', 'linkedin.com')}",  # Email not available
                    first_name=emp.get('name', '').split()[0] if emp.get('name') else '',
                    last_name=' '.join(emp.get('name', '').split()[1:]) if emp.get('name') else '',
                    title=emp.get('title'),
                    linkedin_url=emp.get('profile_url'),
                    external_ids={'linkedin_scraped': emp.get('profile_url')},
                    source_platform='linkedin',
                    enrichment_data={
                        'tenure': emp.get('tenure'),
                        'location': emp.get('location'),
                        'connections': emp.get('connections'),
                        'is_decision_maker': emp.get('is_decision_maker', False),
                        'scraped_at': emp.get('scraped_at')
                    },
                    last_synced_at=datetime.utcnow()
                )
                contacts.append(contact)

            logger.info(f"Discovered {len(contacts)} contacts from {company_linkedin_url}")
            return contacts

        except Exception as e:
            logger.error(f"Company contact discovery error: {e}")
            return []

    # ========================================================================
    # OUTREACH AUTOMATION (STUBBED - Requires LinkedIn Partnership)
    # ========================================================================

    async def send_connection_request(
        self,
        profile_url: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ⚠️ NOT SUPPORTED: Send LinkedIn connection request.

        LinkedIn's official API does not provide automated connection requests.

        Requires:
        - LinkedIn Marketing Developer Platform partnership, OR
        - Sales Navigator API access, OR
        - Third-party automation tool (e.g., PhantomBuster, Expandi)

        Args:
            profile_url: LinkedIn profile URL
            message: Optional connection request message

        Raises:
            CRMValidationError: Always - operation not supported without partnership

        Alternative Approaches:
        1. Apply for LinkedIn Marketing Developer Platform partnership
        2. Use LinkedIn Sales Navigator with approved automation
        3. Integrate third-party tools (PhantomBuster, Expandi, Dux-Soup)
        4. Manual outreach through LinkedIn interface
        """
        raise CRMValidationError(
            "LinkedIn API does not support automated connection requests. "
            "This requires LinkedIn Marketing Developer Platform partnership or "
            "Sales Navigator API access. Alternative: Use third-party automation "
            "tools (PhantomBuster, Expandi) or manual outreach.",
            context={
                'profile_url': profile_url,
                'feature': 'connection_requests',
                'requires_partnership': True,
                'alternatives': [
                    'LinkedIn Marketing Developer Platform',
                    'Sales Navigator API',
                    'PhantomBuster',
                    'Expandi',
                    'Manual outreach'
                ]
            }
        )

    async def send_message(
        self,
        recipient_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        ⚠️ NOT SUPPORTED: Send LinkedIn direct message.

        LinkedIn's official API does not provide automated messaging.

        Requires:
        - LinkedIn Sales Navigator with messaging API access, OR
        - Marketing Developer Platform partnership, OR
        - Third-party messaging automation tools

        Args:
            recipient_id: LinkedIn member ID or profile URL
            message: Message content

        Raises:
            CRMValidationError: Always - operation not supported without partnership

        Alternative Approaches:
        1. LinkedIn Sales Navigator with InMail API access
        2. Marketing Developer Platform partnership
        3. Third-party messaging tools (with caution - may violate ToS)
        4. Manual messaging through LinkedIn interface
        """
        raise CRMValidationError(
            "LinkedIn API does not support automated messaging. "
            "This requires Sales Navigator with InMail API access or "
            "Marketing Developer Platform partnership. Alternative: Use "
            "manual messaging through LinkedIn interface.",
            context={
                'recipient_id': recipient_id,
                'feature': 'direct_messaging',
                'requires_partnership': True,
                'alternatives': [
                    'Sales Navigator InMail API',
                    'Marketing Developer Platform',
                    'Manual messaging'
                ]
            }
        )

    async def get_connections(self, limit: int = 100) -> List[Contact]:
        """
        ⚠️ NOT SUPPORTED: Get authenticated user's LinkedIn connections.

        LinkedIn's official API provides limited connection access.

        Available:
        - First-degree connections count (via profile API)

        Not Available Without Partnership:
        - Full connection list
        - Connection details
        - Mutual connections

        Args:
            limit: Maximum connections to retrieve

        Raises:
            CRMValidationError: Always - operation not supported without partnership

        Alternative Approaches:
        1. Export connections manually from LinkedIn
        2. Use LinkedIn Sales Navigator
        3. Apply for API partnership for connection access
        """
        raise CRMValidationError(
            "LinkedIn API does not provide programmatic access to connections list. "
            "This requires LinkedIn partnership or Sales Navigator access. "
            "Alternative: Export connections manually from LinkedIn settings.",
            context={
                'feature': 'connections_list',
                'requires_partnership': True,
                'alternatives': [
                    'Manual CSV export from LinkedIn',
                    'Sales Navigator',
                    'LinkedIn Partnership Program'
                ]
            }
        )

    # ========================================================================
    # SYNC OPERATIONS (Required by CRMProvider)
    # ========================================================================

    async def sync_contacts(
        self,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Import contacts from LinkedIn using profile scraping.

        LinkedIn official API doesn't support bulk contact sync, but we can
        enrich contacts by scraping their LinkedIn profiles if profile URLs are provided.

        Args:
            direction: Must be "import" (LinkedIn enrichment only)
            filters: Required filters:
                - profile_urls: List[str] - List of LinkedIn profile URLs to scrape and enrich

        Returns:
            SyncResult with enrichment metrics

        Raises:
            CRMValidationError: If direction is not "import" or profile_urls not provided

        Example:
            filters = {
                "profile_urls": [
                    "https://www.linkedin.com/in/johndoe",
                    "https://www.linkedin.com/in/janedoe"
                ]
            }
            result = await provider.sync_contacts(direction="import", filters=filters)
        """
        started_at = datetime.utcnow()

        if direction != "import":
            raise CRMValidationError(
                f"LinkedIn only supports 'import' direction (enrichment only). Got: {direction}"
            )

        if not filters or not filters.get("profile_urls"):
            logger.warning(
                "LinkedIn sync requires 'profile_urls' list in filters. "
                "Returning empty result. "
                "Example: filters={'profile_urls': ['https://www.linkedin.com/in/johndoe']}"
            )
            return SyncResult(
                platform='linkedin',
                operation=direction,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_seconds=0
            )

        profile_urls = filters.get("profile_urls", [])
        if not isinstance(profile_urls, list):
            raise CRMValidationError("'profile_urls' filter must be a list of LinkedIn profile URLs")

        contacts_created = 0
        contacts_updated = 0
        contacts_failed = 0
        total_processed = 0
        errors_list = []

        logger.info(f"Starting LinkedIn profile enrichment for {len(profile_urls)} profiles")

        # Check rate limit before starting
        try:
            await self._check_rate_limit()
        except CRMRateLimitError as e:
            logger.error(f"LinkedIn rate limit exceeded before sync start: {e}")
            return SyncResult(
                platform='linkedin',
                operation=direction,
                contacts_processed=0,
                contacts_created=0,
                contacts_updated=0,
                contacts_failed=len(profile_urls),
                errors=[{"error": str(e), "all_profiles": "Rate limit exceeded"}],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )

        # Enrich each profile URL
        for profile_url in profile_urls:
            total_processed += 1

            try:
                # Use existing scraper-based enrichment method
                enrichment_result = await self.enrich_contact_from_profile(profile_url)

                if enrichment_result:
                    # Successfully enriched
                    contacts_created += 1
                    logger.debug(f"Enriched LinkedIn profile: {profile_url}")
                else:
                    # Profile scraping failed
                    contacts_failed += 1
                    errors_list.append({
                        "profile_url": profile_url,
                        "error": "Failed to scrape LinkedIn profile"
                    })
                    logger.debug(f"Failed to scrape profile: {profile_url}")

            except CRMRateLimitError as e:
                # Rate limit hit - stop processing
                contacts_failed += 1
                errors_list.append({
                    "profile_url": profile_url,
                    "error": f"Rate limit exceeded: {str(e)}"
                })
                logger.warning(f"LinkedIn rate limit exceeded at profile {total_processed}/{len(profile_urls)}")
                break

            except Exception as e:
                # Other error - log and continue
                contacts_failed += 1
                errors_list.append({
                    "profile_url": profile_url,
                    "error": str(e)
                })
                logger.error(f"Failed to enrich {profile_url}: {e}")

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        logger.info(
            f"LinkedIn sync completed: {contacts_created} enriched, "
            f"{contacts_failed} failed out of {total_processed} total in {duration:.2f}s"
        )

        return SyncResult(
            platform='linkedin',
            operation=direction,
            contacts_processed=total_processed,
            contacts_created=contacts_created,
            contacts_updated=contacts_updated,
            contacts_failed=contacts_failed,
            errors=errors_list,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration
        )

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
