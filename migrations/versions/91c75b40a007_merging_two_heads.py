"""merging two heads

Revision ID: 91c75b40a007
Revises: 10a9367a3a92, bed95d9c18a2, c363bf43a44b
Create Date: 2023-03-08 18:49:39.847266

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91c75b40a007'
down_revision = ('10a9367a3a92', 'bed95d9c18a2', 'c363bf43a44b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
