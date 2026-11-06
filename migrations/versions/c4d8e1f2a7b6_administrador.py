"""administrador: acesso total somado ao perfil

Revision ID: c4d8e1f2a7b6
Revises: b7e4c2a91d35
Create Date: 2026-11-06 16:50:00

O Lucas (analista) passa a ser administrador do sistema, mantendo o perfil de analista.
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d8e1f2a7b6"
down_revision = "b7e4c2a91d35"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("administrador", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        sa.text("UPDATE usuario SET administrador = :v, pode_plano_acao = :v WHERE lower(nome) = 'lucas'").bindparams(
            v=True
        )
    )


def downgrade():
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("administrador")
