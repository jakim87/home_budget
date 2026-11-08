"""poczekalnia pamięta plik, z którego przyszedł wiersz (odrzucanie pliku)

Revision ID: a1c2e3f4b5d6
Revises: 7d3e1f5a9b02
Create Date: 2026-11-08 12:00:00.000000

Istniejące wiersze dostają NULL — nie wiadomo, z którego pliku przyszły.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2e3f4b5d6'
down_revision = '7d3e1f5a9b02'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transaction_staging', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_batch_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_transaction_staging_import_batch_id'), ['import_batch_id'], unique=False)


def downgrade():
    with op.batch_alter_table('transaction_staging', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transaction_staging_import_batch_id'))
        batch_op.drop_column('import_batch_id')
