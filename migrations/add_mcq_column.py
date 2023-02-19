from sqlalchemy import Column, String
from alembic import op


def upgrade():
    op.add_column('card', Column('mcq', String(length=255)))

def downgrade():
    op.drop_column('card', 'mcq')