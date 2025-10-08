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
from .rate_limit import (
    get_rate_limiter,
    rate_limit_dependency,
    cleanup_rate_limiter,
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
    "get_rate_limiter",
    "rate_limit_dependency",
    "cleanup_rate_limiter",
]