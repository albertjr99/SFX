"""Data e hora no fuso do setor (padrão: America/Sao_Paulo, UTC−3).

Regra do sistema:
  * no banco, instantes ficam em UTC (independem do fuso do servidor);
  * tudo que o usuário vê — e todo "hoje" usado em regras (semana atual,
    mês padrão) — é calculado no fuso de São Paulo;
  * datas exibidas sempre em formato brasileiro: dd/mm/aaaa (e HH:MM).
"""

from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime
from functools import cache
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

FUSO_PADRAO = "America/Sao_Paulo"
FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_HORA = "%d/%m/%Y %H:%M"


@cache
def _zona(nome: str) -> ZoneInfo:
    return ZoneInfo(nome)


def fuso() -> ZoneInfo:
    if has_app_context():
        return _zona(current_app.config.get("SFX_FUSO") or FUSO_PADRAO)
    return _zona(os.environ.get("SFX_FUSO") or FUSO_PADRAO)


def agora() -> datetime:
    """Agora, no fuso de São Paulo (com tzinfo)."""
    return datetime.now(fuso())


def hoje() -> date:
    """Data de hoje em São Paulo — não a do servidor (que pode estar em UTC)."""
    return agora().date()


def para_local(valor: datetime) -> datetime:
    """Converte um instante gravado em UTC (ingênuo ou não) para São Paulo."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.astimezone(fuso())


def formatar(valor: datetime | date | None, com_hora: bool = False) -> str:
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        valor = para_local(valor)
        return valor.strftime(FORMATO_DATA_HORA if com_hora else FORMATO_DATA)
    return valor.strftime(FORMATO_DATA)


_DMA = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})\s*$")
_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")


def normalizar_data_br(texto: str | None) -> str:
    """Aceita "5/1/26", "05-01-2026", "2026-01-05"… e devolve "05/01/2026".

    Se o texto não for uma data reconhecível, devolve-o como veio (sem perder
    o que o usuário digitou).
    """
    texto = (texto or "").strip()
    if not texto:
        return ""
    d = m = a = None
    if achado := _DMA.match(texto):
        d, m, a = (int(x) for x in achado.groups())
        if a < 100:
            a += 2000
    elif achado := _ISO.match(texto):
        a, m, d = (int(x) for x in achado.groups())
    if d is None:
        return texto
    try:
        return date(a, m, d).strftime(FORMATO_DATA)
    except ValueError:
        return texto
