"""Add cold-reach tables for email infrastructure and sequence campaigns

Revision ID: 017_cold_reach_tables
Revises: 016_star_schema_performance
Create Date: 2025-12-06

This migration adds cold-reach email infrastructure models for the Scientia GTM Stack.
Integrates domain management, mailbox warming, sequence campaigns, and signal processing.

New Tables:
- dim_domains: Managed domains with DNS configuration tracking (SPF, DKIM, DMARC)
- dim_mailboxes: Email accounts for warming and sending with heat scores
- dim_sequences: Multi-step email campaigns with JSON step configuration
- dim_sequence_entries: Prospect progress through sequences (fact table)
- dim_signals: Incoming email signals (replies, bounces, OOO) with AI classification

Integration:
- Extends existing 'leads' table with tier field and cold-outreach relationships
- Foreign keys to leads table for prospect tracking
- Signal processing feeds into VozLux call triggers

Architecture:
- Async-first design compatible with SQLAlchemy 2.0
- Supabase PostgreSQL naming conventions (dim_ prefix)
- Comprehensive indexes for performance
- JSON columns for flexible metadata storage
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017_cold_reach_tables'
down_revision: Union[str, None] = '016_star_schema_performance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Add tier field to existing leads table
    # =========================================================================
    op.add_column('leads', sa.Column('tier', sa.String(length=50), nullable=True))

    # =========================================================================
    # Create dim_domains table
    # =========================================================================
    op.create_table(
        'dim_domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registrar', sa.String(length=100), nullable=True),
        sa.Column('dns_configured', sa.Boolean(), nullable=False),
        sa.Column('spf_configured', sa.Boolean(), nullable=False),
        sa.Column('dkim_configured', sa.Boolean(), nullable=False),
        sa.Column('dmarc_configured', sa.Boolean(), nullable=False),
        sa.Column('godaddy_domain_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_domains_active_registrar', 'dim_domains', ['is_active', 'registrar'], unique=False)
    op.create_index('idx_domains_expires_at', 'dim_domains', ['expires_at'], unique=False)
    op.create_index(op.f('ix_dim_domains_id'), 'dim_domains', ['id'], unique=False)
    op.create_index(op.f('ix_dim_domains_is_active'), 'dim_domains', ['is_active'], unique=False)
    op.create_index(op.f('ix_dim_domains_name'), 'dim_domains', ['name'], unique=True)

    # =========================================================================
    # Create dim_mailboxes table
    # =========================================================================
    op.create_table(
        'dim_mailboxes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_encrypted', sa.Text(), nullable=False),
        sa.Column('smtp_host', sa.String(length=255), nullable=True),
        sa.Column('smtp_port', sa.Integer(), nullable=True),
        sa.Column('imap_host', sa.String(length=255), nullable=True),
        sa.Column('imap_port', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('heat_score', sa.Integer(), nullable=False),
        sa.Column('warming_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_sent', sa.Integer(), nullable=False),
        sa.Column('total_received', sa.Integer(), nullable=False),
        sa.Column('spam_rescues', sa.Integer(), nullable=False),
        sa.Column('bounce_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_mailboxes_status_heat', 'dim_mailboxes', ['status', 'heat_score'], unique=False)
    op.create_index('idx_mailboxes_warming_start', 'dim_mailboxes', ['warming_start_date'], unique=False)
    op.create_index(op.f('ix_dim_mailboxes_email'), 'dim_mailboxes', ['email'], unique=True)
    op.create_index(op.f('ix_dim_mailboxes_id'), 'dim_mailboxes', ['id'], unique=False)
    op.create_index(op.f('ix_dim_mailboxes_status'), 'dim_mailboxes', ['status'], unique=False)

    # =========================================================================
    # Create dim_sequences table
    # =========================================================================
    op.create_table(
        'dim_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sequence_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('stop_on_reply', sa.Boolean(), nullable=False),
        sa.Column('stop_on_bounce', sa.Boolean(), nullable=False),
        sa.Column('daily_limit_per_mailbox', sa.Integer(), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sequences_active_created', 'dim_sequences', ['is_active', 'created_at'], unique=False)
    op.create_index(op.f('ix_dim_sequences_id'), 'dim_sequences', ['id'], unique=False)
    op.create_index(op.f('ix_dim_sequences_is_active'), 'dim_sequences', ['is_active'], unique=False)
    op.create_index(op.f('ix_dim_sequences_sequence_id'), 'dim_sequences', ['sequence_id'], unique=True)

    # =========================================================================
    # Create dim_sequence_entries table (fact table)
    # =========================================================================
    op.create_table(
        'dim_sequence_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('sequence_id', sa.Integer(), nullable=False),
        sa.Column('mailbox_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_step', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_email_sent', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reply_received', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reply_intent', sa.String(length=50), nullable=True),
        sa.Column('emails_sent', sa.Integer(), nullable=False),
        sa.Column('opens', sa.Integer(), nullable=False),
        sa.Column('clicks', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('message_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mailbox_id'], ['dim_mailboxes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sequence_id'], ['dim_sequences.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_entries_lead_sequence', 'dim_sequence_entries', ['lead_id', 'sequence_id'], unique=False)
    op.create_index('idx_entries_status_current_step', 'dim_sequence_entries', ['status', 'current_step'], unique=False)
    op.create_index('idx_entries_status_updated', 'dim_sequence_entries', ['status', 'updated_at'], unique=False)
    op.create_index(op.f('ix_dim_sequence_entries_id'), 'dim_sequence_entries', ['id'], unique=False)
    op.create_index(op.f('ix_dim_sequence_entries_lead_id'), 'dim_sequence_entries', ['lead_id'], unique=False)
    op.create_index(op.f('ix_dim_sequence_entries_mailbox_id'), 'dim_sequence_entries', ['mailbox_id'], unique=False)
    op.create_index(op.f('ix_dim_sequence_entries_sequence_id'), 'dim_sequence_entries', ['sequence_id'], unique=False)
    op.create_index(op.f('ix_dim_sequence_entries_status'), 'dim_sequence_entries', ['status'], unique=False)

    # =========================================================================
    # Create dim_signals table
    # =========================================================================
    op.create_table(
        'dim_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('signal_type', sa.String(length=50), nullable=False),
        sa.Column('mailbox_email', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('intent', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=True),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('raw_headers', sa.JSON(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('routed_to', sa.String(length=100), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_signals_intent_processed', 'dim_signals', ['intent', 'processed'], unique=False)
    op.create_index('idx_signals_processed_received', 'dim_signals', ['processed', 'received_at'], unique=False)
    op.create_index('idx_signals_type_priority', 'dim_signals', ['signal_type', 'priority'], unique=False)
    op.create_index(op.f('ix_dim_signals_id'), 'dim_signals', ['id'], unique=False)
    op.create_index(op.f('ix_dim_signals_intent'), 'dim_signals', ['intent'], unique=False)
    op.create_index(op.f('ix_dim_signals_lead_id'), 'dim_signals', ['lead_id'], unique=False)
    op.create_index(op.f('ix_dim_signals_mailbox_email'), 'dim_signals', ['mailbox_email'], unique=False)
    op.create_index(op.f('ix_dim_signals_message_id'), 'dim_signals', ['message_id'], unique=False)
    op.create_index(op.f('ix_dim_signals_processed'), 'dim_signals', ['processed'], unique=False)
    op.create_index(op.f('ix_dim_signals_signal_type'), 'dim_signals', ['signal_type'], unique=False)
    op.create_index(op.f('ix_dim_signals_thread_id'), 'dim_signals', ['thread_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_index(op.f('ix_dim_signals_thread_id'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_signal_type'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_processed'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_message_id'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_mailbox_email'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_lead_id'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_intent'), table_name='dim_signals')
    op.drop_index(op.f('ix_dim_signals_id'), table_name='dim_signals')
    op.drop_index('idx_signals_type_priority', table_name='dim_signals')
    op.drop_index('idx_signals_processed_received', table_name='dim_signals')
    op.drop_index('idx_signals_intent_processed', table_name='dim_signals')
    op.drop_table('dim_signals')

    op.drop_index(op.f('ix_dim_sequence_entries_status'), table_name='dim_sequence_entries')
    op.drop_index(op.f('ix_dim_sequence_entries_sequence_id'), table_name='dim_sequence_entries')
    op.drop_index(op.f('ix_dim_sequence_entries_mailbox_id'), table_name='dim_sequence_entries')
    op.drop_index(op.f('ix_dim_sequence_entries_lead_id'), table_name='dim_sequence_entries')
    op.drop_index(op.f('ix_dim_sequence_entries_id'), table_name='dim_sequence_entries')
    op.drop_index('idx_entries_status_updated', table_name='dim_sequence_entries')
    op.drop_index('idx_entries_status_current_step', table_name='dim_sequence_entries')
    op.drop_index('idx_entries_lead_sequence', table_name='dim_sequence_entries')
    op.drop_table('dim_sequence_entries')

    op.drop_index(op.f('ix_dim_sequences_sequence_id'), table_name='dim_sequences')
    op.drop_index(op.f('ix_dim_sequences_is_active'), table_name='dim_sequences')
    op.drop_index(op.f('ix_dim_sequences_id'), table_name='dim_sequences')
    op.drop_index('idx_sequences_active_created', table_name='dim_sequences')
    op.drop_table('dim_sequences')

    op.drop_index(op.f('ix_dim_mailboxes_status'), table_name='dim_mailboxes')
    op.drop_index(op.f('ix_dim_mailboxes_id'), table_name='dim_mailboxes')
    op.drop_index(op.f('ix_dim_mailboxes_email'), table_name='dim_mailboxes')
    op.drop_index('idx_mailboxes_warming_start', table_name='dim_mailboxes')
    op.drop_index('idx_mailboxes_status_heat', table_name='dim_mailboxes')
    op.drop_table('dim_mailboxes')

    op.drop_index(op.f('ix_dim_domains_name'), table_name='dim_domains')
    op.drop_index(op.f('ix_dim_domains_is_active'), table_name='dim_domains')
    op.drop_index(op.f('ix_dim_domains_id'), table_name='dim_domains')
    op.drop_index('idx_domains_expires_at', table_name='dim_domains')
    op.drop_index('idx_domains_active_registrar', table_name='dim_domains')
    op.drop_table('dim_domains')

    # Remove tier field from leads table
    op.drop_column('leads', 'tier')
