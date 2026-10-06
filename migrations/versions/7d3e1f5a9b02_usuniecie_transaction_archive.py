"""usunięcie tabeli transaction_archive (twarde usuwanie transakcji, #161)

Revision ID: 7d3e1f5a9b02
Revises: c4a16ece798f
Create Date: 2026-10-06 12:00:00.000000

Tabela znika razem z zawartością — to także wykonanie obietnicy, że usunięte
transakcje nie są przechowywane. downgrade odtwarza pustą tabelę, danych nie.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d3e1f5a9b02'
down_revision = 'c4a16ece798f'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('transaction_archive')


def downgrade():
    op.create_table('transaction_archive',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('original_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('contractor_id', sa.Integer(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('user_token', sa.String(length=36), nullable=False),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('contractor_raw', sa.String(length=255), nullable=True),
    sa.Column('splits_json', sa.Text(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_token'], ['users.token']),
    sa.PrimaryKeyConstraint('id')
    )
