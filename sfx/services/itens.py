"""Colunas e situações configuráveis da grade (atividades, documentos e situações)."""

from __future__ import annotations

import re
import unicodedata

from flask import g, has_app_context

from ..constants import ATIVIDADES_PADRAO, DOCUMENTOS_PADRAO, GRUPO_ATIVIDADE, GRUPO_DOCUMENTO, STATUS_PADRAO
from ..extensions import db
from ..models import ItemGrade, LinhaProducao, Situacao, linha_item

LIMITE_ROTULO = 80
LIMITE_CURTO = 24


def listar(grupo: str, incluir_inativos: bool = False) -> list[ItemGrade]:
    """Itens do grupo em ordem de exibição (cacheado por requisição)."""
    chave_cache = f"_itens_{grupo}_{incluir_inativos}"
    if has_app_context() and chave_cache in g:
        return g.get(chave_cache)
    consulta = ItemGrade.query.filter_by(grupo=grupo)
    if not incluir_inativos:
        consulta = consulta.filter(ItemGrade.ativo.is_(True))
    itens = consulta.order_by(ItemGrade.ordem, ItemGrade.id).all()
    if has_app_context():
        setattr(g, chave_cache, itens)
    return itens


def atividades() -> list[ItemGrade]:
    return listar(GRUPO_ATIVIDADE)


def documentos() -> list[ItemGrade]:
    return listar(GRUPO_DOCUMENTO)


def chaves_atividades() -> list[str]:
    return [i.chave for i in atividades()]


def situacoes(incluir_inativas: bool = False) -> list[Situacao]:
    chave_cache = f"_itens_situacoes_{incluir_inativas}"
    if has_app_context() and chave_cache in g:
        return g.get(chave_cache)
    consulta = Situacao.query
    if not incluir_inativas:
        consulta = consulta.filter(Situacao.ativo.is_(True))
    lista = consulta.order_by(Situacao.ordem, Situacao.id).all()
    if has_app_context():
        setattr(g, chave_cache, lista)
    return lista


def situacao(chave: str | None) -> Situacao | None:
    if not chave:
        return None
    return next((s for s in situacoes(incluir_inativas=True) if s.chave == chave), None)


def chaves_pendentes() -> list[str]:
    return [s.chave for s in situacoes(incluir_inativas=True) if s.pendente]


def limpar_cache() -> None:
    if has_app_context():
        for nome in [k for k in g if k.startswith("_itens_")]:
            g.pop(nome, None)


def semear_padrao() -> int:
    """Cria itens e situações padrão se as tabelas estiverem vazias (bancos novos e testes)."""
    criados = 0
    if not Situacao.query.first():
        for ordem, st in enumerate(STATUS_PADRAO):
            db.session.add(
                Situacao(
                    chave=st.chave,
                    rotulo=st.rotulo,
                    curto=st.curto,
                    simbolo=st.simbolo,
                    cor=st.cor,
                    pendente=st.pendente,
                    ordem=ordem,
                    ativo=True,
                )
            )
            criados += 1
        db.session.commit()
    if ItemGrade.query.first():
        limpar_cache()
        return criados
    for grupo, lista in ((GRUPO_ATIVIDADE, ATIVIDADES_PADRAO), (GRUPO_DOCUMENTO, DOCUMENTOS_PADRAO)):
        for ordem, campo in enumerate(lista):
            db.session.add(
                ItemGrade(
                    grupo=grupo, chave=campo.chave, rotulo=campo.rotulo, curto=campo.curto, ordem=ordem, ativo=True
                )
            )
            criados += 1
    db.session.commit()
    limpar_cache()
    return criados


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")[:40]
    return base or "item"


def criar(grupo: str, rotulo: str, curto: str = "") -> ItemGrade:
    rotulo = rotulo.strip()[:LIMITE_ROTULO]
    curto = (curto.strip() or rotulo)[:LIMITE_CURTO]
    base = _slug(rotulo) + ("_doc" if grupo == GRUPO_DOCUMENTO else "")
    chave, n = base, 2
    while ItemGrade.query.filter_by(chave=chave).first():
        chave, n = f"{base}_{n}", n + 1
    ordem = (db.session.query(db.func.max(ItemGrade.ordem)).filter_by(grupo=grupo).scalar() or 0) + 1
    item = ItemGrade(grupo=grupo, chave=chave, rotulo=rotulo, curto=curto, ordem=ordem, ativo=True)
    db.session.add(item)
    db.session.commit()
    limpar_cache()
    return item


def criar_situacao(rotulo: str, curto: str, simbolo: str, cor: str, pendente: bool) -> Situacao:
    rotulo = rotulo.strip()[:60]
    base, n = _slug(rotulo)[:36], 2
    chave = base
    while Situacao.query.filter_by(chave=chave).first():
        chave, n = f"{base}_{n}", n + 1
    ordem = (db.session.query(db.func.max(Situacao.ordem)).scalar() or 0) + 1
    st = Situacao(
        chave=chave,
        rotulo=rotulo,
        curto=(curto.strip() or rotulo)[:20],
        simbolo=(simbolo.strip() or "•")[:4],
        cor=cor_valida(cor),
        pendente=pendente,
        ordem=ordem,
        ativo=True,
    )
    db.session.add(st)
    db.session.commit()
    limpar_cache()
    return st


def cor_valida(cor: str | None) -> str:
    cor = (cor or "").strip()
    return cor.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else "#2c6493"


def uso_situacao(st: Situacao) -> int:
    return LinhaProducao.query.filter_by(status=st.chave).count()


def mover(item, direcao: int) -> None:
    """Troca o item (ou situação) de lugar com o vizinho (direcao -1 = antes)."""
    lista = (
        situacoes(incluir_inativas=True) if isinstance(item, Situacao) else listar(item.grupo, incluir_inativos=True)
    )
    for posicao, i in enumerate(lista):  # normaliza a ordem
        i.ordem = posicao
    idx = lista.index(item)
    alvo = idx + direcao
    if 0 <= alvo < len(lista):
        lista[idx].ordem, lista[alvo].ordem = lista[alvo].ordem, lista[idx].ordem
    db.session.commit()
    limpar_cache()


def uso(item: ItemGrade) -> int:
    return db.session.query(db.func.count()).select_from(linha_item).filter(linha_item.c.item_id == item.id).scalar()


class ListaPreguicosa:
    """Lista consultada só quando o template realmente a usa."""

    def __init__(self, funcao):
        self._funcao = funcao

    def _lista(self):
        return self._funcao()

    def __iter__(self):
        return iter(self._lista())

    def __len__(self):
        return len(self._lista())

    def __getitem__(self, i):
        return self._lista()[i]

    def __bool__(self):
        return bool(self._lista())


def rotulo(chave: str) -> str:
    for item in listar(GRUPO_ATIVIDADE, True) + listar(GRUPO_DOCUMENTO, True):
        if item.chave == chave:
            return item.rotulo
    return chave
