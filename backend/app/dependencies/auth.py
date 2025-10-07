"""
Authentication and authorization dependencies for FastAPI endpoints.
"""
from typing import Optional, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.security import User
from app.services.auth import AuthService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Security scheme for JWT Bearer authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to extract and validate the current user from JWT token.

    Args:
        credentials: JWT Bearer token from Authorization header
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    auth_service = AuthService(db)

    # Extract token from credentials
    token = credentials.credentials

    # Get user from token
    user = auth_service.get_current_user(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure the current user is active.

    Args:
        current_user: Current authenticated user

    Returns:
        Current active user

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure the current user is a superuser.

    Args:
        current_user: Current authenticated user

    Returns:
        Current superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


class RoleChecker:
    """
    Dependency class to check if user has specific role(s).

    Usage:
        @router.get("/admin", dependencies=[Depends(RoleChecker(["admin"]))])
    """

    def __init__(self, allowed_roles: List[str]):
        """
        Initialize role checker with allowed roles.

        Args:
            allowed_roles: List of role names that are allowed access
        """
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
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
        # Superusers bypass role checks
        if current_user.is_superuser:
            return True

        # Check if user has any of the allowed roles
        user_roles = [role.name for role in current_user.roles]
        if any(role in self.allowed_roles for role in user_roles):
            return True

        logger.warning(
            f"Access denied for user {current_user.username}. "
            f"Required roles: {self.allowed_roles}, User roles: {user_roles}"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not enough permissions. Required role(s): {', '.join(self.allowed_roles)}",
        )


class PermissionChecker:
    """
    Dependency class to check if user has specific permission(s).

    Usage:
        @router.post("/leads", dependencies=[Depends(PermissionChecker(["write:leads"]))])
    """

    def __init__(self, required_permissions: List[str]):
        """
        Initialize permission checker with required permissions.

        Args:
            required_permissions: List of permission names required for access
        """
        self.required_permissions = required_permissions

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> bool:
        """
        Check if the current user has all required permissions.

        Args:
            current_user: Current authenticated user
            db: Database session

        Returns:
            True if user has all required permissions

        Raises:
            HTTPException: If user doesn't have required permissions
        """
        # Superusers bypass permission checks
        if current_user.is_superuser:
            return True

        auth_service = AuthService(db)

        # Check each required permission
        missing_permissions = []
        for permission in self.required_permissions:
            if not auth_service.check_permission(current_user, permission):
                missing_permissions.append(permission)

        if missing_permissions:
            logger.warning(
                f"Access denied for user {current_user.username}. "
                f"Missing permissions: {missing_permissions}"
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required: {', '.join(missing_permissions)}",
            )

        return True


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


def has_permission(permission: str):
    """
    Create a dependency to check for a single permission.

    Args:
        permission: Permission name to check (e.g., "write:leads")

    Returns:
        PermissionChecker dependency
    """
    return Depends(PermissionChecker([permission]))


def has_all_permissions(*permissions: str):
    """
    Create a dependency to check if user has all specified permissions.

    Args:
        *permissions: Permission names to check

    Returns:
        PermissionChecker dependency
    """
    return Depends(PermissionChecker(list(permissions)))


# Optional user dependency - doesn't require authentication
async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Dependency to optionally extract the current user from JWT token.
    Returns None if no valid token is provided.

    Args:
        credentials: Optional JWT Bearer token
        db: Database session

    Returns:
        Current user if authenticated, None otherwise
    """
    if not credentials:
        return None

    auth_service = AuthService(db)
    user = auth_service.get_current_user(credentials.credentials)

    # Return None instead of raising exception
    if not user or not user.is_active:
        return None

    return user