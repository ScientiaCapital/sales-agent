"""
Add OEM tracking and MEP+E scoring fields to leads table

Revision ID: 20251030_add_oem_tracking_fields
Revises: 20251030_add_report_templates
Create Date: 2025-10-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251030_add_oem_tracking_fields'
down_revision = '094a9deda846'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add OEM tracking fields for MEP+E scoring algorithm.

    Fields Added:
    - OEM Category Counts (6): hvac, solar, battery, generator, smart_panel, iot
    - OEM Details (2): oems_certified (JSON list), oem_tiers (JSON dict)
    - OEM Scoring (2): total_oem_count, mep_e_score
    - Service Capability Flags (10): has_hvac, has_solar, has_battery, etc.
    - ICP Category Scores (3): renewable_readiness, asset_centric, projects_service
    """

    # OEM Category Counts (6 fields)
    op.add_column('leads', sa.Column('hvac_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('solar_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('battery_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('generator_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('smart_panel_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('iot_oem_count', sa.Integer(), nullable=False, server_default='0'))

    # OEM Details (2 fields)
    op.add_column('leads', sa.Column('oems_certified', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'))
    op.add_column('leads', sa.Column('oem_tiers', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'))

    # OEM Scoring (2 fields)
    op.add_column('leads', sa.Column('total_oem_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('mep_e_score', sa.Integer(), nullable=False, server_default='0'))

    # Service Capability Flags (10 fields)
    op.add_column('leads', sa.Column('has_hvac', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_solar', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_battery', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_generator', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_ev_charger', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_smart_panel', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_heat_pump', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_microgrid', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_commercial', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leads', sa.Column('has_ops_maintenance', sa.Boolean(), nullable=False, server_default='false'))

    # ICP Category Scores (3 fields)
    op.add_column('leads', sa.Column('renewable_readiness_score', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('asset_centric_score', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('projects_service_score', sa.Integer(), nullable=False, server_default='0'))

    # Add indexes for commonly queried fields
    op.create_index('idx_leads_mep_e_score', 'leads', ['mep_e_score'], unique=False)
    op.create_index('idx_leads_total_oem_count', 'leads', ['total_oem_count'], unique=False)


def downgrade() -> None:
    """Remove OEM tracking fields"""

    # Drop indexes first
    op.drop_index('idx_leads_total_oem_count', table_name='leads')
    op.drop_index('idx_leads_mep_e_score', table_name='leads')

    # Drop ICP Category Scores
    op.drop_column('leads', 'projects_service_score')
    op.drop_column('leads', 'asset_centric_score')
    op.drop_column('leads', 'renewable_readiness_score')

    # Drop Service Capability Flags
    op.drop_column('leads', 'has_ops_maintenance')
    op.drop_column('leads', 'has_commercial')
    op.drop_column('leads', 'has_microgrid')
    op.drop_column('leads', 'has_heat_pump')
    op.drop_column('leads', 'has_smart_panel')
    op.drop_column('leads', 'has_ev_charger')
    op.drop_column('leads', 'has_generator')
    op.drop_column('leads', 'has_battery')
    op.drop_column('leads', 'has_solar')
    op.drop_column('leads', 'has_hvac')

    # Drop OEM Scoring
    op.drop_column('leads', 'mep_e_score')
    op.drop_column('leads', 'total_oem_count')

    # Drop OEM Details
    op.drop_column('leads', 'oem_tiers')
    op.drop_column('leads', 'oems_certified')

    # Drop OEM Category Counts
    op.drop_column('leads', 'iot_oem_count')
    op.drop_column('leads', 'smart_panel_oem_count')
    op.drop_column('leads', 'generator_oem_count')
    op.drop_column('leads', 'battery_oem_count')
    op.drop_column('leads', 'solar_oem_count')
    op.drop_column('leads', 'hvac_oem_count')
