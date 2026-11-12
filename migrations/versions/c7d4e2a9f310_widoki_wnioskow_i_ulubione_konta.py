"""widoki wnioskow (saved_views) i ulubione konta (accounts.is_favorite)

Revision ID: c7d4e2a9f310
Revises: b2c1b9e091ff
Create Date: 2026-11-12 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d4e2a9f310'
down_revision = 'b2c1b9e091ff'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('saved_views',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_token', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('config', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_token'], ['users.token'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('saved_views', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_saved_views_user_token'), ['user_token'], unique=False)

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_favorite', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('is_favorite')

    with op.batch_alter_table('saved_views', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_saved_views_user_token'))

    op.drop_table('saved_views')
