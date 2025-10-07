"""
Application dependencies for FastAPI.
"""
from .auth import (
    get_current_user,
    get_current_active_user,
    get_current_superuser,
    get_optional_current_user,
    RoleChecker,
    PermissionChecker,
    has_role,
    has_any_role,
    has_permission,
    has_all_permissions,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
    "get_optional_current_user",
    "RoleChecker",
    "PermissionChecker",
    "has_role",
    "has_any_role",
    "has_permission",
    "has_all_permissions",
]