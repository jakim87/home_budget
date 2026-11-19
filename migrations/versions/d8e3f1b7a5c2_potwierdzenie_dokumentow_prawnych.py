"""potwierdzenie zmiany dokumentow prawnych (users.legal_docs_ack)

Revision ID: d8e3f1b7a5c2
Revises: c7d4e2a9f310
Create Date: 2026-11-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e3f1b7a5c2'
down_revision = 'c7d4e2a9f310'
branch_labels = None
depends_on = None


def upgrade():
    # NULL = nie potwierdzał — istniejący użytkownicy zobaczą baner raz.
    op.add_column('users', sa.Column('legal_docs_ack', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('users', 'legal_docs_ack')
