"""Regras de negócio da grade de produção e das estatísticas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from ..constants import (
    CAMPOS_TEXTO,
    GRUPO_ATIVIDADE,
    LINHAS_PADRAO_POR_SEMANA,
    MESES,
    PERFIL_ANALISTA,
)
from ..extensions import db
from ..models import ItemGrade, LinhaProducao, Usuario, agora_utc, linha_item
from . import itens as itens_svc
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
    # Só itens ativos aparecem na tela; marcações em itens ocultos são preservadas.
    editaveis = itens_svc.atividades() + itens_svc.documentos()
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
            validas = {st.chave for st in itens_svc.situacoes()} | ({linha.status} if linha.status else set())
            linha.status = status if status in validas else ""
            preservados = [i for i in linha.itens if not i.ativo]
            linha.itens = preservados + [i for i in editaveis if form.get(f"{uid}__{i.chave}") is not None]

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
    return (linha.indice_linha, *textos, frozenset(i.id for i in linha.itens))


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------
def _zeros() -> dict[str, int]:
    return dict.fromkeys(itens_svc.chaves_atividades(), 0)


def _contar(agrupar_por, **filtros):
    """Conta marcações de atividades ativas, agrupando por uma coluna de LinhaProducao."""
    colunas = [agrupar_por] if agrupar_por is not None else []
    consulta = (
        db.session.query(*colunas, ItemGrade.chave, func.count())
        .select_from(LinhaProducao)
        .join(linha_item, linha_item.c.linha_id == LinhaProducao.id)
        .join(ItemGrade, ItemGrade.id == linha_item.c.item_id)
        .filter(ItemGrade.grupo == GRUPO_ATIVIDADE, ItemGrade.ativo.is_(True))
    )
    for chave, valor in filtros.items():
        if valor is not None:
            consulta = consulta.filter(getattr(LinhaProducao, chave) == valor)
    return consulta.group_by(*colunas, ItemGrade.chave).all()


def contagem_por_semana(usuario_id: int, periodo: Periodo) -> dict[str, dict[str, int]]:
    resultado = {s: _zeros() for s in periodo.semanas}
    for semana, chave, n in _contar(LinhaProducao.semana, usuario_id=usuario_id, ano=periodo.ano, mes=periodo.nome_mes):
        resultado.setdefault(semana, _zeros())[chave] = int(n)
    return resultado


def contagem(**filtros) -> dict[str, int]:
    """Contagem por atividade com filtros simples (usuario_id, ano, mes, semana)."""
    resultado = _zeros()
    for chave, n in _contar(None, **filtros):
        resultado[chave] = int(n)
    return resultado


def processos_distintos(**filtros) -> int:
    consulta = db.session.query(func.count(func.distinct(LinhaProducao.numero_processo))).filter(
        LinhaProducao.numero_processo.isnot(None), LinhaProducao.numero_processo != ""
    )
    for chave, valor in filtros.items():
        if valor is not None:
            consulta = consulta.filter(getattr(LinhaProducao, chave) == valor)
    return int(consulta.scalar() or 0)


def serie_mensal(ano: int, usuario_id: int | None = None) -> dict[str, dict[str, int]]:
    resultado = {m: _zeros() for m in MESES}
    for mes, chave, n in _contar(LinhaProducao.mes, ano=ano, usuario_id=usuario_id):
        if mes in resultado:
            resultado[mes][chave] = int(n)
    return resultado


def ranking_equipe(periodo: Periodo) -> list[dict]:
    analistas = (
        Usuario.query.filter_by(tipo=PERFIL_ANALISTA)
        .filter(or_(Usuario.ativo.is_(True), Usuario.ativo.is_(None)))
        .order_by(Usuario.nome)
        .all()
    )
    por_usuario: dict[int, dict[str, int]] = {}
    for usuario_id, chave, n in _contar(LinhaProducao.usuario_id, ano=periodo.ano, mes=periodo.nome_mes):
        por_usuario.setdefault(usuario_id, _zeros())[chave] = int(n)
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
