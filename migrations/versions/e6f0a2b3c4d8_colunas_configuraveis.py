"""colunas e situações configuráveis (atividades, documentos e situações editáveis)

Revision ID: e6f0a2b3c4d8
Revises: d5e9f3a1b2c7
Create Date: 2026-11-06 17:20:00

Antes, cada atividade/documento era uma coluna booleana fixa em
linha_producao. Agora:
  * item_grade   – a lista de colunas (editável pelos administradores);
  * linha_item   – quais itens cada linha marcou.
Todas as marcações existentes são copiadas; as colunas antigas são removidas.
O downgrade recria as colunas e devolve as marcações dos itens padrão.
"""

import sqlalchemy as sa
from alembic import op

revision = "e6f0a2b3c4d8"
down_revision = "d5e9f3a1b2c7"
branch_labels = None
depends_on = None

# (grupo, chave = nome da antiga coluna, rótulo, rótulo curto)
ITENS = [
    ("atividade", "homologacao", "Homologação", "Homolog."),
    ("atividade", "fixacao_civil", "Fixação civil", "Fix. civil"),
    ("atividade", "in_68", "IN 68", "IN 68"),
    ("atividade", "conf_civil", "Conferência civil", "Conf. civil"),
    ("atividade", "registro_civil", "Registro civil", "Reg. civil"),
    ("atividade", "fixacao_pensao", "Fixação pensão", "Fix. pensão"),
    ("atividade", "conf_pensao", "Conferência pensão", "Conf. pensão"),
    ("atividade", "diligencia", "Diligência", "Diligência"),
    ("atividade", "outros", "Outros", "Outros"),
    ("documento", "rg_cpf_doc", "RG / CPF", "RG/CPF"),
    ("documento", "comp_residencia_doc", "Comprovante de residência", "Comp. resid."),
    ("documento", "cert_nasc_casamento_doc", "Certidão de nascimento / casamento", "Cert. nasc./cas."),
    ("documento", "requerimento_doc", "Requerimento", "Requerimento"),
    ("documento", "dtc_doc", "DTC", "DTC"),
    ("documento", "negativa_pad_doc", "Negativa de PAD", "Neg. PAD"),
    ("documento", "contracheque_doc", "Contracheque", "Contracheque"),
    ("documento", "declaracao_chefia_doc", "Declaração da chefia", "Decl. chefia"),
    ("documento", "termo_subsidio_doc", "Termo de subsídio", "Termo subsídio"),
    ("documento", "declaracao_bens_doc", "Declaração de bens", "Decl. bens"),
    ("documento", "extrato_doc", "Extrato", "Extrato"),
    ("documento", "qd_elevacao_doc", "QD de elevação", "QD elevação"),
    ("documento", "lotacao_doc", "Lotação", "Lotação"),
    ("documento", "tempo_contribuicao_doc", "Tempo de contribuição", "Tempo contrib."),
    ("documento", "anexos_tce_doc", "Anexos TCE", "Anexos TCE"),
    ("documento", "portaria_doc", "Portaria", "Portaria"),
    ("documento", "fixacao_o_doc", "Fixação O", "Fixação O"),
    ("documento", "siarhes_doc", "SIARHES", "SIARHES"),
]


SITUACOES = [
    # chave, rótulo, curto, símbolo, cor, conta como pendência
    ("finalizado", "Finalizado", "Finalizado", "X", "#2c6493", False),
    ("tramitado", "Tramitado – aguardando", "Tramitado", "»»", "#f3c04a", True),
    ("aguardando", "Aguardando orientação da chefia", "Aguardando", "?", "#c7d0d9", True),
    ("acompanhar", "Acompanhar mesmo após envio", "Acompanhar", "!", "#e88fb1", True),
    ("conferido", "Conferido e encaminhado", "Conferido", "✓", "#45a079", False),
]


def upgrade():
    situacao = op.create_table(
        "situacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.String(length=40), nullable=False),
        sa.Column("rotulo", sa.String(length=60), nullable=False),
        sa.Column("curto", sa.String(length=20), nullable=False),
        sa.Column("simbolo", sa.String(length=4), nullable=False),
        sa.Column("cor", sa.String(length=7), nullable=False),
        sa.Column("pendente", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_situacao"),
        sa.UniqueConstraint("chave", name="uq_situacao_chave"),
    )
    op.bulk_insert(
        situacao,
        [
            {"chave": c, "rotulo": r, "curto": cu, "simbolo": si, "cor": cor, "pendente": pe, "ordem": i, "ativo": True}
            for i, (c, r, cu, si, cor, pe) in enumerate(SITUACOES)
        ],
    )

    item = op.create_table(
        "item_grade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grupo", sa.String(length=20), nullable=False),
        sa.Column("chave", sa.String(length=60), nullable=False),
        sa.Column("rotulo", sa.String(length=80), nullable=False),
        sa.Column("curto", sa.String(length=24), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_item_grade"),
        sa.UniqueConstraint("chave", name="uq_item_grade_chave"),
    )
    op.create_index("ix_item_grade_grupo", "item_grade", ["grupo"], unique=False)
    op.create_table(
        "linha_item",
        sa.Column("linha_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["item_grade.id"], name="fk_linha_item_item_id_item_grade", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["linha_id"], ["linha_producao.id"], name="fk_linha_item_linha_id_linha_producao", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("linha_id", "item_id", name="pk_linha_item"),
    )

    ordens = {"atividade": 0, "documento": 0}
    linhas = []
    for grupo, chave, rotulo, curto in ITENS:
        linhas.append(
            {"grupo": grupo, "chave": chave, "rotulo": rotulo, "curto": curto, "ordem": ordens[grupo], "ativo": True}
        )
        ordens[grupo] += 1
    op.bulk_insert(item, linhas)

    bind = op.get_bind()
    colunas_existentes = {c["name"] for c in sa.inspect(bind).get_columns("linha_producao")}
    verdadeiro = "1" if bind.dialect.name == "sqlite" else "TRUE"
    for _grupo, chave, _r, _c in ITENS:
        if chave in colunas_existentes:
            op.execute(
                f"INSERT INTO linha_item (linha_id, item_id) "
                f"SELECT lp.id, ig.id FROM linha_producao lp, item_grade ig "
                f"WHERE ig.chave = '{chave}' AND lp.{chave} = {verdadeiro}"
            )

    with op.batch_alter_table("linha_producao", schema=None) as batch_op:
        for _grupo, chave, _r, _c in ITENS:
            if chave in colunas_existentes:
                batch_op.drop_column(chave)


def downgrade():
    with op.batch_alter_table("linha_producao", schema=None) as batch_op:
        for _grupo, chave, _r, _c in ITENS:
            batch_op.add_column(sa.Column(chave, sa.Boolean(), nullable=True))
    bind = op.get_bind()
    verdadeiro = "1" if bind.dialect.name == "sqlite" else "TRUE"
    for _grupo, chave, _r, _c in ITENS:
        op.execute(
            f"UPDATE linha_producao SET {chave} = {verdadeiro} WHERE id IN ("
            f"SELECT li.linha_id FROM linha_item li JOIN item_grade ig ON ig.id = li.item_id "
            f"WHERE ig.chave = '{chave}')"
        )
    op.drop_table("linha_item")
    op.drop_index("ix_item_grade_grupo", table_name="item_grade")
    op.drop_table("item_grade")
    op.drop_table("situacao")
