"""Merge migration heads

Revision ID: 0293cbeb9305
Revises: 013_document_analysis, ebf714f5f7b9
Create Date: 2025-10-28 19:03:28.471312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0293cbeb9305'
down_revision: Union[str, None] = ('013_document_analysis', 'ebf714f5f7b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
