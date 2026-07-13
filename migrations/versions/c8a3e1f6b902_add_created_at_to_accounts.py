"""add created_at to accounts

Revision ID: c8a3e1f6b902
Revises: b7f2c9d4a1e5
Create Date: 2026-07-13 11:00:00.000000

Dodaje kolumnę accounts.created_at (data dodania konta do słownika). Konta
istniejące przed migracją otrzymują znacznik czasu migracji (server_default now()) —
nie znamy ich rzeczywistej daty utworzenia. Kolejne konta zapisują prawdziwą datę.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8a3e1f6b902'
down_revision = 'b7f2c9d4a1e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False
        ))


def downgrade():
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('created_at')
