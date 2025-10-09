"""Add conversation intelligence models

Revision ID: 012_conversation_intelligence
Revises: 011_optimize_lead_model_indexes_constraints
Create Date: 2025-10-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_conversation_intelligence'
down_revision = '011_lead_optimization'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE conversationstatus AS ENUM ('active', 'completed', 'paused', 'error', 'abandoned');
        CREATE TYPE speakerrole AS ENUM ('agent', 'prospect', 'system');
        CREATE TYPE sentimenttype AS ENUM ('positive', 'neutral', 'negative', 'mixed');
        CREATE TYPE battlecardtype AS ENUM ('pricing', 'competitor', 'feature', 'objection', 'case_study', 'technical', 'general');
    """)

    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('active', 'completed', 'paused', 'error', 'abandoned', name='conversationstatus'), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('total_audio_seconds', sa.Float(), nullable=True),
        sa.Column('audio_quality_score', sa.Float(), nullable=True),
        sa.Column('total_turns', sa.Integer(), nullable=True),
        sa.Column('agent_turns', sa.Integer(), nullable=True),
        sa.Column('prospect_turns', sa.Integer(), nullable=True),
        sa.Column('overall_sentiment', sa.Enum('positive', 'neutral', 'negative', 'mixed', name='sentimenttype'), nullable=True),
        sa.Column('average_sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_trend', sa.String(), nullable=True),
        sa.Column('detected_topics', sa.JSON(), nullable=True),
        sa.Column('key_objections', sa.JSON(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('total_suggestions_shown', sa.Integer(), nullable=True),
        sa.Column('total_suggestions_used', sa.Integer(), nullable=True),
        sa.Column('suggestion_usage_rate', sa.Float(), nullable=True),
        sa.Column('total_battle_cards_shown', sa.Integer(), nullable=True),
        sa.Column('total_battle_cards_used', sa.Integer(), nullable=True),
        sa.Column('battle_card_usage_rate', sa.Float(), nullable=True),
        sa.Column('average_transcription_latency_ms', sa.Integer(), nullable=True),
        sa.Column('average_analysis_latency_ms', sa.Integer(), nullable=True),
        sa.Column('average_total_latency_ms', sa.Integer(), nullable=True),
        sa.Column('final_outcome', sa.String(), nullable=True),
        sa.Column('next_action', sa.Text(), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('agent_notes', sa.Text(), nullable=True),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_lead_id', 'conversations', ['lead_id'], unique=False)
    op.create_index('ix_conversations_status', 'conversations', ['status'], unique=False)
    op.create_index('ix_conversations_started_at', 'conversations', ['started_at'], unique=False)
    op.create_index('ix_conversations_overall_sentiment', 'conversations', ['overall_sentiment'], unique=False)

    # Create conversation_turns table
    op.create_table(
        'conversation_turns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('turn_number', sa.Integer(), nullable=True),
        sa.Column('speaker', sa.Enum('agent', 'prospect', 'system', name='speakerrole'), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('transcription_confidence', sa.Float(), nullable=True),
        sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('sentiment', sa.Enum('positive', 'neutral', 'negative', 'mixed', name='sentimenttype'), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('detected_emotions', sa.JSON(), nullable=True),
        sa.Column('detected_topics', sa.JSON(), nullable=True),
        sa.Column('detected_keywords', sa.JSON(), nullable=True),
        sa.Column('is_objection', sa.Boolean(), nullable=True),
        sa.Column('is_question', sa.Boolean(), nullable=True),
        sa.Column('is_commitment', sa.Boolean(), nullable=True),
        sa.Column('suggestions', sa.JSON(), nullable=True),
        sa.Column('suggestion_shown', sa.Boolean(), nullable=True),
        sa.Column('suggestion_used', sa.Boolean(), nullable=True),
        sa.Column('suggestion_used_index', sa.Integer(), nullable=True),
        sa.Column('transcription_latency_ms', sa.Integer(), nullable=True),
        sa.Column('sentiment_analysis_latency_ms', sa.Integer(), nullable=True),
        sa.Column('suggestion_generation_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_latency_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_turns_conversation_id', 'conversation_turns', ['conversation_id'], unique=False)
    op.create_index('ix_conversation_turns_speaker', 'conversation_turns', ['speaker'], unique=False)
    op.create_index('ix_conversation_turns_sentiment', 'conversation_turns', ['sentiment'], unique=False)
    op.create_index('ix_conversation_turns_started_at', 'conversation_turns', ['started_at'], unique=False)

    # Create conversation_battle_cards table
    op.create_table(
        'conversation_battle_cards',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('card_type', sa.Enum('pricing', 'competitor', 'feature', 'objection', 'case_study', 'technical', 'general', name='battlecardtype'), nullable=False),
        sa.Column('trigger_keyword', sa.String(), nullable=True),
        sa.Column('trigger_turn_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('talking_points', sa.JSON(), nullable=True),
        sa.Column('response_template', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('suggested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('viewed_at', sa.DateTime(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('was_helpful', sa.Boolean(), nullable=True),
        sa.Column('time_to_view_seconds', sa.Integer(), nullable=True),
        sa.Column('time_to_use_seconds', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_battle_cards_conversation_id', 'conversation_battle_cards', ['conversation_id'], unique=False)
    op.create_index('ix_conversation_battle_cards_card_type', 'conversation_battle_cards', ['card_type'], unique=False)
    op.create_index('ix_conversation_battle_cards_suggested_at', 'conversation_battle_cards', ['suggested_at'], unique=False)

    # Create battle_card_templates table
    op.create_table(
        'battle_card_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('card_type', sa.Enum('pricing', 'competitor', 'feature', 'objection', 'case_study', 'technical', 'general', name='battlecardtype'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('talking_points', sa.JSON(), nullable=True),
        sa.Column('response_template', sa.Text(), nullable=True),
        sa.Column('trigger_keywords', sa.JSON(), nullable=False),
        sa.Column('trigger_phrases', sa.JSON(), nullable=True),
        sa.Column('trigger_topics', sa.JSON(), nullable=True),
        sa.Column('times_triggered', sa.Integer(), nullable=True),
        sa.Column('times_used', sa.Integer(), nullable=True),
        sa.Column('average_helpfulness_score', sa.Float(), nullable=True),
        sa.Column('usage_rate', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_battle_card_templates_card_type', 'battle_card_templates', ['card_type'], unique=False)
    op.create_index('ix_battle_card_templates_is_active', 'battle_card_templates', ['is_active'], unique=False)
    op.create_index('ix_battle_card_templates_priority', 'battle_card_templates', ['priority'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index('ix_battle_card_templates_priority', table_name='battle_card_templates')
    op.drop_index('ix_battle_card_templates_is_active', table_name='battle_card_templates')
    op.drop_index('ix_battle_card_templates_card_type', table_name='battle_card_templates')
    op.drop_table('battle_card_templates')

    op.drop_index('ix_conversation_battle_cards_suggested_at', table_name='conversation_battle_cards')
    op.drop_index('ix_conversation_battle_cards_card_type', table_name='conversation_battle_cards')
    op.drop_index('ix_conversation_battle_cards_conversation_id', table_name='conversation_battle_cards')
    op.drop_table('conversation_battle_cards')

    op.drop_index('ix_conversation_turns_started_at', table_name='conversation_turns')
    op.drop_index('ix_conversation_turns_sentiment', table_name='conversation_turns')
    op.drop_index('ix_conversation_turns_speaker', table_name='conversation_turns')
    op.drop_index('ix_conversation_turns_conversation_id', table_name='conversation_turns')
    op.drop_table('conversation_turns')

    op.drop_index('ix_conversations_overall_sentiment', table_name='conversations')
    op.drop_index('ix_conversations_started_at', table_name='conversations')
    op.drop_index('ix_conversations_status', table_name='conversations')
    op.drop_index('ix_conversations_lead_id', table_name='conversations')
    op.drop_table('conversations')

    # Drop enum types
    op.execute("""
        DROP TYPE IF EXISTS battlecardtype;
        DROP TYPE IF EXISTS sentimenttype;
        DROP TYPE IF EXISTS speakerrole;
        DROP TYPE IF EXISTS conversationstatus;
    """)
