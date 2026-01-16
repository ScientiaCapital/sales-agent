"""
Add comprehensive analytics tables for metrics tracking and A/B testing

Revision ID: 20251030_add_analytics
Revises: 20251030_lead_indexes
Create Date: 2025-10-30

Creates tables for:
- User session tracking
- Lead qualification metrics
- Campaign performance analytics
- System health metrics
- A/B test experiments with statistical significance
- Generated analytics reports
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251030_add_analytics'
down_revision = '20251030_lead_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all analytics tables and indexes."""

    # ========================================================================
    # analytics_user_sessions
    # ========================================================================
    op.create_table(
        'analytics_user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('api_calls_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_cost_usd', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('agents_used', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('leads_processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('session_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('referrer', sa.String(length=500), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_user_sessions_id', 'analytics_user_sessions', ['id'])
    op.create_index('ix_analytics_user_sessions_session_id', 'analytics_user_sessions', ['session_id'], unique=True)
    op.create_index('ix_analytics_user_sessions_user_id', 'analytics_user_sessions', ['user_id'])
    op.create_index('idx_analytics_session_user_time', 'analytics_user_sessions', ['user_id', 'started_at'])

    # ========================================================================
    # analytics_lead_metrics
    # ========================================================================
    op.create_table(
        'analytics_lead_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('external_lead_id', sa.String(length=100), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('campaign_id', sa.String(length=100), nullable=True),
        sa.Column('utm_source', sa.String(length=100), nullable=True),
        sa.Column('utm_medium', sa.String(length=100), nullable=True),
        sa.Column('utm_campaign', sa.String(length=100), nullable=True),
        sa.Column('qualification_score', sa.Float(), nullable=True),
        sa.Column('qualification_tier', sa.String(length=10), nullable=True),
        sa.Column('qualification_reasoning', sa.Text(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('agents_used', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('enrichment_sources', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('conversion_status', sa.String(length=50), nullable=True),
        sa.Column('conversion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revenue_attributed', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_lead_metrics_id', 'analytics_lead_metrics', ['id'])
    op.create_index('ix_analytics_lead_metrics_lead_id', 'analytics_lead_metrics', ['lead_id'])
    op.create_index('ix_analytics_lead_metrics_external_lead_id', 'analytics_lead_metrics', ['external_lead_id'])
    op.create_index('ix_analytics_lead_metrics_source', 'analytics_lead_metrics', ['source'])
    op.create_index('ix_analytics_lead_metrics_campaign_id', 'analytics_lead_metrics', ['campaign_id'])
    op.create_index('ix_analytics_lead_metrics_qualification_score', 'analytics_lead_metrics', ['qualification_score'])
    op.create_index('ix_analytics_lead_metrics_qualification_tier', 'analytics_lead_metrics', ['qualification_tier'])
    op.create_index('ix_analytics_lead_metrics_conversion_status', 'analytics_lead_metrics', ['conversion_status'])
    op.create_index('idx_analytics_lead_source_time', 'analytics_lead_metrics', ['source', 'created_at'])
    op.create_index('idx_analytics_lead_conversion', 'analytics_lead_metrics', ['conversion_status', 'conversion_date'])

    # ========================================================================
    # analytics_campaign_metrics
    # ========================================================================
    op.create_table(
        'analytics_campaign_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.String(length=100), nullable=False),
        sa.Column('campaign_name', sa.String(length=200), nullable=False),
        sa.Column('campaign_type', sa.String(length=50), nullable=False),
        sa.Column('impressions', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('clicks', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('conversions', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('leads_generated', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('click_through_rate', sa.Float(), nullable=True),
        sa.Column('conversion_rate', sa.Float(), nullable=True),
        sa.Column('cost_per_click', sa.Float(), nullable=True),
        sa.Column('cost_per_conversion', sa.Float(), nullable=True),
        sa.Column('revenue_generated', sa.Float(), nullable=True),
        sa.Column('roi_percentage', sa.Float(), nullable=True),
        sa.Column('campaign_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('campaign_end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('campaign_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_campaign_metrics_id', 'analytics_campaign_metrics', ['id'])
    op.create_index('ix_analytics_campaign_metrics_campaign_id', 'analytics_campaign_metrics', ['campaign_id'])
    op.create_index('ix_analytics_campaign_metrics_campaign_type', 'analytics_campaign_metrics', ['campaign_type'])
    op.create_index('idx_analytics_campaign_type_time', 'analytics_campaign_metrics', ['campaign_type', 'created_at'])

    # ========================================================================
    # analytics_system_metrics
    # ========================================================================
    op.create_table(
        'analytics_system_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(length=20), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('subcategory', sa.String(length=50), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=True),
        sa.Column('endpoint', sa.String(length=200), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metric_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_system_metrics_id', 'analytics_system_metrics', ['id'])
    op.create_index('ix_analytics_system_metrics_metric_name', 'analytics_system_metrics', ['metric_name'])
    op.create_index('ix_analytics_system_metrics_category', 'analytics_system_metrics', ['category'])
    op.create_index('ix_analytics_system_metrics_subcategory', 'analytics_system_metrics', ['subcategory'])
    op.create_index('ix_analytics_system_metrics_agent_type', 'analytics_system_metrics', ['agent_type'])
    op.create_index('ix_analytics_system_metrics_endpoint', 'analytics_system_metrics', ['endpoint'])
    op.create_index('ix_analytics_system_metrics_recorded_at', 'analytics_system_metrics', ['recorded_at'])
    op.create_index('idx_analytics_system_category_time', 'analytics_system_metrics', ['category', 'recorded_at'])

    # ========================================================================
    # analytics_ab_tests - Core A/B testing with statistical significance
    # ========================================================================
    op.create_table(
        'analytics_ab_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_id', sa.String(length=100), nullable=False),
        sa.Column('test_name', sa.String(length=200), nullable=False),
        sa.Column('test_description', sa.Text(), nullable=True),
        sa.Column('variant_a_name', sa.String(length=100), nullable=False),
        sa.Column('variant_b_name', sa.String(length=100), nullable=False),
        sa.Column('test_type', sa.String(length=50), nullable=False),
        sa.Column('participants_a', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('participants_b', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('conversions_a', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('conversions_b', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('conversion_rate_a', sa.Float(), nullable=True),
        sa.Column('conversion_rate_b', sa.Float(), nullable=True),
        sa.Column('statistical_significance', sa.Float(), nullable=True),  # p-value
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.Column('winner', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('test_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_ab_tests_id', 'analytics_ab_tests', ['id'])
    op.create_index('ix_analytics_ab_tests_test_id', 'analytics_ab_tests', ['test_id'], unique=True)
    op.create_index('ix_analytics_ab_tests_test_type', 'analytics_ab_tests', ['test_type'])
    op.create_index('ix_analytics_ab_tests_status', 'analytics_ab_tests', ['status'])
    op.create_index('idx_analytics_ab_test_status', 'analytics_ab_tests', ['status', 'start_date'])

    # ========================================================================
    # analytics_reports
    # ========================================================================
    op.create_table(
        'analytics_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.String(length=36), nullable=True),
        sa.Column('report_name', sa.String(length=200), nullable=False),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('report_parameters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('time_range_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_range_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('chart_configs', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('generated_by', sa.String(length=100), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='generated'),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_reports_id', 'analytics_reports', ['id'])
    op.create_index('ix_analytics_reports_report_id', 'analytics_reports', ['report_id'], unique=True)
    op.create_index('ix_analytics_reports_report_type', 'analytics_reports', ['report_type'])
    op.create_index('ix_analytics_reports_status', 'analytics_reports', ['status'])
    op.create_index('idx_analytics_report_type_time', 'analytics_reports', ['report_type', 'generated_at'])


def downgrade() -> None:
    """Drop all analytics tables and indexes."""

    # Drop tables in reverse order
    op.drop_index('idx_analytics_report_type_time', table_name='analytics_reports')
    op.drop_index('ix_analytics_reports_status', table_name='analytics_reports')
    op.drop_index('ix_analytics_reports_report_type', table_name='analytics_reports')
    op.drop_index('ix_analytics_reports_report_id', table_name='analytics_reports')
    op.drop_index('ix_analytics_reports_id', table_name='analytics_reports')
    op.drop_table('analytics_reports')

    op.drop_index('idx_analytics_ab_test_status', table_name='analytics_ab_tests')
    op.drop_index('ix_analytics_ab_tests_status', table_name='analytics_ab_tests')
    op.drop_index('ix_analytics_ab_tests_test_type', table_name='analytics_ab_tests')
    op.drop_index('ix_analytics_ab_tests_test_id', table_name='analytics_ab_tests')
    op.drop_index('ix_analytics_ab_tests_id', table_name='analytics_ab_tests')
    op.drop_table('analytics_ab_tests')

    op.drop_index('idx_analytics_system_category_time', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_recorded_at', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_endpoint', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_agent_type', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_subcategory', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_category', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_metric_name', table_name='analytics_system_metrics')
    op.drop_index('ix_analytics_system_metrics_id', table_name='analytics_system_metrics')
    op.drop_table('analytics_system_metrics')

    op.drop_index('idx_analytics_campaign_type_time', table_name='analytics_campaign_metrics')
    op.drop_index('ix_analytics_campaign_metrics_campaign_type', table_name='analytics_campaign_metrics')
    op.drop_index('ix_analytics_campaign_metrics_campaign_id', table_name='analytics_campaign_metrics')
    op.drop_index('ix_analytics_campaign_metrics_id', table_name='analytics_campaign_metrics')
    op.drop_table('analytics_campaign_metrics')

    op.drop_index('idx_analytics_lead_conversion', table_name='analytics_lead_metrics')
    op.drop_index('idx_analytics_lead_source_time', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_conversion_status', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_qualification_tier', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_qualification_score', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_campaign_id', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_source', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_external_lead_id', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_lead_id', table_name='analytics_lead_metrics')
    op.drop_index('ix_analytics_lead_metrics_id', table_name='analytics_lead_metrics')
    op.drop_table('analytics_lead_metrics')

    op.drop_index('idx_analytics_session_user_time', table_name='analytics_user_sessions')
    op.drop_index('ix_analytics_user_sessions_user_id', table_name='analytics_user_sessions')
    op.drop_index('ix_analytics_user_sessions_session_id', table_name='analytics_user_sessions')
    op.drop_index('ix_analytics_user_sessions_id', table_name='analytics_user_sessions')
    op.drop_table('analytics_user_sessions')
