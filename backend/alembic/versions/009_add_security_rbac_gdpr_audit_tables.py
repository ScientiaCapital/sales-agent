"""Add security tables for RBAC, GDPR, and audit logging

Revision ID: 009_security_tables
Revises: 008_add_campaign_tables
Create Date: 2025-10-07

Adds comprehensive security infrastructure:
- User authentication and authorization tables
- Role-Based Access Control (RBAC)
- Audit logging for SOC 2 compliance
- GDPR consent management
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic
revision = '009_security_tables'
down_revision = '008_add_campaign_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create security-related tables for Task 9: Security & Compliance"""

    # Create enum types
    op.execute("""
        CREATE TYPE eventtype AS ENUM (
            'login_success', 'login_failed', 'logout', 'token_refresh', 'token_revoked',
            'access_granted', 'access_denied', 'permission_changed', 'role_assigned', 'role_removed',
            'data_created', 'data_read', 'data_updated', 'data_deleted', 'data_exported',
            'crm_sync', 'crm_auth', 'credential_encrypted', 'credential_decrypted',
            'consent_granted', 'consent_revoked', 'data_export_requested', 'data_deletion_requested',
            'config_changed', 'api_error', 'security_alert'
        )
    """)

    op.execute("""
        CREATE TYPE consenttype AS ENUM (
            'marketing', 'analytics', 'data_processing',
            'third_party_sharing', 'cookies', 'profiling'
        )
    """)

    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_ip', sa.String(45), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_username', 'users', ['username'], unique=True)
    op.create_index('idx_users_email', 'users', ['email'], unique=True)

    # 2. Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_roles_name', 'roles', ['name'], unique=True)

    # 3. Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource', sa.String(100), nullable=True),
        sa.Column('action', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_permissions_name', 'permissions', ['name'], unique=True)
    op.create_index('idx_permissions_resource', 'permissions', ['resource'])
    op.create_index('idx_permissions_action', 'permissions', ['action'])

    # 4. Create user_roles association table
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    # 5. Create role_permissions association table
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # 6. Create security_events table for audit logging
    op.create_table(
        'security_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', postgresql.ENUM(name='eventtype', create_type=False), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('resource', sa.String(255), nullable=True),
        sa.Column('action', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('request_path', sa.String(500), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_security_events_event_type', 'security_events', ['event_type'])
    op.create_index('idx_security_events_user_id', 'security_events', ['user_id'])
    op.create_index('idx_security_events_timestamp', 'security_events', ['timestamp'])
    op.create_index('idx_security_events_request_id', 'security_events', ['request_id'])
    op.create_index('idx_security_events_timestamp_type', 'security_events', ['timestamp', 'event_type'])
    op.create_index('idx_security_events_user_timestamp', 'security_events', ['user_id', 'timestamp'])

    # 7. Create user_consent table for GDPR compliance
    op.create_table(
        'user_consent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('consent_type', postgresql.ENUM(name='consenttype', create_type=False), nullable=False),
        sa.Column('is_granted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.Column('consent_version', sa.String(50), nullable=True),
        sa.Column('legal_basis', sa.String(100), nullable=True),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'consent_type', name='uq_user_consent_type')
    )
    op.create_index('idx_user_consent_user_id', 'user_consent', ['user_id'])
    op.create_index('idx_user_consent_type', 'user_consent', ['consent_type'])
    op.create_index('idx_user_consent_status', 'user_consent', ['user_id', 'consent_type', 'is_granted'])

    # 8. Insert default roles
    op.execute("""
        INSERT INTO roles (name, description, is_system) VALUES
        ('admin', 'Full system access with all permissions', true),
        ('manager', 'Read and write access to business data', true),
        ('user', 'Read-only access to business data', true)
    """)

    # 9. Insert default permissions
    op.execute("""
        INSERT INTO permissions (name, description, resource, action) VALUES
        -- Lead permissions
        ('read:leads', 'View lead information', 'leads', 'read'),
        ('write:leads', 'Create and update leads', 'leads', 'write'),
        ('delete:leads', 'Delete leads', 'leads', 'delete'),

        -- Campaign permissions
        ('read:campaigns', 'View campaign information', 'campaigns', 'read'),
        ('write:campaigns', 'Create and update campaigns', 'campaigns', 'write'),
        ('delete:campaigns', 'Delete campaigns', 'campaigns', 'delete'),

        -- CRM permissions
        ('read:crm', 'View CRM data', 'crm', 'read'),
        ('write:crm', 'Sync and update CRM data', 'crm', 'write'),
        ('manage:crm', 'Manage CRM connections and credentials', 'crm', 'manage'),

        -- Report permissions
        ('read:reports', 'View reports', 'reports', 'read'),
        ('write:reports', 'Generate reports', 'reports', 'write'),

        -- Admin permissions
        ('manage:users', 'Manage user accounts', 'users', 'manage'),
        ('manage:roles', 'Manage roles and permissions', 'roles', 'manage'),
        ('view:audit', 'View audit logs', 'audit', 'view'),
        ('manage:system', 'System administration', 'system', 'manage')
    """)

    # 10. Assign permissions to roles
    op.execute("""
        -- Admin role gets all permissions
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'admin';

        -- Manager role gets business permissions
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'manager'
        AND p.name IN (
            'read:leads', 'write:leads',
            'read:campaigns', 'write:campaigns',
            'read:crm', 'write:crm',
            'read:reports', 'write:reports'
        );

        -- User role gets read-only permissions
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'user'
        AND p.name IN (
            'read:leads',
            'read:campaigns',
            'read:crm',
            'read:reports'
        );
    """)

    # 11. Create a default admin user (password: admin123! - MUST be changed on first login)
    # Note: In production, this should be done via a secure setup script
    op.execute("""
        INSERT INTO users (username, email, hashed_password, is_active, is_superuser, email_verified, full_name)
        VALUES (
            'admin',
            'admin@salesagent.local',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGPKtu.pQIy',  -- bcrypt hash of 'admin123!'
            true,
            true,
            true,
            'System Administrator'
        )
    """)

    # 12. Assign admin role to admin user
    op.execute("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u, roles r
        WHERE u.username = 'admin' AND r.name = 'admin'
    """)


def downgrade() -> None:
    """Drop all security-related tables and enums"""

    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('user_consent')
    op.drop_table('security_events')
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS eventtype CASCADE')
    op.execute('DROP TYPE IF EXISTS consenttype CASCADE')