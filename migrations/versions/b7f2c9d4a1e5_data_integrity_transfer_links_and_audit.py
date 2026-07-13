"""data integrity: transfer links, schedule source ids, fuller archive

Revision ID: b7f2c9d4a1e5
Revises: 4b85c5d7b8c2
Create Date: 2026-07-13 10:00:00.000000

Dodaje kolumny wspierające poprawki integralności danych finansowych:
- transactions.linked_transaction_id  — twarde powiązanie dwóch stron przelewu wewnętrznego
- transactions.source_recurring_id    — ślad pochodzenia z definicji cyklicznej (idempotentność)
- transactions.source_planned_id      — ślad pochodzenia z definicji zaplanowanej (idempotentność)
- contractors.linked_account_id       — twarde powiązanie kontrahenta "Moje konto: X" z kontem
- transaction_archive.comment / contractor_raw / splits_json — pełny ślad audytowy

Migracja backfilluje contractors.linked_account_id na podstawie dotychczasowej
konwencji nazewniczej "Moje konto: {nazwa konta}".
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f2c9d4a1e5'
down_revision = '4b85c5d7b8c2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('linked_transaction_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_recurring_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_planned_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'transactions_linked_transaction_id_fkey', 'transactions',
            ['linked_transaction_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'transactions_source_recurring_id_fkey', 'recurring_transactions',
            ['source_recurring_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'transactions_source_planned_id_fkey', 'planned_transactions',
            ['source_planned_id'], ['id'], ondelete='SET NULL'
        )

    with op.batch_alter_table('contractors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('linked_account_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'contractors_linked_account_id_fkey', 'accounts',
            ['linked_account_id'], ['id']
        )

    with op.batch_alter_table('transaction_archive', schema=None) as batch_op:
        batch_op.add_column(sa.Column('comment', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('contractor_raw', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('splits_json', sa.Text(), nullable=True))

    # Backfill: powiąż istniejących kontrahentów "Moje konto: {nazwa}" z kontem po nazwie.
    # substring od pozycji 13 = pominięcie prefiksu "Moje konto: " (12 znaków).
    op.execute(sa.text(
        "UPDATE contractors SET linked_account_id = ("
        "  SELECT a.id FROM accounts a"
        "  WHERE a.user_token = contractors.user_token"
        "    AND a.name = substring(contractors.name from 13)"
        "  LIMIT 1"
        ") WHERE contractors.name LIKE 'Moje konto: %'"
    ))


def downgrade():
    with op.batch_alter_table('transaction_archive', schema=None) as batch_op:
        batch_op.drop_column('splits_json')
        batch_op.drop_column('contractor_raw')
        batch_op.drop_column('comment')

    with op.batch_alter_table('contractors', schema=None) as batch_op:
        batch_op.drop_constraint('contractors_linked_account_id_fkey', type_='foreignkey')
        batch_op.drop_column('linked_account_id')

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint('transactions_source_planned_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('transactions_source_recurring_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('transactions_linked_transaction_id_fkey', type_='foreignkey')
        batch_op.drop_column('source_planned_id')
        batch_op.drop_column('source_recurring_id')
        batch_op.drop_column('linked_transaction_id')
