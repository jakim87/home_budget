"""check constraint interval gte 1 dla recurring_transactions

Revision ID: e1ca3132bdf5
Revises: 3923305e558c
Create Date: 2026-08-24 13:51:01.713203

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1ca3132bdf5'
down_revision = '3923305e558c'
branch_labels = None
depends_on = None


def upgrade():
    # ck_recurring_transactions_interval_positive: interval=0 zapetla
    # process_recurring_transactions (next_run_date sie nie posuwa) — patrz
    # bezpiecznik w app/services/recurring_service.py. Sprawdzone przed migracja:
    # zadnego istniejacego wiersza z interval < 1 (constraint wymuszony w app/models.py).
    op.create_check_constraint(
        'ck_recurring_transactions_interval_positive',
        'recurring_transactions',
        'interval >= 1',
    )


def downgrade():
    op.drop_constraint(
        'ck_recurring_transactions_interval_positive',
        'recurring_transactions',
        type_='check',
    )
