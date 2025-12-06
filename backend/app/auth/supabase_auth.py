"""
Supabase authentication client wrapper for sales-agent.

This module provides async Supabase authentication methods including:
- Email/password signup and login
- Magic link authentication
- JWT token validation
- Password reset flows
- Session management
"""

from typing import Optional, Dict, Any
from functools import lru_cache
import jwt
from supabase import create_client, Client
from gotrue.errors import AuthApiError

from app.core.config import settings
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class SupabaseAuthClient:
    """
    Wrapper around Supabase client for authentication operations.

    Provides methods for:
    - User signup and login
    - Magic link authentication
    - JWT token validation
    - Password reset
    - Session management
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (anon or service key)
        """
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and key are required")

        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")

    async def signup(
        self,
        email: str,
        password: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a new user with email and password.

        Args:
            email: User's email address
            password: User's password
            user_metadata: Optional metadata (full_name, etc.)

        Returns:
            Dict containing user data and session info

        Raises:
            AuthApiError: If signup fails
        """
        try:
            options = {}
            if user_metadata:
                options["data"] = user_metadata

            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": options
            })

            logger.info(f"User signup successful: {email}")
            return {
                "user": response.user.model_dump() if response.user else None,
                "session": response.session.model_dump() if response.session else None
            }

        except AuthApiError as e:
            logger.error(f"Signup failed for {email}: {e}")
            raise

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Dict containing user data and session info

        Raises:
            AuthApiError: If login fails
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            logger.info(f"User login successful: {email}")
            return {
                "user": response.user.model_dump() if response.user else None,
                "session": response.session.model_dump() if response.session else None
            }

        except AuthApiError as e:
            logger.error(f"Login failed for {email}: {e}")
            raise

    async def send_magic_link(self, email: str) -> Dict[str, Any]:
        """
        Send magic link authentication email.

        Args:
            email: User's email address

        Returns:
            Dict with success status

        Raises:
            AuthApiError: If magic link send fails
        """
        try:
            response = self.client.auth.sign_in_with_otp({
                "email": email
            })

            logger.info(f"Magic link sent to: {email}")
            return {"success": True, "email": email}

        except AuthApiError as e:
            logger.error(f"Magic link send failed for {email}: {e}")
            raise

    async def verify_otp(self, email: str, token: str, type: str = "magiclink") -> Dict[str, Any]:
        """
        Verify OTP/magic link token.

        Args:
            email: User's email address
            token: OTP token from email
            type: Token type (magiclink, signup, recovery)

        Returns:
            Dict containing user data and session info

        Raises:
            AuthApiError: If verification fails
        """
        try:
            response = self.client.auth.verify_otp({
                "email": email,
                "token": token,
                "type": type
            })

            logger.info(f"OTP verified for: {email}")
            return {
                "user": response.user.model_dump() if response.user else None,
                "session": response.session.model_dump() if response.session else None
            }

        except AuthApiError as e:
            logger.error(f"OTP verification failed for {email}: {e}")
            raise

    async def logout(self, access_token: str) -> Dict[str, Any]:
        """
        Sign out user by invalidating their session.

        Args:
            access_token: User's access token

        Returns:
            Dict with success status

        Raises:
            AuthApiError: If logout fails
        """
        try:
            # Set the session token for this operation
            self.client.auth.set_session(access_token, "")
            self.client.auth.sign_out()

            logger.info("User logout successful")
            return {"success": True}

        except AuthApiError as e:
            logger.error(f"Logout failed: {e}")
            raise

    async def send_password_reset(self, email: str) -> Dict[str, Any]:
        """
        Send password reset email.

        Args:
            email: User's email address

        Returns:
            Dict with success status

        Raises:
            AuthApiError: If password reset send fails
        """
        try:
            self.client.auth.reset_password_email(email)

            logger.info(f"Password reset email sent to: {email}")
            return {"success": True, "email": email}

        except AuthApiError as e:
            logger.error(f"Password reset send failed for {email}: {e}")
            raise

    async def update_password(self, access_token: str, new_password: str) -> Dict[str, Any]:
        """
        Update user's password.

        Args:
            access_token: User's access token
            new_password: New password

        Returns:
            Dict containing updated user data

        Raises:
            AuthApiError: If password update fails
        """
        try:
            # Set the session token for this operation
            self.client.auth.set_session(access_token, "")
            response = self.client.auth.update_user({
                "password": new_password
            })

            logger.info("Password update successful")
            return {
                "user": response.user.model_dump() if response.user else None
            }

        except AuthApiError as e:
            logger.error(f"Password update failed: {e}")
            raise

    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: User's refresh token

        Returns:
            Dict containing new session info

        Raises:
            AuthApiError: If refresh fails
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)

            logger.info("Session refresh successful")
            return {
                "session": response.session.model_dump() if response.session else None
            }

        except AuthApiError as e:
            logger.error(f"Session refresh failed: {e}")
            raise

    async def get_user_from_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from access token.

        Args:
            access_token: User's access token

        Returns:
            User data dict or None if invalid

        Raises:
            AuthApiError: If user fetch fails
        """
        try:
            # Set the session token for this operation
            self.client.auth.set_session(access_token, "")
            response = self.client.auth.get_user()

            if response.user:
                logger.debug(f"User fetched from token: {response.user.email}")
                return response.user.model_dump()
            return None

        except AuthApiError as e:
            logger.error(f"Get user from token failed: {e}")
            return None

    def validate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate Supabase JWT token without API call.

        Args:
            token: JWT token to validate

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            # Decode JWT (Supabase uses HS256 by default)
            # Note: You need to get the JWT secret from your Supabase project settings
            if not settings.SUPABASE_JWT_SECRET:
                logger.warning("SUPABASE_JWT_SECRET not configured, using get_user_from_token instead")
                return None

            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )

            logger.debug(f"JWT validated for user: {payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT validation failed: Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT validation failed: {e}")
            return None


@lru_cache()
def get_supabase_client() -> SupabaseAuthClient:
    """
    Get cached Supabase client instance.

    Returns:
        SupabaseAuthClient instance

    Raises:
        ValueError: If Supabase credentials not configured
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise ValueError(
            "Supabase credentials not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
        )

    return SupabaseAuthClient(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY
    )
