"""add_customer_platform_and_knowledge_base_tables

Revision ID: c4a5b9d2e8f1
Revises: af36f48fb48c
Create Date: 2025-01-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c4a5b9d2e8f1'
down_revision = 'af36f48fb48c'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create customers table
    op.create_table('customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('firebase_uid', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.String(length=128), nullable=False),
        sa.Column('api_key_hash', sa.String(length=256), nullable=True),
        sa.Column('subscription_tier', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_title', sa.String(length=200), nullable=True),
        sa.Column('company_website', sa.String(length=500), nullable=True),
        sa.Column('company_size', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=200), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_company_name'), 'customers', ['company_name'], unique=False)
    op.create_index(op.f('ix_customers_firebase_uid'), 'customers', ['firebase_uid'], unique=True)
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=True)
    op.create_index(op.f('ix_customers_api_key'), 'customers', ['api_key'], unique=True)
    op.create_index(op.f('ix_customers_status'), 'customers', ['status'], unique=False)
    
    # Create knowledge_documents table
    op.create_table('knowledge_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.String(length=128), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('firebase_storage_path', sa.String(length=1000), nullable=True),
        sa.Column('firebase_url', sa.String(length=2000), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('text_length', sa.Integer(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float(), dimensions=1), nullable=True),
        sa.Column('target_industries', sa.JSON(), nullable=True),
        sa.Column('company_sizes', sa.JSON(), nullable=True),
        sa.Column('decision_makers', sa.JSON(), nullable=True),
        sa.Column('target_regions', sa.JSON(), nullable=True),
        sa.Column('icp_data', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('processing_status', sa.String(length=50), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_documents_customer_id'), 'knowledge_documents', ['customer_id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_document_id'), 'knowledge_documents', ['document_id'], unique=True)
    
    # Create customer_agents table
    op.create_table('customer_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=False),
        sa.Column('agent_type', sa.String(length=100), nullable=False),
        sa.Column('agent_role', sa.String(length=100), nullable=True),
        sa.Column('deployment_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('total_tasks', sa.Integer(), nullable=True),
        sa.Column('completed_tasks', sa.Integer(), nullable=True),
        sa.Column('failed_tasks', sa.Integer(), nullable=True),
        sa.Column('average_latency_ms', sa.Float(), nullable=True),
        sa.Column('total_api_calls', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_agents_customer_id'), 'customer_agents', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_agents_deployment_id'), 'customer_agents', ['deployment_id'], unique=True)
    op.create_index(op.f('ix_customer_agents_status'), 'customer_agents', ['status'], unique=False)
    
    # Create customer_quotas table
    op.create_table('customer_quotas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('max_api_calls_per_day', sa.Integer(), nullable=True),
        sa.Column('max_api_calls_per_month', sa.Integer(), nullable=True),
        sa.Column('api_calls_today', sa.Integer(), nullable=True),
        sa.Column('api_calls_this_month', sa.Integer(), nullable=True),
        sa.Column('max_agents', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_agents', sa.Integer(), nullable=True),
        sa.Column('active_agents_count', sa.Integer(), nullable=True),
        sa.Column('max_leads_per_month', sa.Integer(), nullable=True),
        sa.Column('leads_this_month', sa.Integer(), nullable=True),
        sa.Column('max_storage_mb', sa.Integer(), nullable=True),
        sa.Column('storage_used_mb', sa.Float(), nullable=True),
        sa.Column('max_documents', sa.Integer(), nullable=True),
        sa.Column('documents_count', sa.Integer(), nullable=True),
        sa.Column('max_cost_per_month_usd', sa.Float(), nullable=True),
        sa.Column('cost_this_month_usd', sa.Float(), nullable=True),
        sa.Column('rate_limit_per_second', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
        sa.Column('last_daily_reset', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_monthly_reset', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_quotas_customer_id'), 'customer_quotas', ['customer_id'], unique=True)


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_customer_quotas_customer_id'), table_name='customer_quotas')
    op.drop_table('customer_quotas')
    
    op.drop_index(op.f('ix_customer_agents_status'), table_name='customer_agents')
    op.drop_index(op.f('ix_customer_agents_deployment_id'), table_name='customer_agents')
    op.drop_index(op.f('ix_customer_agents_customer_id'), table_name='customer_agents')
    op.drop_table('customer_agents')
    
    op.drop_index(op.f('ix_knowledge_documents_document_id'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_customer_id'), table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
    
    op.drop_index(op.f('ix_customers_status'), table_name='customers')
    op.drop_index(op.f('ix_customers_api_key'), table_name='customers')
    op.drop_index(op.f('ix_customers_email'), table_name='customers')
    op.drop_index(op.f('ix_customers_firebase_uid'), table_name='customers')
    op.drop_index(op.f('ix_customers_company_name'), table_name='customers')
    op.drop_table('customers')
    
    # Note: We don't drop the vector extension as it might be used elsewhere
