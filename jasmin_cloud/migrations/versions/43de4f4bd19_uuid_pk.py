"""uuid_pk

Revision ID: 43de4f4bd19
Revises: 2da92b07e42
Create Date: 2015-10-27 11:06:06.802287

"""

# revision identifiers, used by Alembic.
revision = '43de4f4bd19'
down_revision = '2da92b07e42'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

from jasmin_cloud.util import UUIDType


def upgrade():
    # Create new table with uuid primary key
    op.create_table('catalogue_meta_tmp',
        sa.Column('id', UUIDType(), nullable=False),
        sa.Column('cloud_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('allow_inbound', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from the old table, generating random UUIDs as we go
    # NOTE: This syntax is PostgreSQL only...
    op.execute(
        'INSERT INTO catalogue_meta_tmp '
        'SELECT md5(random()::text)::uuid, cm.cloud_id, cm.name, cm.description, cm.allow_inbound '
        'FROM catalogue_meta AS cm'
    )
    
    # Drop the old table and rename
    op.drop_table('catalogue_meta')
    op.rename_table('catalogue_meta_tmp', 'catalogue_meta')


def downgrade():
    # Recreate old table with integer primary key
    op.create_table('catalogue_meta_tmp',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cloud_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('allow_inbound', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from the catalogue_meta table, letting the id autoincrement
    op.execute(
        'INSERT INTO catalogue_meta_tmp (cloud_id, name, description, allow_inbound) '
        'SELECT cm.cloud_id, cm.name, cm.description, cm.allow_inbound '
        'FROM catalogue_meta AS cm'
    )
    
    # Drop the old table and rename
    op.drop_table('catalogue_meta')
    op.rename_table('catalogue_meta_tmp', 'catalogue_meta')
    