"""Regras de negócio da grade de produção e das estatísticas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from ..constants import (
    CAMPOS_TEXTO,
    CHAVES_ATIVIDADES,
    CHAVES_DOCUMENTOS,
    LINHAS_PADRAO_POR_SEMANA,
    MESES,
    PERFIL_ANALISTA,
    STATUS_POR_CHAVE,
)
from ..extensions import db
from ..models import LinhaProducao, Usuario, agora_utc
from .periodo import Periodo

LIMITES_TEXTO = {"numero_processo": 100, "nome_do_segurado": 100, "setor": 100, "observacoes": 4000}


# ---------------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------------
def linhas_do_mes(usuario_id: int, periodo: Periodo) -> list[LinhaProducao]:
    return (
        LinhaProducao.query.filter_by(usuario_id=usuario_id, ano=periodo.ano, mes=periodo.nome_mes)
        .options(joinedload(LinhaProducao.atualizado_por))
        .order_by(LinhaProducao.indice_linha.asc().nulls_last(), LinhaProducao.id.asc())
        .all()
    )


def carregar_grade(usuario_id: int, periodo: Periodo) -> dict[str, list[LinhaProducao | None]]:
    """Linhas por semana, completadas com vagas em branco até o mínimo padrão."""
    por_semana: dict[str, list[LinhaProducao | None]] = {s: [] for s in periodo.semanas}
    for linha in linhas_do_mes(usuario_id, periodo):
        por_semana.setdefault(linha.semana, []).append(linha)
    for linhas in por_semana.values():
        faltam = LINHAS_PADRAO_POR_SEMANA - len(linhas)
        if faltam > 0:
            linhas.extend([None] * faltam)
    return por_semana


@dataclass
class ResultadoGravacao:
    criadas: int = 0
    atualizadas: int = 0
    removidas: int = 0
    ignoradas: list[str] = field(default_factory=list)

    @property
    def mensagem(self) -> str:
        partes = []
        if self.criadas:
            partes.append(f"{self.criadas} nova(s)")
        if self.atualizadas:
            partes.append(f"{self.atualizadas} atualizada(s)")
        if self.removidas:
            partes.append(f"{self.removidas} removida(s)")
        return "Produção salva" + (f": {', '.join(partes)}." if partes else ".")


def _texto(form, chave: str, campo: str) -> str:
    valor = (form.get(chave) or "").strip()
    return valor[: LIMITES_TEXTO.get(campo, 255)]


def salvar_grade(alvo: Usuario, periodo: Periodo, form, editor: Usuario) -> ResultadoGravacao:
    """Aplica o formulário da grade às linhas do mês.

    Protocolo do formulário (ver ``partials/_grade.html``):
      * ``s{w}`` – rótulo da semana ``w`` (só semanas enviadas são tocadas);
      * ``s{w}_linha`` – lista ordenada de identificadores de linha
        (``e<id>`` para linhas existentes, ``n<token>`` para novas);
      * ``<uid>__<campo>`` – valores de cada linha.

    Linhas existentes que não voltam no formulário são excluídas; linhas sem
    nenhum conteúdo não são gravadas (nem mantidas).
    """
    resultado = ResultadoGravacao()
    semanas_validas = set(periodo.semanas)
    existentes = {l.id: l for l in linhas_do_mes(alvo.id, periodo)}
    agora = agora_utc()

    indices = sorted(int(k[1:]) for k in form if k[:1] == "s" and k[1:].isdigit())
    for w in indices:
        semana = form.get(f"s{w}")
        uids = form.getlist(f"s{w}_linha")
        if semana not in semanas_validas:
            resultado.ignoradas.append(semana)
            continue

        mantidos: set[int] = set()
        indice = 0
        for uid in uids:
            linha: LinhaProducao | None = None
            if uid.startswith("e") and uid[1:].isdigit():
                candidato = existentes.get(int(uid[1:]))
                if candidato is not None and candidato.semana == semana:
                    linha = candidato
            nova = linha is None
            if nova:
                linha = LinhaProducao(
                    usuario_id=alvo.id,
                    ano=periodo.ano,
                    mes=periodo.nome_mes,
                    semana=semana,
                    data_registro=agora,
                )

            antes = _assinatura(linha) if not nova else None
            for campo in CAMPOS_TEXTO:
                setattr(linha, campo, _texto(form, f"{uid}__{campo}", campo))
            status = form.get(f"{uid}__status") or ""
            linha.status = status if status in STATUS_POR_CHAVE else ""
            for campo in CHAVES_ATIVIDADES + CHAVES_DOCUMENTOS:
                setattr(linha, campo, form.get(f"{uid}__{campo}") is not None)

            if linha.esta_vazia():
                if not nova:
                    db.session.delete(linha)
                    resultado.removidas += 1
                    mantidos.add(linha.id)  # já tratado
                continue

            linha.indice_linha = indice
            indice += 1
            if nova:
                linha.atualizado_por_id = editor.id
                db.session.add(linha)
                resultado.criadas += 1
            else:
                mantidos.add(linha.id)
                if _assinatura(linha) != antes:
                    linha.atualizado_por_id = editor.id
                    linha.atualizado_em = agora
                    resultado.atualizadas += 1

        for linha in [l for l in existentes.values() if l.semana == semana]:
            if linha.id not in mantidos:
                db.session.delete(linha)
                resultado.removidas += 1

    db.session.commit()
    return resultado


def _assinatura(linha: LinhaProducao) -> tuple:
    """Valores normalizados (None ≡ "" ≡ False) para detectar alteração real."""
    textos = tuple((getattr(linha, c) or "") for c in ("status", *CAMPOS_TEXTO))
    marcas = tuple(bool(getattr(linha, c)) for c in (*CHAVES_ATIVIDADES, *CHAVES_DOCUMENTOS))
    return (linha.indice_linha, *textos, *marcas)


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------
def _somas_atividades():
    return [func.sum(case((getattr(LinhaProducao, c).is_(True), 1), else_=0)).label(c) for c in CHAVES_ATIVIDADES]


def _zeros() -> dict[str, int]:
    return {c: 0 for c in CHAVES_ATIVIDADES}


def contagem_por_semana(usuario_id: int, periodo: Periodo) -> dict[str, dict[str, int]]:
    linhas = (
        db.session.query(LinhaProducao.semana, *_somas_atividades())
        .filter_by(usuario_id=usuario_id, ano=periodo.ano, mes=periodo.nome_mes)
        .group_by(LinhaProducao.semana)
        .all()
    )
    resultado = {s: _zeros() for s in periodo.semanas}
    for linha in linhas:
        resultado.setdefault(linha.semana, _zeros())
        for c in CHAVES_ATIVIDADES:
            resultado[linha.semana][c] = int(getattr(linha, c) or 0)
    return resultado


def contagem(**filtros) -> dict[str, int]:
    """Contagem por atividade com filtros simples (usuario_id, ano, mes, semana)."""
    consulta = db.session.query(*_somas_atividades())
    for chave, valor in filtros.items():
        if valor is not None:
            consulta = consulta.filter(getattr(LinhaProducao, chave) == valor)
    linha = consulta.one()
    return {c: int(getattr(linha, c) or 0) for c in CHAVES_ATIVIDADES}


def processos_distintos(**filtros) -> int:
    consulta = db.session.query(func.count(func.distinct(LinhaProducao.numero_processo))).filter(
        LinhaProducao.numero_processo.isnot(None), LinhaProducao.numero_processo != ""
    )
    for chave, valor in filtros.items():
        if valor is not None:
            consulta = consulta.filter(getattr(LinhaProducao, chave) == valor)
    return int(consulta.scalar() or 0)


def serie_mensal(ano: int, usuario_id: int | None = None) -> dict[str, dict[str, int]]:
    consulta = db.session.query(LinhaProducao.mes, *_somas_atividades()).filter(LinhaProducao.ano == ano)
    if usuario_id is not None:
        consulta = consulta.filter(LinhaProducao.usuario_id == usuario_id)
    resultado = {m: _zeros() for m in MESES}
    for linha in consulta.group_by(LinhaProducao.mes).all():
        if linha.mes in resultado:
            resultado[linha.mes] = {c: int(getattr(linha, c) or 0) for c in CHAVES_ATIVIDADES}
    return resultado


def ranking_equipe(periodo: Periodo) -> list[dict]:
    analistas = (
        Usuario.query.filter_by(tipo=PERFIL_ANALISTA)
        .filter(or_(Usuario.ativo.is_(True), Usuario.ativo.is_(None)))
        .order_by(Usuario.nome)
        .all()
    )
    linhas = (
        db.session.query(LinhaProducao.usuario_id, *_somas_atividades())
        .filter_by(ano=periodo.ano, mes=periodo.nome_mes)
        .group_by(LinhaProducao.usuario_id)
        .all()
    )
    por_usuario = {l.usuario_id: {c: int(getattr(l, c) or 0) for c in CHAVES_ATIVIDADES} for l in linhas}
    tabela = []
    for analista in analistas:
        valores = por_usuario.get(analista.id, _zeros())
        tabela.append({"usuario": analista, "valores": valores, "total": sum(valores.values())})
    tabela.sort(key=lambda r: (-r["total"], r["usuario"].nome))
    return tabela


def total(valores: dict[str, int]) -> int:
    return sum(valores.values())


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------
def buscar(termo: str, usuario_id: int | None = None, limite: int = 30) -> list[LinhaProducao]:
    termo = termo.strip()
    if len(termo) < 2:
        return []
    padrao = f"%{termo}%"
    consulta = LinhaProducao.query.filter(
        or_(
            LinhaProducao.numero_processo.ilike(padrao),
            LinhaProducao.nome_do_segurado.ilike(padrao),
        )
    )
    if usuario_id is not None:
        consulta = consulta.filter(LinhaProducao.usuario_id == usuario_id)
    return consulta.order_by(LinhaProducao.data_registro.desc()).limit(limite).all()


def semanas_por_mes_do_ano(ano: int) -> dict[str, list[str]]:
    return {m: Periodo(ano, i + 1).semanas for i, m in enumerate(MESES)}


def agrupar_pendencias(linhas: list[LinhaProducao]) -> dict[str, list[LinhaProducao]]:
    grupos: dict[str, list[LinhaProducao]] = defaultdict(list)
    for linha in linhas:
        grupos["removidas" if linha.removido else "abertas"].append(linha)
    return grupos
