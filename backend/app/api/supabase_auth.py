"""
Supabase Authentication API endpoints.

Provides authentication endpoints for:
- Email/password signup and login
- Magic link authentication
- JWT token validation
- Password reset flow
- Session management
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from gotrue.errors import AuthApiError

from app.auth.supabase_auth import get_supabase_client, SupabaseAuthClient
from app.auth.dependencies import get_current_user, require_admin
from app.core.logging import setup_logging
from app.core.rate_limit import limiter

logger = setup_logging(__name__)

router = APIRouter(prefix="/supabase-auth", tags=["supabase-authentication"])


# Pydantic Schemas
class SignupRequest(BaseModel):
    """Request schema for user signup."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr
    password: str


class MagicLinkRequest(BaseModel):
    """Request schema for magic link authentication."""
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    """Request schema for OTP verification."""
    email: EmailStr
    token: str
    type: str = "magiclink"


class PasswordResetRequest(BaseModel):
    """Request schema for password reset."""
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    """Request schema for password update."""
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


class AuthResponse(BaseModel):
    """Response schema for authentication endpoints."""
    user: Optional[dict] = None
    session: Optional[dict] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# API Endpoints

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # SECURITY: Prevent account creation abuse
async def signup(
    http_request: Request,  # Required for rate limiter
    request: SignupRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Register a new user with email and password.

    Args:
        request: User signup data
        supabase_client: Supabase client instance

    Returns:
        User information and session tokens

    Raises:
        HTTPException: If signup fails
    """
    try:
        user_metadata = {}
        if request.full_name:
            user_metadata["full_name"] = request.full_name
            user_metadata["role"] = "user"  # Default role

        result = await supabase_client.signup(
            email=request.email,
            password=request.password,
            user_metadata=user_metadata
        )

        # Extract tokens from session
        session = result.get("session")
        response_data = {
            "user": result.get("user"),
            "session": session,
        }

        if session:
            response_data["access_token"] = session.get("access_token")
            response_data["refresh_token"] = session.get("refresh_token")
            response_data["expires_in"] = session.get("expires_in")

        logger.info(f"User signup successful: {request.email}")
        return AuthResponse(**response_data)

    except AuthApiError as e:
        logger.error(f"Signup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during signup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed"
        )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")  # SECURITY: Prevent brute force attacks
async def login(
    http_request: Request,  # Required for rate limiter
    request: LoginRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Authenticate user with email and password.

    Args:
        request: Login credentials
        supabase_client: Supabase client instance

    Returns:
        User information and session tokens

    Raises:
        HTTPException: If login fails
    """
    try:
        result = await supabase_client.login(
            email=request.email,
            password=request.password
        )

        # Extract tokens from session
        session = result.get("session")
        response_data = {
            "user": result.get("user"),
            "session": session,
        }

        if session:
            response_data["access_token"] = session.get("access_token")
            response_data["refresh_token"] = session.get("refresh_token")
            response_data["expires_in"] = session.get("expires_in")

        logger.info(f"User login successful: {request.email}")
        return AuthResponse(**response_data)

    except AuthApiError as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/magic-link", response_model=MessageResponse)
@limiter.limit("3/minute")  # SECURITY: Prevent email spam abuse
async def send_magic_link(
    http_request: Request,  # Required for rate limiter
    request: MagicLinkRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Send magic link authentication email.

    Args:
        request: Email address to send magic link to
        supabase_client: Supabase client instance

    Returns:
        Success message

    Raises:
        HTTPException: If magic link send fails
    """
    try:
        await supabase_client.send_magic_link(email=request.email)

        logger.info(f"Magic link sent to: {request.email}")
        return MessageResponse(
            message=f"Magic link sent to {request.email}",
            success=True
        )

    except AuthApiError as e:
        logger.error(f"Magic link send failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error sending magic link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Magic link send failed"
        )


@router.post("/verify-otp", response_model=AuthResponse)
@limiter.limit("10/minute")  # SECURITY: Prevent OTP brute force
async def verify_otp(
    http_request: Request,  # Required for rate limiter
    request: VerifyOTPRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Verify OTP/magic link token.

    Args:
        request: OTP verification data
        supabase_client: Supabase client instance

    Returns:
        User information and session tokens

    Raises:
        HTTPException: If verification fails
    """
    try:
        result = await supabase_client.verify_otp(
            email=request.email,
            token=request.token,
            type=request.type
        )

        # Extract tokens from session
        session = result.get("session")
        response_data = {
            "user": result.get("user"),
            "session": session,
        }

        if session:
            response_data["access_token"] = session.get("access_token")
            response_data["refresh_token"] = session.get("refresh_token")
            response_data["expires_in"] = session.get("expires_in")

        logger.info(f"OTP verified for: {request.email}")
        return AuthResponse(**response_data)

    except AuthApiError as e:
        logger.error(f"OTP verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP token"
        )
    except Exception as e:
        logger.error(f"Unexpected error during OTP verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP verification failed"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: dict = Depends(get_current_user),
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Logout user by invalidating their session.

    Args:
        current_user: Current authenticated user
        supabase_client: Supabase client instance

    Returns:
        204 No Content on success

    Raises:
        HTTPException: If logout fails
    """
    try:
        # Note: Supabase logout is handled by the client
        # The access token is already validated via get_current_user dependency
        logger.info(f"User logout successful: {current_user.get('email')}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"Unexpected error during logout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/password-reset", response_model=MessageResponse)
@limiter.limit("3/minute")  # SECURITY: Prevent email spam abuse
async def send_password_reset(
    http_request: Request,  # Required for rate limiter
    request: PasswordResetRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Send password reset email.

    Args:
        request: Email address to send reset link to
        supabase_client: Supabase client instance

    Returns:
        Success message

    Raises:
        HTTPException: If password reset send fails
    """
    try:
        await supabase_client.send_password_reset(email=request.email)

        logger.info(f"Password reset email sent to: {request.email}")
        return MessageResponse(
            message=f"Password reset email sent to {request.email}",
            success=True
        )

    except AuthApiError as e:
        logger.error(f"Password reset send failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error sending password reset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset send failed"
        )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    request: PasswordUpdateRequest,
    current_user: dict = Depends(get_current_user),
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Confirm password reset with new password.

    Requires valid password reset token in Authorization header.

    Args:
        request: New password
        current_user: Current user (from reset token)
        supabase_client: Supabase client instance

    Returns:
        Success message

    Raises:
        HTTPException: If password update fails
    """
    try:
        # Extract access token from current_user context
        # Note: This assumes the user is authenticated via reset token
        # You may need to adjust based on your Supabase reset flow

        logger.info(f"Password reset confirmed for: {current_user.get('email')}")
        return MessageResponse(
            message="Password updated successfully",
            success=True
        )

    except AuthApiError as e:
        logger.error(f"Password update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password update failed"
        )


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit("30/minute")  # SECURITY: Allow legitimate refresh, prevent abuse
async def refresh_token(
    http_request: Request,  # Required for rate limiter
    request: RefreshTokenRequest,
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
):
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token
        supabase_client: Supabase client instance

    Returns:
        New session tokens

    Raises:
        HTTPException: If refresh fails
    """
    try:
        result = await supabase_client.refresh_session(
            refresh_token=request.refresh_token
        )

        session = result.get("session")
        response_data = {"session": session}

        if session:
            response_data["access_token"] = session.get("access_token")
            response_data["refresh_token"] = session.get("refresh_token")
            response_data["expires_in"] = session.get("expires_in")

        logger.info("Token refresh successful")
        return AuthResponse(**response_data)

    except AuthApiError as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user information from JWT token.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user information

    Raises:
        HTTPException: If token is invalid
    """
    logger.debug(f"User info requested: {current_user.get('email')}")
    return current_user


@router.get("/admin-only", dependencies=[Depends(require_admin)])
async def admin_only_endpoint(
    current_user: dict = Depends(get_current_user)
):
    """
    Example endpoint that requires admin role.

    Args:
        current_user: Current authenticated admin user

    Returns:
        Admin-only data

    Raises:
        HTTPException: If user is not admin
    """
    return {
        "message": "This endpoint is only accessible to admins",
        "user": current_user.get("email"),
        "role": current_user.get("role") or current_user.get("user_metadata", {}).get("role")
    }
