from __future__ import annotations

from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .constants import (
    CAMPOS_TEXTO,
    GRUPO_DOCUMENTO,
    PERFIL_ADMIN,
    PERFIL_ANALISTA,
    PERFIS,
    PERFIS_EDICAO_EQUIPE,
    PERFIS_GESTAO,
)
from .extensions import db


def agora_utc() -> datetime:
    """UTC "ingênuo" — mantém compatibilidade com os registros já gravados."""
    return datetime.now(UTC).replace(tzinfo=None)


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    modalidade = db.Column(db.String(20))
    # False = a senha atual é provisória e deve ser trocada no próximo acesso.
    primeiro_acesso_realizado = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    pode_plano_acao = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    # Acesso total ao sistema, somado ao perfil (ex.: analista que também administra).
    administrador = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    linhas = db.relationship(
        "LinhaProducao",
        back_populates="usuario",
        foreign_keys="LinhaProducao.usuario_id",
        lazy="dynamic",
    )

    # --- senha -------------------------------------------------------------
    def definir_senha(self, senha: str, *, provisoria: bool = False) -> None:
        self.senha = generate_password_hash(senha)
        self.primeiro_acesso_realizado = not provisoria

    def confere_senha(self, senha: str) -> bool:
        return bool(self.senha) and check_password_hash(self.senha, senha)

    @property
    def precisa_trocar_senha(self) -> bool:
        return not self.primeiro_acesso_realizado

    # --- perfis ------------------------------------------------------------
    @property
    def is_active(self) -> bool:  # usado pelo Flask-Login
        return bool(self.ativo) if self.ativo is not None else True

    @property
    def eh_analista(self) -> bool:
        return self.tipo == PERFIL_ANALISTA

    @property
    def eh_admin(self) -> bool:
        """Acesso total: gestão, equipe, plano de ação e cadastro de administradores."""
        return bool(self.administrador) or self.tipo == PERFIL_ADMIN

    @property
    def eh_gestor(self) -> bool:
        return self.tipo in PERFIS_GESTAO or self.eh_admin

    @property
    def edita_equipe(self) -> bool:
        return self.tipo in PERFIS_EDICAO_EQUIPE or self.eh_admin

    @property
    def acessa_plano_acao(self) -> bool:
        return bool(self.pode_plano_acao) or self.eh_gestor

    @property
    def perfil_rotulo(self) -> str:
        return PERFIS.get(self.tipo, self.tipo.title())

    @property
    def papel_rotulo(self) -> str:
        """Perfil + administrador, ex.: "Analista · Administrador"."""
        if self.administrador and self.tipo != PERFIL_ADMIN:
            return f"{self.perfil_rotulo} · Administrador"
        return self.perfil_rotulo

    @property
    def iniciais(self) -> str:
        partes = self.nome.split()
        return "".join(p[0] for p in partes[:2]).upper() or "?"

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.nome!r} {self.tipo}>"


linha_item = db.Table(
    "linha_item",
    db.Column("linha_id", db.Integer, db.ForeignKey("linha_producao.id", ondelete="CASCADE"), primary_key=True),
    db.Column("item_id", db.Integer, db.ForeignKey("item_grade.id", ondelete="CASCADE"), primary_key=True),
)


class ItemGrade(db.Model):
    """Coluna configurável da grade: uma atividade (conta como produção) ou um
    documento da conferência documental. Administradores criam, renomeiam,
    reordenam e ocultam itens; ocultar preserva o histórico."""

    __tablename__ = "item_grade"

    id = db.Column(db.Integer, primary_key=True)
    grupo = db.Column(db.String(20), nullable=False, index=True)  # "atividade" | "documento"
    chave = db.Column(db.String(60), nullable=False, unique=True)  # identificador fixo
    rotulo = db.Column(db.String(80), nullable=False)
    curto = db.Column(db.String(24), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    def __repr__(self) -> str:
        return f"<ItemGrade {self.grupo}:{self.chave}>"


class Situacao(db.Model):
    """Situação de um processo na grade (Finalizado, Tramitado…), editável pelos administradores."""

    __tablename__ = "situacao"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(40), nullable=False, unique=True)  # gravada em linha_producao.status
    rotulo = db.Column(db.String(60), nullable=False)
    curto = db.Column(db.String(20), nullable=False)
    simbolo = db.Column(db.String(4), nullable=False, default="•")
    cor = db.Column(db.String(7), nullable=False, default="#2c6493")
    # Processos nesta situação aparecem na tela de pendências.
    pendente = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    ordem = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    @property
    def cor_texto(self) -> str:
        """Preto ou branco, o que tiver mais contraste com a cor de fundo."""
        try:
            r, g, b = (int(self.cor[i : i + 2], 16) / 255 for i in (1, 3, 5))
        except (TypeError, ValueError):
            return "#ffffff"

        def canal(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        luminancia = 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)
        return "#1b2633" if luminancia > 0.4 else "#ffffff"

    def __repr__(self) -> str:
        return f"<Situacao {self.chave}>"


class LinhaProducao(db.Model):
    """Uma linha da grade semanal: um processo trabalhado por um analista."""

    __tablename__ = "linha_producao"
    __table_args__ = (db.Index("ix_linha_producao_periodo", "usuario_id", "ano", "mes", "semana"),)

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    semana = db.Column(db.String(50), nullable=False)
    indice_linha = db.Column(db.Integer)
    data_registro = db.Column(db.DateTime, default=agora_utc)
    atualizado_em = db.Column(db.DateTime, default=agora_utc, onupdate=agora_utc)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))

    numero_processo = db.Column(db.String(100))
    nome_do_segurado = db.Column(db.String(100))
    status = db.Column(db.String(20))
    setor = db.Column(db.String(100))
    observacoes = db.Column(db.Text)

    # Pendências
    resolucao = db.Column(db.Text, default="")
    removido = db.Column(db.Boolean, default=False)

    # Atividades e documentos marcados (colunas configuráveis — ver ItemGrade)
    itens = db.relationship("ItemGrade", secondary="linha_item", lazy="selectin")

    usuario = db.relationship("Usuario", back_populates="linhas", foreign_keys=[usuario_id])
    atualizado_por = db.relationship("Usuario", foreign_keys=[atualizado_por_id])

    @property
    def chaves_marcadas(self) -> set[str]:
        return {i.chave for i in self.itens}

    @property
    def documentos_conferidos(self) -> int:
        return sum(1 for i in self.itens if i.grupo == GRUPO_DOCUMENTO and i.ativo)

    @property
    def pendente(self) -> bool:
        from .services.itens import chaves_pendentes

        return self.status in chaves_pendentes() and not self.removido

    def esta_vazia(self) -> bool:
        if any((getattr(self, c) or "").strip() for c in CAMPOS_TEXTO):
            return False
        if self.status or (self.resolucao or "").strip():
            return False
        return not self.itens

    def __repr__(self) -> str:
        return f"<LinhaProducao {self.id} {self.mes}/{self.ano} {self.numero_processo!r}>"


class PlanoAcaoCiclo(db.Model):
    """Um ano de acompanhamento das caixas do setor (antiga planilha Pasta2)."""

    __tablename__ = "plano_acao_ciclo"

    ano = db.Column(db.Integer, primary_key=True, autoincrement=False)
    nota = db.Column(db.Text, default="")
    meses = db.relationship(
        "PlanoAcaoMes",
        back_populates="ciclo",
        order_by="PlanoAcaoMes.ordem",
        cascade="all, delete-orphan",
    )


class PlanoAcaoMes(db.Model):
    __tablename__ = "plano_acao_mes"

    id = db.Column(db.Integer, primary_key=True)
    ciclo_ano = db.Column(db.Integer, db.ForeignKey("plano_acao_ciclo.ano"), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    rotulo = db.Column(db.String(40), nullable=False)
    # Linha de referência (ex.: "Dezembro de 2024") usada só para a variação.
    eh_base = db.Column(db.Boolean, nullable=False, default=False)
    caixa_pa = db.Column(db.Integer)
    caixa_in_p = db.Column(db.Integer)
    caixa_conferencia_p = db.Column(db.Integer)
    caixa_p_sem_pensao = db.Column(db.Integer)
    data_extracao = db.Column(db.String(20))
    observacoes = db.Column(db.Text)
    atualizado_em = db.Column(db.DateTime, default=agora_utc, onupdate=agora_utc)

    ciclo = db.relationship("PlanoAcaoCiclo", back_populates="meses")

    CAIXAS = ("caixa_pa", "caixa_in_p", "caixa_conferencia_p", "caixa_p_sem_pensao")

    @property
    def total(self) -> int | None:
        valores = [getattr(self, c) for c in self.CAIXAS]
        if all(v is None for v in valores):
            return None
        return sum(v or 0 for v in valores)
