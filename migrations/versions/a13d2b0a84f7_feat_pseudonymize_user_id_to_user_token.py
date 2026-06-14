"""feat: pseudonymize user_id to user_token

Revision ID: a13d2b0a84f7
Revises: 79344ae08191
Create Date: 2026-06-14 23:00:05.339977

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a13d2b0a84f7'
down_revision = '79344ae08191'
branch_labels = None
depends_on = None

# Tabele finansowe z NOT NULL user_token
_REQUIRED_TABLES = [
    'accounts',
    'budgets',
    'contractors',
    'planned_transactions',
    'recurring_transactions',
    'transaction_archive',
    'transactions',
]

# Tabele finansowe z Optional user_token
_OPTIONAL_TABLES = [
    'transaction_staging',
]


def upgrade():
    conn = op.get_bind()

    # 1. Dodaj users.token (nullable tymczasowo)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token', sa.String(length=36), nullable=True))

    # 2. Wygeneruj UUID dla każdego istniejącego użytkownika
    conn.execute(text("UPDATE users SET token = gen_random_uuid()::text WHERE token IS NULL"))

    # 3. Ustaw NOT NULL + UNIQUE + indeks
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('token', nullable=False)
        batch_op.create_index(batch_op.f('ix_users_token'), ['token'], unique=True)

    # 4. Przepisz user_id → user_token w tabelach wymaganych (NOT NULL)
    for table in _REQUIRED_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_token', sa.String(length=36), nullable=True))

        conn.execute(text(
            f"UPDATE {table} SET user_token = (SELECT token FROM users WHERE users.id = {table}.user_id)"
        ))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('user_token', nullable=False)
            batch_op.create_foreign_key(f'{table}_user_token_fkey', 'users', ['user_token'], ['token'])
            if table in ('planned_transactions', 'recurring_transactions'):
                batch_op.drop_index(batch_op.f(f'ix_{table}_user_id'))
                batch_op.create_index(batch_op.f(f'ix_{table}_user_token'), ['user_token'], unique=False)
            if table != 'transaction_archive':
                batch_op.drop_constraint(batch_op.f(f'{table}_user_id_fkey'), type_='foreignkey')
            batch_op.drop_column('user_id')

    # 5. Przepisz user_id → user_token w tabelach opcjonalnych
    for table in _OPTIONAL_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_token', sa.String(length=36), nullable=True))

        conn.execute(text(
            f"UPDATE {table} SET user_token = (SELECT token FROM users WHERE users.id = {table}.user_id)"
            f" WHERE {table}.user_id IS NOT NULL"
        ))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_foreign_key(f'{table}_user_token_fkey', 'users', ['user_token'], ['token'])
            batch_op.drop_constraint(batch_op.f(f'{table}_user_id_fkey'), type_='foreignkey')
            batch_op.drop_column('user_id')


def downgrade():
    conn = op.get_bind()

    # Opcjonalne tabele
    for table in _OPTIONAL_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))

        conn.execute(text(
            f"UPDATE {table} SET user_id = (SELECT id FROM users WHERE users.token = {table}.user_token)"
            f" WHERE {table}.user_token IS NOT NULL"
        ))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'{table}_user_token_fkey', type_='foreignkey')
            batch_op.create_foreign_key(batch_op.f(f'{table}_user_id_fkey'), 'users', ['user_id'], ['id'])
            batch_op.drop_column('user_token')

    # Wymagane tabele
    for table in reversed(_REQUIRED_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))

        conn.execute(text(
            f"UPDATE {table} SET user_id = (SELECT id FROM users WHERE users.token = {table}.user_token)"
        ))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('user_id', nullable=False)
            batch_op.drop_constraint(f'{table}_user_token_fkey', type_='foreignkey')
            if table != 'transaction_archive':
                batch_op.create_foreign_key(batch_op.f(f'{table}_user_id_fkey'), 'users', ['user_id'], ['id'])
            if table in ('planned_transactions', 'recurring_transactions'):
                batch_op.drop_index(batch_op.f(f'ix_{table}_user_token'))
                batch_op.create_index(batch_op.f(f'ix_{table}_user_id'), ['user_id'], unique=False)
            batch_op.drop_column('user_token')

    # Usuń token z users
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_token'))
        batch_op.drop_column('token')
