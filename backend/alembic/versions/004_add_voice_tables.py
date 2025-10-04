"""Add voice interaction tables

Revision ID: 004_add_voice_tables
Revises: 003_add_social_media_tables
Create Date: 2025-10-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '004_add_voice_tables'
down_revision = '003_add_social_media_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create voice_session_logs table
    op.create_table('voice_session_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('voice_id', sa.String(), nullable=False),
        sa.Column('voice_name', sa.String(), nullable=True),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('initial_emotion', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', 'ERROR', 'ABANDONED', name='voicesessionstatus'), nullable=True),
        sa.Column('total_turns', sa.Integer(), nullable=True),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        sa.Column('average_latency_ms', sa.Float(), nullable=True),
        sa.Column('min_latency_ms', sa.Integer(), nullable=True),
        sa.Column('max_latency_ms', sa.Integer(), nullable=True),
        sa.Column('p50_latency_ms', sa.Integer(), nullable=True),
        sa.Column('p95_latency_ms', sa.Integer(), nullable=True),
        sa.Column('p99_latency_ms', sa.Integer(), nullable=True),
        sa.Column('target_compliance_rate', sa.Float(), nullable=True),
        sa.Column('total_tts_cost_usd', sa.Float(), nullable=True),
        sa.Column('total_stt_cost_usd', sa.Float(), nullable=True),
        sa.Column('total_inference_cost_usd', sa.Float(), nullable=True),
        sa.Column('conversation_summary', sa.Text(), nullable=True),
        sa.Column('final_outcome', sa.String(), nullable=True),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_voice_session_logs_created_at', 'voice_session_logs', ['created_at'], unique=False)
    op.create_index('ix_voice_session_logs_lead_id', 'voice_session_logs', ['lead_id'], unique=False)
    op.create_index('ix_voice_session_logs_status', 'voice_session_logs', ['status'], unique=False)

    # Create voice_turns table
    op.create_table('voice_turns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('voice_session_id', sa.String(), nullable=True),
        sa.Column('turn_number', sa.Integer(), nullable=True),
        sa.Column('user_transcript', sa.Text(), nullable=True),
        sa.Column('user_audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('stt_confidence', sa.Float(), nullable=True),
        sa.Column('ai_response_text', sa.Text(), nullable=True),
        sa.Column('ai_audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('response_emotion', sa.String(), nullable=True),
        sa.Column('response_speed', sa.String(), nullable=True),
        sa.Column('stt_latency_ms', sa.Integer(), nullable=True),
        sa.Column('inference_latency_ms', sa.Integer(), nullable=True),
        sa.Column('tts_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_latency_ms', sa.Integer(), nullable=True),
        sa.Column('met_latency_target', sa.Boolean(), nullable=True),
        sa.Column('turn_context', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['voice_session_id'], ['voice_session_logs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_voice_turns_started_at', 'voice_turns', ['started_at'], unique=False)
    op.create_index('ix_voice_turns_total_latency_ms', 'voice_turns', ['total_latency_ms'], unique=False)
    op.create_index('ix_voice_turns_voice_session_id', 'voice_turns', ['voice_session_id'], unique=False)

    # Create cartesia_api_calls table
    op.create_table('cartesia_api_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('voice_session_id', sa.String(), nullable=True),
        sa.Column('turn_id', sa.String(), nullable=True),
        sa.Column('operation', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('characters_processed', sa.Integer(), nullable=True),
        sa.Column('audio_seconds_processed', sa.Float(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['turn_id'], ['voice_turns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voice_session_id'], ['voice_session_logs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cartesia_api_calls_created_at', 'cartesia_api_calls', ['created_at'], unique=False)
    op.create_index('ix_cartesia_api_calls_operation', 'cartesia_api_calls', ['operation'], unique=False)
    op.create_index('ix_cartesia_api_calls_voice_session_id', 'cartesia_api_calls', ['voice_session_id'], unique=False)

    # Create voice_configurations table
    op.create_table('voice_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('voice_id', sa.String(), nullable=False),
        sa.Column('voice_name', sa.String(), nullable=True),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('default_emotion', sa.String(), nullable=True),
        sa.Column('default_speed', sa.String(), nullable=True),
        sa.Column('sample_rate', sa.Integer(), nullable=True),
        sa.Column('encoding', sa.String(), nullable=True),
        sa.Column('container', sa.String(), nullable=True),
        sa.Column('times_used', sa.Integer(), nullable=True),
        sa.Column('average_satisfaction', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_voice_configurations_is_active', 'voice_configurations', ['is_active'], unique=False)
    op.create_index('ix_voice_configurations_name', 'voice_configurations', ['name'], unique=False)


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index('ix_voice_configurations_name', table_name='voice_configurations')
    op.drop_index('ix_voice_configurations_is_active', table_name='voice_configurations')
    op.drop_table('voice_configurations')

    op.drop_index('ix_cartesia_api_calls_voice_session_id', table_name='cartesia_api_calls')
    op.drop_index('ix_cartesia_api_calls_operation', table_name='cartesia_api_calls')
    op.drop_index('ix_cartesia_api_calls_created_at', table_name='cartesia_api_calls')
    op.drop_table('cartesia_api_calls')

    op.drop_index('ix_voice_turns_voice_session_id', table_name='voice_turns')
    op.drop_index('ix_voice_turns_total_latency_ms', table_name='voice_turns')
    op.drop_index('ix_voice_turns_started_at', table_name='voice_turns')
    op.drop_table('voice_turns')

    op.drop_index('ix_voice_session_logs_status', table_name='voice_session_logs')
    op.drop_index('ix_voice_session_logs_lead_id', table_name='voice_session_logs')
    op.drop_index('ix_voice_session_logs_created_at', table_name='voice_session_logs')
    op.drop_table('voice_session_logs')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS voicesessionstatus')