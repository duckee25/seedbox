"""empty message

Revision ID: 91248bf831b8
Revises: b70159a8c7c2
Create Date: 2017-04-27 17:31:28.639958

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91248bf831b8'
down_revision = 'b70159a8c7c2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cluster', sa.Column('k8s_is_rbac_enabled', sa.Boolean(), nullable=False, server_default='TRUE'))
    op.alter_column('cluster', 'k8s_is_rbac_enabled', server_default=None)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('cluster', 'k8s_is_rbac_enabled')
    # ### end Alembic commands ###
