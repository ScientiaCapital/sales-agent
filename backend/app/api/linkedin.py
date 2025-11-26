"""
LinkedIn OAuth 2.0 API Endpoints

FastAPI endpoints for LinkedIn OAuth authentication flow and profile access.

Endpoints:
- GET /linkedin/authorize - Generate OAuth authorization URL
- GET /linkedin/callback - Handle OAuth callback and exchange code for tokens
- POST /linkedin/refresh - Refresh access token (if refresh token available)
- GET /linkedin/profile - Get authenticated user profile
- GET /linkedin/email - Get authenticated user email
- GET /linkedin/rate-limit - Check current rate limit status
- GET /linkedin/token-status - Check token expiration and refresh availability
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import logging

from app.services.crm import LinkedInProvider, CRMCredentials, CRMAuthenticationError, CRMRateLimitError
from app.services.linkedin_credentials import LinkedInCredentialService, get_linkedin_credential_service
from app.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn OAuth"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class AuthorizeResponse(BaseModel):
    """Response from /authorize endpoint"""
    authorization_url: str = Field(..., description="URL to redirect user for OAuth consent")
    state: str = Field(..., description="State parameter for CSRF protection")
    expires_in: int = Field(600, description="State validity in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?...",
                "state": "abc123...",
                "expires_in": 600
            }
        }


class TokenResponse(BaseModel):
    """Response from token exchange"""
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Token validity in seconds")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    refresh_token_available: bool = Field(..., description="Whether refresh token was provided")
    scope: Optional[str] = Field(None, description="Granted scopes")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "AQX...",
                "token_type": "Bearer",
                "expires_in": 5184000,
                "expires_at": "2024-03-15T10:00:00Z",
                "refresh_token_available": True,
                "scope": "r_liteprofile r_emailaddress"
            }
        }


class ProfileResponse(BaseModel):
    """LinkedIn profile response"""
    id: str = Field(..., description="LinkedIn member ID")
    first_name: str = Field(..., description="First name (localized)")
    last_name: str = Field(..., description="Last name (localized)")
    profile_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    raw_data: Dict[str, Any] = Field(..., description="Raw API response")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "first_name": "John",
                "last_name": "Doe",
                "profile_url": "https://linkedin.com/in/johndoe",
                "raw_data": {"id": "abc123", "localizedFirstName": "John"}
            }
        }


class EmailResponse(BaseModel):
    """LinkedIn email response"""
    email: str = Field(..., description="Primary email address")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com"
            }
        }


class RateLimitResponse(BaseModel):
    """Rate limit status"""
    remaining: int = Field(..., description="Remaining requests")
    limit: int = Field(..., description="Total daily limit")
    reset_at: Optional[datetime] = Field(None, description="When limit resets")
    retry_after: int = Field(0, description="Seconds to wait if throttled")
    requests_today: int = Field(0, description="Requests made today")

    class Config:
        json_schema_extra = {
            "example": {
                "remaining": 85,
                "limit": 100,
                "reset_at": "2024-01-16T00:00:00Z",
                "retry_after": 0,
                "requests_today": 15
            }
        }


class TokenStatusResponse(BaseModel):
    """Token expiration status"""
    has_access_token: bool = Field(..., description="Whether access token exists")
    has_refresh_token: bool = Field(..., description="Whether refresh token exists")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    is_expired: bool = Field(..., description="Whether token is expired")
    days_until_expiry: Optional[float] = Field(None, description="Days until token expires")
    requires_reauth: bool = Field(..., description="Whether re-authentication is needed")

    class Config:
        json_schema_extra = {
            "example": {
                "has_access_token": True,
                "has_refresh_token": False,
                "expires_at": "2024-03-15T10:00:00Z",
                "is_expired": False,
                "days_until_expiry": 45.5,
                "requires_reauth": False
            }
        }


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================


def get_linkedin_config() -> Dict[str, str]:
    """Get LinkedIn OAuth configuration from environment variables"""
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8001/api/v1/linkedin/callback")

    if not client_id or not client_secret:
        raise ConfigurationError(
            "LinkedIn OAuth credentials not configured. "
            "Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env file."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }


def get_redis_client():
    """Get Redis client for rate limiting (optional)."""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url)
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None


def get_linkedin_provider(
    config: Dict[str, str] = Depends(get_linkedin_config)
) -> LinkedInProvider:
    """
    Create LinkedIn provider instance.

    Note: This creates a provider without stored credentials.
    For endpoints requiring authentication, credentials should be loaded from database.
    """
    credentials = CRMCredentials(platform="linkedin")

    return LinkedInProvider(
        credentials=credentials,
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        redis_client=get_redis_client()
    )


# ============================================================================
# OAUTH FLOW ENDPOINTS
# ============================================================================


@router.get("/authorize", response_model=AuthorizeResponse, status_code=200)
async def authorize(
    scopes: str = Query(
        "r_liteprofile r_emailaddress",
        description="Space-separated OAuth scopes",
        example="r_liteprofile r_emailaddress w_member_social"
    ),
    user_id: Optional[str] = Query(None, description="User ID to associate with OAuth flow"),
    redirect_after: Optional[str] = Query(None, description="URL to redirect after OAuth completes"),
    provider: LinkedInProvider = Depends(get_linkedin_provider),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> AuthorizeResponse:
    """
    Generate LinkedIn OAuth authorization URL.

    This endpoint initiates the OAuth 2.0 flow by generating an authorization URL
    with PKCE (code challenge) and state parameter for CSRF protection.

    **Flow:**
    1. Call this endpoint to get authorization URL
    2. Redirect user to authorization URL
    3. User grants consent on LinkedIn
    4. LinkedIn redirects to callback URL with code and state
    5. Call /callback endpoint to exchange code for tokens

    **Scopes:**
    - `r_liteprofile`: Basic profile info (id, name, photo)
    - `r_emailaddress`: Email address
    - `w_member_social`: Share content on behalf of user

    **Security:**
    - State parameter stored in Redis (10 min TTL) for CSRF protection
    - PKCE code_verifier stored for callback verification
    - Returns state to client for callback verification

    Args:
        scopes: Space-separated list of OAuth scopes

    Returns:
        Authorization URL and state parameter

    Example:
        ```
        GET /api/linkedin/authorize?scopes=r_liteprofile r_emailaddress

        Response:
        {
          "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?...",
          "state": "abc123...",
          "expires_in": 600
        }
        ```
    """
    try:
        scope_list = scopes.split()

        auth_url, code_verifier, state = provider.generate_authorization_url(scope_list)

        # Store OAuth state in Supabase for callback verification
        await cred_service.create_oauth_state(
            redirect_after=redirect_after,
            user_id=user_id
        )

        logger.info(f"Generated LinkedIn authorization URL with scopes: {scope_list}")

        return AuthorizeResponse(
            authorization_url=auth_url,
            state=state,
            expires_in=600  # 10 minutes
        )

    except Exception as e:
        logger.error(f"Failed to generate authorization URL: {e}")
        raise HTTPException(status_code=500, detail=f"Authorization URL generation failed: {str(e)}")


@router.get("/callback", response_model=TokenResponse, status_code=200)
async def callback(
    code: str = Query(..., description="Authorization code from LinkedIn"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    provider: LinkedInProvider = Depends(get_linkedin_provider),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> TokenResponse:
    """
    Handle OAuth callback and exchange authorization code for tokens.

    This endpoint receives the authorization code from LinkedIn's redirect
    and exchanges it for access and refresh tokens.

    **Flow:**
    1. User grants consent on LinkedIn
    2. LinkedIn redirects to this endpoint with code and state
    3. Verify state parameter (CSRF protection)
    4. Exchange code for tokens using PKCE code_verifier
    5. Store tokens in database (encrypted)
    6. Return token information

    **Token Validity:**
    - Access tokens: 60 days (standard) or 1 year (compliance API)
    - Refresh tokens: May not be provided for all API types
    - If no refresh token, re-authentication required after expiry

    Args:
        code: Authorization code from OAuth callback
        state: State parameter for verification

    Returns:
        Access token and metadata

    Raises:
        HTTPException: If code exchange fails or state verification fails

    Example:
        ```
        GET /api/linkedin/callback?code=AQT...&state=abc123

        Response:
        {
          "access_token": "AQX...",
          "token_type": "Bearer",
          "expires_in": 5184000,
          "expires_at": "2024-03-15T10:00:00Z",
          "refresh_token_available": true,
          "scope": "r_liteprofile r_emailaddress"
        }
        ```
    """
    try:
        # Validate and consume OAuth state from Supabase
        state_data = await cred_service.validate_and_consume_state(state)
        if not state_data:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired state parameter - possible CSRF attack"
            )

        user_id = state_data.get("user_id") or "default"

        # Exchange code for tokens
        token_data = await provider.exchange_code_for_token(
            authorization_code=code,
            code_verifier="",  # Retrieved from Redis in the provider
            state=state
        )

        # Store credentials in Supabase
        await cred_service.store_credentials(
            user_id=user_id,
            access_token=token_data['access_token'],
            expires_in=token_data.get('expires_in', 5184000),
            scope=token_data.get('scope')
        )

        logger.info(
            f"LinkedIn OAuth callback successful - "
            f"token expires at {provider.credentials.token_expires_at}"
        )

        return TokenResponse(
            access_token=token_data['access_token'],
            token_type='Bearer',
            expires_in=token_data.get('expires_in', 5184000),  # 60 days default
            expires_at=provider.credentials.token_expires_at,
            refresh_token_available='refresh_token' in token_data,
            scope=token_data.get('scope')
        )

    except CRMAuthenticationError as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")


@router.post("/refresh", response_model=TokenResponse, status_code=200)
async def refresh_token(
    user_id: str = Query("default", description="User ID to refresh token for"),
    provider: LinkedInProvider = Depends(get_linkedin_provider),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    **Important:** LinkedIn may not provide refresh tokens for all API types.
    If no refresh token is available, this endpoint will return an error
    indicating that re-authentication is required.

    **Token Refresh:**
    - Only works if LinkedIn provided a refresh token during initial auth
    - Refresh tokens are valid for 1 year
    - New access token valid for 60 days
    - If refresh fails, re-authentication required

    Returns:
        New access token and metadata

    Raises:
        HTTPException 401: If no refresh token available or refresh fails
        HTTPException 500: If refresh operation fails

    Example:
        ```
        POST /api/linkedin/refresh

        Response (Success):
        {
          "access_token": "AQY...",
          "token_type": "Bearer",
          "expires_in": 5184000,
          "expires_at": "2024-05-15T10:00:00Z",
          "refresh_token_available": true
        }

        Response (No Refresh Token):
        {
          "detail": "No refresh token available - LinkedIn did not provide refresh capability. Please re-authenticate via OAuth flow."
        }
        ```
    """
    try:
        # Load credentials from Supabase
        creds = await cred_service.get_credentials(user_id)
        if not creds:
            raise HTTPException(
                status_code=401,
                detail="No credentials found for user - please authenticate via OAuth first"
            )

        # Set access token on provider for refresh
        provider.access_token = creds.get("access_token")
        provider.credentials.access_token = provider.encrypt_credential(provider.access_token)

        new_access_token = await provider.refresh_access_token()

        # Update credentials in Supabase
        await cred_service.update_credentials(
            user_id=user_id,
            access_token=new_access_token,
            expires_in=5184000  # 60 days
        )

        logger.info("LinkedIn access token refreshed successfully")

        return TokenResponse(
            access_token=new_access_token,
            token_type='Bearer',
            expires_in=5184000,  # 60 days
            expires_at=provider.credentials.token_expires_at,
            refresh_token_available=provider.credentials.refresh_token is not None
        )

    except CRMAuthenticationError as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error refreshing token: {e}")
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


# ============================================================================
# PROFILE API ENDPOINTS
# ============================================================================


@router.get("/profile", response_model=ProfileResponse, status_code=200)
async def get_profile(
    user_id: str = Query("default", description="User ID to get profile for"),
    provider: LinkedInProvider = Depends(get_linkedin_provider),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> ProfileResponse:
    """
    Get authenticated user's LinkedIn profile.

    Requires:
    - Valid access token
    - Scope: `r_liteprofile`

    Returns:
        Profile data including id, name, and raw API response

    Raises:
        HTTPException 401: If not authenticated or token expired
        HTTPException 429: If rate limit exceeded (100 requests/day)

    Example:
        ```
        GET /api/linkedin/profile
        Authorization: Bearer {access_token}

        Response:
        {
          "id": "abc123",
          "first_name": "John",
          "last_name": "Doe",
          "profile_url": "https://linkedin.com/in/johndoe",
          "raw_data": {
            "id": "abc123",
            "localizedFirstName": "John",
            "localizedLastName": "Doe"
          }
        }
        ```
    """
    try:
        # Load credentials from Supabase
        creds = await cred_service.get_credentials(user_id)
        if not creds:
            raise HTTPException(
                status_code=401,
                detail="No credentials found - please authenticate via OAuth first"
            )

        # Set access token on provider
        provider.access_token = creds.get("access_token")

        profile_data = await provider.get_profile()

        member_id = profile_data.get('id', 'unknown')
        first_name = profile_data.get('localizedFirstName', '')
        last_name = profile_data.get('localizedLastName', '')

        return ProfileResponse(
            id=member_id,
            first_name=first_name,
            last_name=last_name,
            profile_url=f"https://linkedin.com/in/{member_id}",
            raw_data=profile_data
        )

    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except CRMRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch profile: {e}")
        raise HTTPException(status_code=500, detail=f"Profile fetch failed: {str(e)}")


@router.get("/email", response_model=EmailResponse, status_code=200)
async def get_email(
    user_id: str = Query("default", description="User ID to get email for"),
    provider: LinkedInProvider = Depends(get_linkedin_provider),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> EmailResponse:
    """
    Get authenticated user's email address.

    Requires:
    - Valid access token
    - Scope: `r_emailaddress`

    Returns:
        Primary email address

    Raises:
        HTTPException 401: If not authenticated or missing scope
        HTTPException 429: If rate limit exceeded

    Example:
        ```
        GET /api/linkedin/email
        Authorization: Bearer {access_token}

        Response:
        {
          "email": "john.doe@example.com"
        }
        ```
    """
    try:
        # Load credentials from Supabase
        creds = await cred_service.get_credentials(user_id)
        if not creds:
            raise HTTPException(
                status_code=401,
                detail="No credentials found - please authenticate via OAuth first"
            )

        # Set access token on provider
        provider.access_token = creds.get("access_token")

        email = await provider.get_email_address()

        if not email:
            raise HTTPException(
                status_code=404,
                detail="Email address not available - check r_emailaddress scope"
            )

        return EmailResponse(email=email)

    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except CRMRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch email: {e}")
        raise HTTPException(status_code=500, detail=f"Email fetch failed: {str(e)}")


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================


@router.get("/rate-limit", response_model=RateLimitResponse, status_code=200)
async def rate_limit_status(
    provider: LinkedInProvider = Depends(get_linkedin_provider)
) -> RateLimitResponse:
    """
    Check current rate limit status.

    LinkedIn basic tier allows 100 requests per day.
    This endpoint helps track usage and avoid hitting limits.

    Returns:
        Rate limit information

    Example:
        ```
        GET /api/linkedin/rate-limit

        Response:
        {
          "remaining": 85,
          "limit": 100,
          "reset_at": "2024-01-16T00:00:00Z",
          "retry_after": 0,
          "requests_today": 15
        }
        ```
    """
    try:
        rate_limit_info = await provider.check_rate_limit()

        return RateLimitResponse(**rate_limit_info)

    except Exception as e:
        logger.error(f"Failed to check rate limit: {e}")
        raise HTTPException(status_code=500, detail=f"Rate limit check failed: {str(e)}")


@router.get("/token-status", response_model=TokenStatusResponse, status_code=200)
async def token_status(
    user_id: str = Query("default", description="User ID to check token status for"),
    cred_service: LinkedInCredentialService = Depends(get_linkedin_credential_service)
) -> TokenStatusResponse:
    """
    Check token expiration status and refresh availability.

    Useful for determining:
    - Whether token is still valid
    - How much time until expiration
    - Whether refresh is possible
    - If re-authentication is needed

    Returns:
        Token status information

    Example:
        ```
        GET /api/linkedin/token-status

        Response:
        {
          "has_access_token": true,
          "has_refresh_token": false,
          "expires_at": "2024-03-15T10:00:00Z",
          "is_expired": false,
          "days_until_expiry": 45.5,
          "requires_reauth": false
        }
        ```
    """
    try:
        # Load credentials from Supabase
        creds = await cred_service.get_credentials(user_id)

        has_access = creds is not None and creds.get("access_token") is not None
        has_refresh = False  # LinkedIn typically doesn't provide refresh tokens
        expires_at = None
        is_expired = True
        days_until_expiry = None
        requires_reauth = True

        if creds and creds.get("expires_at"):
            expires_at_str = creds["expires_at"]
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            is_expired = expires_at <= datetime.utcnow()

            if not is_expired:
                time_until_expiry = expires_at - datetime.utcnow()
                days_until_expiry = time_until_expiry.total_seconds() / 86400
                requires_reauth = False
            else:
                requires_reauth = True  # Need reauth if expired

        return TokenStatusResponse(
            has_access_token=has_access,
            has_refresh_token=has_refresh,
            expires_at=expires_at,
            is_expired=is_expired,
            days_until_expiry=days_until_expiry,
            requires_reauth=requires_reauth
        )

    except Exception as e:
        logger.error(f"Failed to check token status: {e}")
        raise HTTPException(status_code=500, detail=f"Token status check failed: {str(e)}")
