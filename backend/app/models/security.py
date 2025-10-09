"""
Security-related database models for audit logging, RBAC, and GDPR compliance.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON,
    ForeignKey, Table, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class EventType(enum.Enum):
    """Types of security events for audit logging."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"

    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"

    # Data events
    DATA_CREATED = "data_created"
    DATA_READ = "data_read"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_EXPORTED = "data_exported"

    # CRM events
    CRM_SYNC = "crm_sync"
    CRM_AUTH = "crm_auth"
    CREDENTIAL_ENCRYPTED = "credential_encrypted"
    CREDENTIAL_DECRYPTED = "credential_decrypted"

    # GDPR events
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    DATA_EXPORT_REQUESTED = "data_export_requested"
    DATA_DELETION_REQUESTED = "data_deletion_requested"

    # System events
    CONFIG_CHANGED = "config_changed"
    API_ERROR = "api_error"
    SECURITY_ALERT = "security_alert"


class SecurityEvent(Base):
    """
    Audit log table for all security-relevant events.
    Stores detailed information about every API request and security-sensitive operation.
    """
    __tablename__ = "security_events"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Event details
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    resource = Column(String(255), nullable=True)  # e.g., "lead:123", "campaign:456"
    action = Column(String(50), nullable=True)  # e.g., "create", "read", "update", "delete"

    # Request context
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(36), nullable=True, index=True)  # UUID for request tracing
    request_method = Column(String(10), nullable=True)  # GET, POST, PUT, DELETE, etc.
    request_path = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)  # Request processing time

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Flexible metadata field for additional context
    event_metadata = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="security_events")

    # Indexes for query performance
    __table_args__ = (
        Index('idx_security_events_timestamp_type', 'timestamp', 'event_type'),
        Index('idx_security_events_user_timestamp', 'user_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<SecurityEvent(id={self.id}, type={self.event_type}, user_id={self.user_id})>"


# Many-to-many association tables for RBAC
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), server_default=func.now()),
    Column("assigned_by", Integer, ForeignKey("users.id"))
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
    Column("granted_at", DateTime(timezone=True), server_default=func.now())
)


class User(Base):
    """
    User account table for authentication and authorization.
    Passwords are hashed using bcrypt via pwdlib.
    """
    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Authentication fields
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)  # bcrypt/argon2 hash

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)

    # Profile information
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Security fields
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)  # Account lockout

    # JWT token management
    refresh_token_version = Column(Integer, default=0, nullable=False)  # Incremented to invalidate all tokens

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    security_events = relationship("SecurityEvent", back_populates="user", cascade="all, delete-orphan")
    consent_records = relationship("UserConsent", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission through any of their roles."""
        for role in self.roles:
            if any(perm.name == permission_name for perm in role.permissions):
                return True
        return self.is_superuser  # Superusers have all permissions


class Role(Base):
    """
    Role table for Role-Based Access Control (RBAC).
    Roles are collections of permissions assigned to users.
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"


class Permission(Base):
    """
    Permission table for fine-grained access control.
    Permissions follow the format: "action:resource" (e.g., "read:leads", "write:campaigns").
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "read:leads"
    description = Column(Text, nullable=True)
    resource = Column(String(100), nullable=True, index=True)  # e.g., "leads", "campaigns"
    action = Column(String(50), nullable=True, index=True)  # e.g., "read", "write", "delete"

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}')>"


class ConsentType(enum.Enum):
    """Types of user consent for GDPR compliance."""
    MARKETING = "marketing"  # Marketing communications
    ANALYTICS = "analytics"  # Usage analytics and tracking
    DATA_PROCESSING = "data_processing"  # Core data processing for service
    THIRD_PARTY_SHARING = "third_party_sharing"  # Sharing with partners
    COOKIES = "cookies"  # Cookie usage
    PROFILING = "profiling"  # Automated profiling and scoring


class UserConsent(Base):
    """
    User consent tracking table for GDPR Articles 6 & 7 compliance.
    Records all consent grants and revocations with full audit trail.
    """
    __tablename__ = "user_consent"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    consent_type = Column(SQLEnum(ConsentType), nullable=False, index=True)

    # Consent status
    is_granted = Column(Boolean, default=False, nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Consent context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    consent_text = Column(Text, nullable=True)  # The exact consent text shown to user
    consent_version = Column(String(50), nullable=True)  # Version of consent text

    # Legal basis (GDPR Article 6)
    legal_basis = Column(String(100), nullable=True)  # e.g., "consent", "legitimate_interest", "contract"
    purpose = Column(Text, nullable=True)  # Purpose of data processing

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="consent_records")

    # Unique constraint: one record per user per consent type
    __table_args__ = (
        UniqueConstraint('user_id', 'consent_type', name='uq_user_consent_type'),
        Index('idx_user_consent_status', 'user_id', 'consent_type', 'is_granted'),
    )

    def __repr__(self):
        return f"<UserConsent(user_id={self.user_id}, type={self.consent_type}, granted={self.is_granted})>"