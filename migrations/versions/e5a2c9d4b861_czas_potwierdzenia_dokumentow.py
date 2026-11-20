"""czas potwierdzenia dokumentow prawnych (users.legal_docs_ack_at)

Revision ID: e5a2c9d4b861
Revises: d8e3f1b7a5c2
Create Date: 2026-11-20 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a2c9d4b861'
down_revision = 'd8e3f1b7a5c2'
branch_labels = None
depends_on = None


def upgrade():
    # NULL = brak kliknięcia "Rozumiem" (konto sprzed banera albo wersja przyjęta przy rejestracji).
    op.add_column('users', sa.Column('legal_docs_ack_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'legal_docs_ack_at')
