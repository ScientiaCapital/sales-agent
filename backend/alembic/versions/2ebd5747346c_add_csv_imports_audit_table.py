"""add_csv_imports_audit_table

Revision ID: 2ebd5747346c
Revises: aa04f1da746c
Create Date: 2025-11-16 08:47:19.794006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ebd5747346c'
down_revision: Union[str, None] = 'aa04f1da746c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create csv_imports audit table
    op.create_table(
        'csv_imports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_rows', sa.Integer(), nullable=False),
        sa.Column('processed_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost_usd', sa.Numeric(precision=10, scale=6), nullable=False, server_default='0.0'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('started_processing_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('idx_csv_imports_status', 'csv_imports', ['status'])
    op.create_index('idx_csv_imports_uploaded_at', 'csv_imports', ['uploaded_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_csv_imports_uploaded_at', table_name='csv_imports')
    op.drop_index('idx_csv_imports_status', table_name='csv_imports')

    # Drop table
    op.drop_table('csv_imports')
