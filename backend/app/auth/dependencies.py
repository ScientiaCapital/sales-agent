"""
FastAPI dependencies for Supabase authentication.

Provides dependency injection for:
- Current user extraction from JWT
- Role-based access control (admin, user)
- Permission checking
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.supabase_auth import get_supabase_client, SupabaseAuthClient
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Security scheme for JWT Bearer authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
) -> dict:
    """
    Dependency to extract and validate the current user from Supabase JWT token.

    Args:
        credentials: JWT Bearer token from Authorization header
        supabase_client: Supabase client instance

    Returns:
        Current authenticated user data

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Get user from Supabase token
    user = await supabase_client.get_user_from_token(token)

    if not user:
        logger.warning("Invalid or expired JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active (if you have a banned/disabled field)
    if user.get("banned", False):
        logger.warning(f"Access denied for banned user: {user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    logger.debug(f"User authenticated: {user.get('email')}")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    supabase_client: SupabaseAuthClient = Depends(get_supabase_client)
) -> Optional[dict]:
    """
    Dependency to optionally extract the current user from JWT token.
    Returns None if no valid token is provided.

    Args:
        credentials: Optional JWT Bearer token
        supabase_client: Supabase client instance

    Returns:
        Current user if authenticated, None otherwise
    """
    if not credentials:
        return None

    token = credentials.credentials
    user = await supabase_client.get_user_from_token(token)

    if not user or user.get("banned", False):
        return None

    return user


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to ensure the current user has admin role.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not an admin
    """
    # Check user metadata for admin role
    user_metadata = current_user.get("user_metadata", {})
    role = current_user.get("role") or user_metadata.get("role", "user")

    if role != "admin":
        logger.warning(
            f"Access denied for user {current_user.get('email')}: "
            f"requires admin role, has {role}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin role required.",
        )

    return current_user


async def require_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to ensure the user is authenticated (has user or admin role).

    Args:
        current_user: Current authenticated user

    Returns:
        Current user if authenticated

    Raises:
        HTTPException: If user is not authenticated
    """
    # Check user metadata for role
    user_metadata = current_user.get("user_metadata", {})
    role = current_user.get("role") or user_metadata.get("role", "user")

    if role not in ["user", "admin"]:
        logger.warning(
            f"Access denied for user {current_user.get('email')}: "
            f"invalid role {role}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. User role required.",
        )

    return current_user


class RoleChecker:
    """
    Dependency class to check if user has specific role(s).

    Usage:
        @router.get("/admin", dependencies=[Depends(RoleChecker(["admin"]))])
    """

    def __init__(self, allowed_roles: list[str]):
        """
        Initialize role checker with allowed roles.

        Args:
            allowed_roles: List of role names that are allowed access
        """
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: dict = Depends(get_current_user),
    ) -> bool:
        """
        Check if the current user has any of the allowed roles.

        Args:
            current_user: Current authenticated user

        Returns:
            True if user has required role

        Raises:
            HTTPException: If user doesn't have required role
        """
        user_metadata = current_user.get("user_metadata", {})
        user_role = current_user.get("role") or user_metadata.get("role", "user")

        if user_role in self.allowed_roles:
            return True

        logger.warning(
            f"Access denied for user {current_user.get('email')}. "
            f"Required roles: {self.allowed_roles}, User role: {user_role}"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not enough permissions. Required role(s): {', '.join(self.allowed_roles)}",
        )


# Convenience functions for common role checks
def has_role(role: str):
    """
    Create a dependency to check for a single role.

    Args:
        role: Role name to check

    Returns:
        RoleChecker dependency
    """
    return Depends(RoleChecker([role]))


def has_any_role(*roles: str):
    """
    Create a dependency to check if user has any of the specified roles.

    Args:
        *roles: Role names to check

    Returns:
        RoleChecker dependency
    """
    return Depends(RoleChecker(list(roles)))
