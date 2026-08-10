"""kategorie: user_token (NULL = globalna)

Revision ID: 482b348b2b66
Revises: e21ba7cff2e7
Create Date: 2026-08-10 18:11:51.100011

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '482b348b2b66'
down_revision = 'e21ba7cff2e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_token', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_categories_user_token'), ['user_token'], unique=False)
        batch_op.create_foreign_key('fk_categories_user_token_users', 'users', ['user_token'], ['token'])

    # Backfill: dotąd wszystkie kategorie były globalne (wspólne dla wszystkich
    # użytkowników). Przypisujemy je właścicielowi, który faktycznie prowadzi
    # księgowość — użytkownikowi z największą liczbą transakcji. Kategorie
    # systemowe ("Uzgadnianie salda") zostają globalne (user_token IS NULL),
    # bo tworzy je i używa sama aplikacja.
    #
    # Gdy baza nie ma jeszcze żadnych transakcji, podzapytanie zwraca NULL —
    # wszystkie kategorie zostają globalne, czyli dokładnie stan sprzed migracji.
    op.execute(
        "UPDATE categories "
        "SET user_token = ("
        "  SELECT user_token FROM transactions"
        "  GROUP BY user_token ORDER BY COUNT(*) DESC LIMIT 1"
        ") "
        "WHERE is_system_category = false"
    )


def downgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint('fk_categories_user_token_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_categories_user_token'))
        batch_op.drop_column('user_token')
