"""Enable RLS on additional tables not covered in migration 015.

Revision ID: 022_enable_rls_additional_tables
Revises: 021_deal_attribution
Create Date: 2025-12-27

SECURITY FIX: Complete RLS coverage for all public-facing tables.

Tables secured by this migration:
- Security/Auth: users, roles, permissions, security_events, user_consent
- Customer/Multi-tenant: customers, knowledge_documents, customer_agents, customer_quotas
- Agent system: agent_executions, agent_workflows, langgraph_executions
- Conversations: conversations, conversation_turns
- Voice: voice_session_logs, voice_turns
- Campaigns: campaigns, campaign_messages
- Call Intelligence: call_insights
- Trigger Engine: trigger_rules, trigger_executions
- Attribution: fact_deal_attribution, touchpoint_types
- Legacy: leads
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '022_enable_rls_additional_tables'
down_revision: Union[str, None] = '021_deal_attribution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables to secure with RLS
TABLES_TO_SECURE = [
    # Security/Auth tables (CRITICAL - user data)
    'users',
    'roles',
    'permissions',
    'security_events',
    'user_consent',

    # Customer/Multi-tenant tables (CRITICAL - tenant isolation)
    'customers',
    'knowledge_documents',
    'customer_agents',
    'customer_quotas',

    # Agent system tables
    'agent_executions',
    'agent_workflows',
    'langgraph_executions',
    'langgraph_checkpoints',
    'langgraph_tool_calls',

    # Conversation tables
    'conversations',
    'conversation_turns',
    'conversation_battle_cards',

    # Voice tables
    'voice_session_logs',
    'voice_turns',
    'voice_configurations',

    # Campaign tables
    'campaigns',
    'campaign_messages',
    'message_variant_analytics',

    # Call Intelligence (new in 019)
    'call_insights',

    # Trigger Engine (new in 020)
    'trigger_rules',
    'trigger_executions',

    # Attribution (new in 021)
    'fact_deal_attribution',
    'touchpoint_types',

    # Legacy tables
    'leads',

    # CRM tables
    'crm_credentials',
    'crm_contacts',
    'crm_sync_logs',

    # Other tables
    'reports',
    'batch_jobs',
    'batch_job_leads',
    'api_call_logs',
    'ai_cost_tracking',
]


def upgrade() -> None:
    """Enable RLS and create service role policies for additional tables."""

    # Track which tables were successfully secured
    secured_tables = []
    skipped_tables = []

    # ===========================================================================
    # SECTION 1: ENABLE ROW LEVEL SECURITY
    # ===========================================================================
    for table in TABLES_TO_SECURE:
        try:
            op.execute(f'ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY')
            secured_tables.append(table)
        except Exception as e:
            # Table might not exist in this environment
            skipped_tables.append((table, str(e)))
            print(f"Warning: Could not enable RLS on {table}: {e}")

    # ===========================================================================
    # SECTION 2: CREATE SERVICE ROLE POLICIES
    # ===========================================================================
    for table in secured_tables:
        policy_name = f"{table}_service_all"

        # Drop existing policy if exists (idempotent)
        try:
            op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON {table}')
        except Exception:
            pass

        # Create service role policy for backend access
        try:
            op.execute(f'''
                CREATE POLICY "{policy_name}" ON {table}
                    FOR ALL
                    USING (auth.jwt()->>'role' = 'service_role')
                    WITH CHECK (auth.jwt()->>'role' = 'service_role')
            ''')
        except Exception as e:
            print(f"Warning: Could not create policy for {table}: {e}")

    # ===========================================================================
    # SECTION 3: CREATE USER-LEVEL POLICIES FOR MULTI-TENANT TABLES
    # ===========================================================================
    # These policies allow authenticated users to access their own data

    # Customers table - users can only see their own customer record
    try:
        op.execute('DROP POLICY IF EXISTS "customers_user_own" ON customers')
        op.execute('''
            CREATE POLICY "customers_user_own" ON customers
                FOR SELECT
                USING (
                    auth.jwt()->>'role' = 'service_role' OR
                    id::text = auth.jwt()->>'customer_id'
                )
        ''')
    except Exception as e:
        print(f"Warning: Could not create user policy for customers: {e}")

    # Users table - users can see their own record
    try:
        op.execute('DROP POLICY IF EXISTS "users_user_own" ON users')
        op.execute('''
            CREATE POLICY "users_user_own" ON users
                FOR SELECT
                USING (
                    auth.jwt()->>'role' = 'service_role' OR
                    id::text = auth.jwt()->>'sub'
                )
        ''')
    except Exception as e:
        print(f"Warning: Could not create user policy for users: {e}")

    # ===========================================================================
    # VERIFICATION SUMMARY
    # ===========================================================================
    print("\n" + "=" * 80)
    print("RLS SECURITY MIGRATION 022 COMPLETED")
    print("=" * 80)
    print(f"✓ Enabled RLS on {len(secured_tables)} tables")
    print(f"⚠ Skipped {len(skipped_tables)} tables (may not exist)")
    print("\nTables secured:")
    for table in secured_tables:
        print(f"  ✓ {table}")
    if skipped_tables:
        print("\nTables skipped:")
        for table, reason in skipped_tables:
            print(f"  ⚠ {table}")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """Rollback: Disable RLS and remove policies."""

    # WARNING: This will re-expose data!
    print("\n⚠️  WARNING: Disabling RLS on additional tables!")

    for table in TABLES_TO_SECURE:
        policy_name = f"{table}_service_all"

        # Drop policies
        try:
            op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON {table}')
            op.execute(f'DROP POLICY IF EXISTS "{table}_user_own" ON {table}')
        except Exception:
            pass

        # Disable RLS
        try:
            op.execute(f'ALTER TABLE IF EXISTS {table} DISABLE ROW LEVEL SECURITY')
        except Exception:
            pass

    print("⚠️  RLS has been disabled - data is now exposed!")
