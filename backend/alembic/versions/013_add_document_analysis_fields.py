"""Add document analysis fields to KnowledgeDocument

Revision ID: 013_document_analysis
Revises: 012_conversation_intelligence
Create Date: 2025-10-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_document_analysis'
down_revision = '012_conversation_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add document analysis fields to knowledge_documents table
    op.add_column('knowledge_documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('key_items', sa.JSON(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('page_gists', sa.JSON(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('page_metadata', sa.JSON(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('analysis_status', sa.String(length=50), nullable=True, server_default='pending'))
    op.add_column('knowledge_documents', sa.Column('analysis_error', sa.Text(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('knowledge_documents', sa.Column('page_count', sa.Integer(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('compression_ratio', sa.Float(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('processing_time_ms', sa.Integer(), nullable=True))

    # Create index on analysis_status for efficient filtering
    op.create_index('ix_knowledge_documents_analysis_status', 'knowledge_documents', ['analysis_status'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_knowledge_documents_analysis_status', table_name='knowledge_documents')

    # Remove document analysis fields
    op.drop_column('knowledge_documents', 'processing_time_ms')
    op.drop_column('knowledge_documents', 'compression_ratio')
    op.drop_column('knowledge_documents', 'page_count')
    op.drop_column('knowledge_documents', 'analyzed_at')
    op.drop_column('knowledge_documents', 'analysis_error')
    op.drop_column('knowledge_documents', 'analysis_status')
    op.drop_column('knowledge_documents', 'page_metadata')
    op.drop_column('knowledge_documents', 'page_gists')
    op.drop_column('knowledge_documents', 'key_items')
    op.drop_column('knowledge_documents', 'summary')
