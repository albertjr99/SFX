"""Plano de ação: acompanhamento mensal das caixas de processos do setor.

Substitui a antiga planilha ``data/Pasta2.xlsx`` (que era lida e reescrita a
cada acesso) por tabelas no banco. A planilha pode ser importada uma única vez
com ``flask plano importar caminho.xlsx``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from ..constants import MESES
from ..extensions import db
from ..models import PlanoAcaoCiclo, PlanoAcaoMes

ABA_PADRAO = "Controle processos 2025"
# (ano do ciclo, primeira linha, última linha) na planilha original.
FAIXAS_PLANILHA = ((2024, 4, 15), (2025, 16, 28))
CELULA_NOTA = "A31"


def variacao(anterior: int | None, atual: int | None) -> float | None:
    """Redução percentual em relação ao mês anterior (positivo = caixa diminuiu).

    Mesma fórmula da planilha: ((atual / anterior) - 1) * -1 * 100.
    """
    if not anterior or atual is None:
        return None
    return round((1 - atual / anterior) * 100, 1)


def serializar_ciclo(ciclo: PlanoAcaoCiclo) -> list[dict]:
    linhas = []
    anterior: int | None = None
    for mes in ciclo.meses:
        tot = mes.total
        linhas.append(
            {
                "id": mes.id,
                "rotulo": mes.rotulo,
                "eh_base": mes.eh_base,
                "caixa_pa": mes.caixa_pa,
                "caixa_in_p": mes.caixa_in_p,
                "caixa_conferencia_p": mes.caixa_conferencia_p,
                "caixa_p_sem_pensao": mes.caixa_p_sem_pensao,
                "total": tot,
                "variacao": variacao(anterior, tot),
                "data_extracao": mes.data_extracao or "",
                "observacoes": mes.observacoes or "",
            }
        )
        if tot is not None:
            anterior = tot
    return linhas


def criar_ciclo(ano: int) -> PlanoAcaoCiclo:
    """Cria um ciclo com os 12 meses e uma linha-base copiada de dezembro anterior."""
    ciclo = db.session.get(PlanoAcaoCiclo, ano)
    if ciclo:
        return ciclo
    ciclo = PlanoAcaoCiclo(ano=ano, nota="")
    db.session.add(ciclo)
    ordem = 0
    anterior = db.session.get(PlanoAcaoCiclo, ano - 1)
    if anterior:
        dezembro = next((m for m in reversed(anterior.meses) if m.total is not None), None)
        if dezembro:
            base = PlanoAcaoMes(
                rotulo=f"{dezembro.rotulo} de {ano - 1}",
                eh_base=True,
                ordem=ordem,
                data_extracao=dezembro.data_extracao,
                observacoes="Linha de referência para a variação de janeiro.",
            )
            for c in PlanoAcaoMes.CAIXAS:
                setattr(base, c, getattr(dezembro, c))
            ciclo.meses.append(base)
            ordem += 1
    for nome in MESES:
        ciclo.meses.append(PlanoAcaoMes(rotulo=nome, ordem=ordem))
        ordem += 1
    db.session.commit()
    return ciclo


def _inteiro(valor) -> int | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = str(valor).strip().replace(" ", "")
    if "," in texto:  # formato brasileiro: 1.234,5
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return int(float(texto))
    except ValueError:
        return None


def salvar_ciclo(ciclo: PlanoAcaoCiclo, dados: dict) -> None:
    por_id = {m.id: m for m in ciclo.meses}
    for item in dados.get("linhas", []):
        mes = por_id.get(item.get("id"))
        if mes is None:
            continue
        for c in PlanoAcaoMes.CAIXAS:
            setattr(mes, c, _inteiro(item.get(c)))
        mes.data_extracao = (str(item.get("data_extracao") or "")).strip()[:20]
        mes.observacoes = (str(item.get("observacoes") or "")).strip()[:8000]
    if "nota" in dados:
        ciclo.nota = (str(dados.get("nota") or "")).strip()[:8000]
    db.session.commit()


def _data_texto(valor) -> str:
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if valor is None:
        return ""
    texto = str(valor).strip()
    try:
        return datetime.fromisoformat(texto.split()[0]).strftime("%d/%m/%Y")
    except ValueError:
        return texto


def importar_planilha(caminho: str | Path, aba: str = ABA_PADRAO, substituir: bool = False) -> list[int]:
    import openpyxl  # import tardio: só a importação precisa da biblioteca

    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb[aba] if aba in wb.sheetnames else wb.active
    importados = []
    for ano, inicio, fim in FAIXAS_PLANILHA:
        existente = db.session.get(PlanoAcaoCiclo, ano)
        if existente and not substituir:
            continue
        if existente:
            db.session.delete(existente)
            db.session.flush()
        ciclo = PlanoAcaoCiclo(ano=ano, nota="")
        db.session.add(ciclo)
        for ordem, linha in enumerate(ws.iter_rows(min_row=inicio, max_row=fim, max_col=9, values_only=True)):
            rotulo = str(linha[0] or "").strip()
            if not rotulo:
                continue
            ciclo.meses.append(
                PlanoAcaoMes(
                    ordem=ordem,
                    rotulo=rotulo[:40],
                    eh_base=rotulo not in MESES,
                    caixa_pa=_inteiro(linha[1]),
                    caixa_in_p=_inteiro(linha[2]),
                    caixa_conferencia_p=_inteiro(linha[3]),
                    caixa_p_sem_pensao=_inteiro(linha[4]),
                    data_extracao=_data_texto(linha[7])[:20],
                    observacoes=(str(linha[8]).strip() if linha[8] else ""),
                )
            )
        if ano == 2024 and ws[CELULA_NOTA].value:
            ciclo.nota = str(ws[CELULA_NOTA].value).strip()
        importados.append(ano)
    db.session.commit()
    return importados
