from __future__ import annotations

from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .constants import (
    CAMPOS_TEXTO,
    CHAVES_ATIVIDADES,
    CHAVES_DOCUMENTOS,
    PERFIL_ANALISTA,
    PERFIS,
    PERFIS_EDICAO_EQUIPE,
    PERFIS_GESTAO,
    STATUS_PENDENTES,
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
    def eh_gestor(self) -> bool:
        return self.tipo in PERFIS_GESTAO

    @property
    def edita_equipe(self) -> bool:
        return self.tipo in PERFIS_EDICAO_EQUIPE

    @property
    def acessa_plano_acao(self) -> bool:
        return bool(self.pode_plano_acao) or self.eh_gestor

    @property
    def perfil_rotulo(self) -> str:
        return PERFIS.get(self.tipo, self.tipo.title())

    @property
    def iniciais(self) -> str:
        partes = self.nome.split()
        return "".join(p[0] for p in partes[:2]).upper() or "?"

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.nome!r} {self.tipo}>"


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

    # Atividades (contam como produção)
    homologacao = db.Column(db.Boolean, default=False)
    diligencia = db.Column(db.Boolean, default=False)
    fixacao_civil = db.Column(db.Boolean, default=False)
    conf_civil = db.Column(db.Boolean, default=False)
    registro_civil = db.Column(db.Boolean, default=False)
    fixacao_pensao = db.Column(db.Boolean, default=False)
    conf_pensao = db.Column(db.Boolean, default=False)
    in_68 = db.Column(db.Boolean, default=False)
    outros = db.Column(db.Boolean, default=False)

    # Pendências
    resolucao = db.Column(db.Text, default="")
    removido = db.Column(db.Boolean, default=False)

    # Conferência documental
    rg_cpf_doc = db.Column(db.Boolean, default=False)
    comp_residencia_doc = db.Column(db.Boolean, default=False)
    cert_nasc_casamento_doc = db.Column(db.Boolean, default=False)
    requerimento_doc = db.Column(db.Boolean, default=False)
    dtc_doc = db.Column(db.Boolean, default=False)
    negativa_pad_doc = db.Column(db.Boolean, default=False)
    contracheque_doc = db.Column(db.Boolean, default=False)
    declaracao_chefia_doc = db.Column(db.Boolean, default=False)
    termo_subsidio_doc = db.Column(db.Boolean, default=False)
    declaracao_bens_doc = db.Column(db.Boolean, default=False)
    extrato_doc = db.Column(db.Boolean, default=False)
    qd_elevacao_doc = db.Column(db.Boolean, default=False)
    lotacao_doc = db.Column(db.Boolean, default=False)
    tempo_contribuicao_doc = db.Column(db.Boolean, default=False)
    anexos_tce_doc = db.Column(db.Boolean, default=False)
    portaria_doc = db.Column(db.Boolean, default=False)
    fixacao_o_doc = db.Column(db.Boolean, default=False)
    siarhes_doc = db.Column(db.Boolean, default=False)

    usuario = db.relationship("Usuario", back_populates="linhas", foreign_keys=[usuario_id])
    atualizado_por = db.relationship("Usuario", foreign_keys=[atualizado_por_id])

    @property
    def atividades_marcadas(self) -> list[str]:
        return [c for c in CHAVES_ATIVIDADES if getattr(self, c)]

    @property
    def documentos_conferidos(self) -> int:
        return sum(1 for c in CHAVES_DOCUMENTOS if getattr(self, c))

    @property
    def pendente(self) -> bool:
        return self.status in STATUS_PENDENTES and not self.removido

    def esta_vazia(self) -> bool:
        if any((getattr(self, c) or "").strip() for c in CAMPOS_TEXTO):
            return False
        if self.status or (self.resolucao or "").strip():
            return False
        return not any(getattr(self, c) for c in CHAVES_ATIVIDADES + CHAVES_DOCUMENTOS)

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
