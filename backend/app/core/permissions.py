"""
Permission-based access control (Part 2.3).
Define permissions and role->permissions matrix; use require_permission() in endpoints.
"""
from fastapi import Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models.user import User

# Permission constants (resource:action)
STATS_READ = "stats:read"
ALERTS_READ = "alerts:read"
ALERTS_READ_OWN = "alerts:read_own"
ALERTS_RESOLVE = "alerts:resolve"
AUDIT_READ = "audit:read"
EXPORT_READ = "export:read"
PURCHASES_READ_OWN = "purchases:read_own"
PURCHASES_READ_ALL = "purchases:read_all"
PURCHASES_CREATE = "purchases:create"
PURCHASES_CONFIRM = "purchases:confirm"
POLICIES_READ = "policies:read"
POLICIES_WRITE = "policies:write"
USERS_READ = "users:read"
USERS_WRITE = "users:write"
SETTINGS_READ = "settings:read"
SETTINGS_WRITE = "settings:write"

# Role -> set of permission strings
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "employee": {
        PURCHASES_READ_OWN,
        PURCHASES_CREATE,
        PURCHASES_CONFIRM,
        ALERTS_READ_OWN,
        POLICIES_READ,
    },
    "director": {
        STATS_READ,
        ALERTS_READ,
        ALERTS_RESOLVE,
        AUDIT_READ,
        EXPORT_READ,
        PURCHASES_READ_OWN,
        PURCHASES_READ_ALL,
        PURCHASES_CREATE,
        PURCHASES_CONFIRM,
        POLICIES_READ,
        SETTINGS_READ,
        USERS_READ,  # dashboard users-map
    },
    "accountant": {
        STATS_READ,
        ALERTS_READ,
        AUDIT_READ,
        EXPORT_READ,
        PURCHASES_READ_OWN,
        PURCHASES_READ_ALL,
        PURCHASES_CONFIRM,
        POLICIES_READ,
        SETTINGS_READ,
        USERS_READ,
    },
    "admin": {
        STATS_READ,
        ALERTS_READ,
        ALERTS_RESOLVE,
        AUDIT_READ,
        EXPORT_READ,
        PURCHASES_READ_OWN,
        PURCHASES_READ_ALL,
        PURCHASES_CREATE,
        PURCHASES_CONFIRM,
        POLICIES_READ,
        POLICIES_WRITE,
        USERS_READ,
        USERS_WRITE,
        SETTINGS_READ,
        SETTINGS_WRITE,
    },
}


def get_user_permissions(user: User) -> set[str]:
    """Return the set of permission strings for the user's role."""
    return ROLE_PERMISSIONS.get(user.role, set()).copy()


def require_permission(*permissions: str):
    """
    Dependency: current user must have at least one of the given permissions.
    Replaces role checks with permission checks (Part 2.3).
    """

    def _check(user: User = Depends(get_current_user)) -> User:
        user_perms = get_user_permissions(user)
        if not user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        if not any(p in user_perms for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {list(permissions)}",
            )
        return user

    return Depends(_check)
