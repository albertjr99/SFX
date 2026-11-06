"""albert: administrador e plano de ação, como o Lucas

Revision ID: d5e9f3a1b2c7
Revises: c4d8e1f2a7b6
Create Date: 2026-11-06 17:05:00
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e9f3a1b2c7"
down_revision = "c4d8e1f2a7b6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text("UPDATE usuario SET administrador = :v, pode_plano_acao = :v WHERE lower(nome) = 'albert'").bindparams(
            v=True
        )
    )


def downgrade():
    op.execute(sa.text("UPDATE usuario SET administrador = :v WHERE lower(nome) = 'albert'").bindparams(v=False))
