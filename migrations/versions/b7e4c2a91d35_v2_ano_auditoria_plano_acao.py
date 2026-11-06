"""v2: ano nas linhas, auditoria, usuários ativos e plano de ação no banco

Revision ID: b7e4c2a91d35
Revises: ecf042e679b9
Create Date: 2026-11-06 16:30:00

- linha_producao.ano: até a v1 o mês era gravado só pelo nome ("Julho"), o que
  misturaria anos diferentes. O ano é preenchido a partir de data_registro.
- linha_producao.atualizado_em / atualizado_por_id: quem alterou por último.
- usuario.ativo / usuario.pode_plano_acao: desativar acessos sem apagar
  histórico e liberar o plano de ação sem depender do nome no código.
- plano_acao_ciclo / plano_acao_mes: substituem a planilha data/Pasta2.xlsx.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e4c2a91d35"
down_revision = "ecf042e679b9"
branch_labels = None
depends_on = None

ANO_PADRAO = 2025  # a v1 entrou em uso em junho de 2025


def upgrade():
    bind = op.get_bind()

    with op.batch_alter_table("linha_producao", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ano", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("atualizado_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("atualizado_por_id", sa.Integer(), nullable=True))

    if bind.dialect.name == "sqlite":
        op.execute(
            "UPDATE linha_producao SET ano = CAST(strftime('%Y', data_registro) AS INTEGER) "
            "WHERE data_registro IS NOT NULL"
        )
    else:
        op.execute("UPDATE linha_producao SET ano = EXTRACT(YEAR FROM data_registro) WHERE data_registro IS NOT NULL")
    op.execute(f"UPDATE linha_producao SET ano = {ANO_PADRAO} WHERE ano IS NULL")
    op.execute("UPDATE linha_producao SET atualizado_em = data_registro")
    op.execute(
        "UPDATE linha_producao SET removido = 0 WHERE removido IS NULL"
        if bind.dialect.name == "sqlite"
        else "UPDATE linha_producao SET removido = FALSE WHERE removido IS NULL"
    )

    with op.batch_alter_table("linha_producao", schema=None) as batch_op:
        batch_op.alter_column("ano", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_linha_producao_atualizado_por_id_usuario", "usuario", ["atualizado_por_id"], ["id"]
        )
        batch_op.create_index("ix_linha_producao_periodo", ["usuario_id", "ano", "mes", "semana"], unique=False)

    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("pode_plano_acao", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Na v1 o plano de ação era liberado por nome, direto no código.
    op.execute(sa.text("UPDATE usuario SET pode_plano_acao = :v WHERE lower(nome) = 'lucas'").bindparams(v=True))

    op.create_table(
        "plano_acao_ciclo",
        sa.Column("ano", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ano", name="pk_plano_acao_ciclo"),
    )
    op.create_table(
        "plano_acao_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ciclo_ano", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("rotulo", sa.String(length=40), nullable=False),
        sa.Column("eh_base", sa.Boolean(), nullable=False),
        sa.Column("caixa_pa", sa.Integer(), nullable=True),
        sa.Column("caixa_in_p", sa.Integer(), nullable=True),
        sa.Column("caixa_conferencia_p", sa.Integer(), nullable=True),
        sa.Column("caixa_p_sem_pensao", sa.Integer(), nullable=True),
        sa.Column("data_extracao", sa.String(length=20), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ciclo_ano"], ["plano_acao_ciclo.ano"], name="fk_plano_acao_mes_ciclo_ano_plano_acao_ciclo"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plano_acao_mes"),
    )


def downgrade():
    op.drop_table("plano_acao_mes")
    op.drop_table("plano_acao_ciclo")
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("pode_plano_acao")
        batch_op.drop_column("ativo")
    with op.batch_alter_table("linha_producao", schema=None) as batch_op:
        batch_op.drop_index("ix_linha_producao_periodo")
        batch_op.drop_constraint("fk_linha_producao_atualizado_por_id_usuario", type_="foreignkey")
        batch_op.drop_column("atualizado_por_id")
        batch_op.drop_column("atualizado_em")
        batch_op.drop_column("ano")
