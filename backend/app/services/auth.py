"""
Authentication and authorization service for JWT token management and user authentication.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

import jwt
from jwt import PyJWTError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.orm import Session

from app.models.security import User, Role, Permission
from app.core.logging import setup_logging
from app.core.exceptions import APIAuthenticationError

logger = setup_logging(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # Generate a secure default for development (should be overridden in production)
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("JWT_SECRET_KEY not set in environment, using generated key (NOT FOR PRODUCTION)")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing configuration
password_hash = PasswordHash((BcryptHasher(),))  # Uses bcrypt explicitly


class AuthService:
    """
    Service for handling authentication and authorization operations.
    """

    def __init__(self, db: Session):
        """
        Initialize the authentication service.

        Args:
            db: Database session
        """
        self.db = db

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role_names: Optional[List[str]] = None,
    ) -> User:
        """
        Create a new user account with hashed password.

        Args:
            username: Unique username
            email: User's email address
            password: Plain text password to hash
            full_name: User's full name
            role_names: List of role names to assign

        Returns:
            Created user object

        Raises:
            ValueError: If username or email already exists
        """
        # Check for existing user
        existing_user = self.db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            if existing_user.username == username:
                raise ValueError(f"Username '{username}' already exists")
            else:
                raise ValueError(f"Email '{email}' already exists")

        # Hash the password
        hashed_password = password_hash.hash(password)

        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
        )

        # Assign roles if provided
        if role_names:
            roles = self.db.query(Role).filter(Role.name.in_(role_names)).all()
            user.roles = roles

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"Created new user: {username} (ID: {user.id})")
        return user

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username/email and password.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        # Find user by username or email
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            logger.warning(f"Authentication failed: User not found for '{username}'")
            return None

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            logger.warning(f"Authentication failed: Account locked for user '{username}'")
            return None

        # Verify password
        try:
            password_hash.verify(password, user.hashed_password)
        except Exception:
            # Password verification failed
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                logger.warning(f"Account locked due to failed attempts: {username}")

            self.db.commit()
            logger.warning(f"Authentication failed: Invalid password for '{username}'")
            return None

        # Check if password needs rehashing (algorithm upgrade)
        if password_hash.needs_rehash(user.hashed_password):
            user.hashed_password = password_hash.hash(password)
            logger.info(f"Password rehashed for user '{username}'")

        # Reset failed attempts and update login info
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info(f"User authenticated successfully: {username}")
        return user

    def create_access_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token for a user.

        Args:
            user: User object
            expires_delta: Custom expiration time

        Returns:
            JWT token string
        """
        # Set expiration time
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        # Prepare token payload
        payload = {
            "sub": str(user.id),  # Subject (user ID)
            "username": user.username,
            "email": user.email,
            "roles": [role.name for role in user.roles],
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }

        # Create token
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        logger.debug(f"Created access token for user {user.username}")
        return token

    def create_refresh_token(self, user: User) -> str:
        """
        Create a JWT refresh token for a user.

        Args:
            user: User object

        Returns:
            JWT refresh token string
        """
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        # Prepare token payload
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "version": user.refresh_token_version,  # Token version for revocation
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
        }

        # Create token
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        logger.debug(f"Created refresh token for user {user.username}")
        return token

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            token_type: Expected token type ("access" or "refresh")

        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token expired")
            return None
        except PyJWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[tuple[str, str]]:
        """
        Generate new access and refresh tokens using a valid refresh token.

        Args:
            refresh_token: Current refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token) if successful, None otherwise
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None

        # Get user
        user_id = int(payload.get("sub"))
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            logger.warning(f"Token refresh failed: User {user_id} not found or inactive")
            return None

        # Check token version (for revocation)
        if payload.get("version") != user.refresh_token_version:
            logger.warning(f"Token refresh failed: Token version mismatch for user {user_id}")
            return None

        # Create new tokens
        new_access_token = self.create_access_token(user)
        new_refresh_token = self.create_refresh_token(user)

        logger.info(f"Refreshed tokens for user {user.username}")
        return new_access_token, new_refresh_token

    def revoke_all_tokens(self, user: User):
        """
        Revoke all tokens for a user by incrementing the refresh token version.

        Args:
            user: User object
        """
        user.refresh_token_version += 1
        self.db.commit()
        logger.info(f"Revoked all tokens for user {user.username}")

    def get_current_user(self, token: str) -> Optional[User]:
        """
        Get the current user from a JWT token.

        Args:
            token: JWT access token

        Returns:
            User object if token is valid, None otherwise
        """
        # Verify token
        payload = self.verify_token(token, token_type="access")
        if not payload:
            return None

        # Get user from database
        user_id = int(payload.get("sub"))
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            logger.warning(f"User {user_id} not found or inactive")
            return None

        return user

    def check_permission(self, user: User, permission_name: str) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user: User object
            permission_name: Permission name (e.g., "read:leads")

        Returns:
            True if user has permission, False otherwise
        """
        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Check user's roles for permission
        for role in user.roles:
            if any(perm.name == permission_name for perm in role.permissions):
                return True

        return False

    def check_role(self, user: User, role_name: str) -> bool:
        """
        Check if a user has a specific role.

        Args:
            user: User object
            role_name: Role name

        Returns:
            True if user has role, False otherwise
        """
        return any(role.name == role_name for role in user.roles)

    def create_default_roles_and_permissions(self):
        """
        Create default system roles and permissions.
        Called during initial setup or migration.
        """
        # Define default permissions
        default_permissions = [
            # Lead permissions
            ("read:leads", "View lead information"),
            ("write:leads", "Create and update leads"),
            ("delete:leads", "Delete leads"),

            # Campaign permissions
            ("read:campaigns", "View campaign information"),
            ("write:campaigns", "Create and update campaigns"),
            ("delete:campaigns", "Delete campaigns"),

            # CRM permissions
            ("read:crm", "View CRM data"),
            ("write:crm", "Sync and update CRM data"),
            ("manage:crm", "Manage CRM connections and credentials"),

            # Report permissions
            ("read:reports", "View reports"),
            ("write:reports", "Generate reports"),

            # Admin permissions
            ("manage:users", "Manage user accounts"),
            ("manage:roles", "Manage roles and permissions"),
            ("view:audit", "View audit logs"),
            ("manage:system", "System administration"),
        ]

        # Create permissions
        permissions = {}
        for perm_name, description in default_permissions:
            resource, action = perm_name.split(":")
            perm = self.db.query(Permission).filter(Permission.name == perm_name).first()
            if not perm:
                perm = Permission(
                    name=perm_name,
                    description=description,
                    resource=resource,
                    action=action,
                )
                self.db.add(perm)
            permissions[perm_name] = perm

        # Define default roles with their permissions
        default_roles = [
            ("admin", "Full system access", [
                "manage:users", "manage:roles", "view:audit", "manage:system",
                "read:leads", "write:leads", "delete:leads",
                "read:campaigns", "write:campaigns", "delete:campaigns",
                "read:crm", "write:crm", "manage:crm",
                "read:reports", "write:reports",
            ]),
            ("manager", "Read and write access to business data", [
                "read:leads", "write:leads",
                "read:campaigns", "write:campaigns",
                "read:crm", "write:crm",
                "read:reports", "write:reports",
            ]),
            ("user", "Read-only access to business data", [
                "read:leads",
                "read:campaigns",
                "read:crm",
                "read:reports",
            ]),
        ]

        # Create roles
        for role_name, description, perm_names in default_roles:
            role = self.db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(
                    name=role_name,
                    description=description,
                    is_system=True,
                )
                # Assign permissions
                role.permissions = [permissions[pname] for pname in perm_names]
                self.db.add(role)

        self.db.commit()
        logger.info("Default roles and permissions created")


def hash_password(password: str) -> str:
    """
    Hash a plain text password.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_hash.verify(plain_password, hashed_password)
        return True
    except Exception:
        return False