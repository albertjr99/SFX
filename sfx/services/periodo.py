"""Cálculo de períodos: meses, semanas úteis e navegação entre meses."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from .. import tempo
from ..constants import MESES


def mes_numero(nome: str) -> int:
    return MESES.index(nome) + 1


def mes_nome(numero: int) -> str:
    return MESES[numero - 1]


def gerar_semanas(mes: int, ano: int) -> list[str]:
    """Semanas úteis (seg–sex) do mês no formato "dd/mm a dd/mm".

    Mantém exatamente o formato usado desde a primeira versão do sistema, pois
    é a chave com que as linhas de produção foram gravadas.
    """
    semanas: list[str] = []
    atual: list[date] = []
    ultimo = calendar.monthrange(ano, mes)[1]
    dia = date(ano, mes, 1)
    fim = date(ano, mes, ultimo)
    while dia <= fim:
        if dia.weekday() < 5:
            atual.append(dia)
        if (dia.weekday() == 4 or dia == fim) and atual:
            semanas.append(f"{atual[0]:%d/%m} a {atual[-1]:%d/%m}")
            atual = []
        dia += timedelta(days=1)
    return semanas


def semana_atual(mes: int, ano: int, hoje: date | None = None) -> str | None:
    hoje = hoje or tempo.hoje()
    if (hoje.year, hoje.month) != (ano, mes):
        return None
    alvo = hoje
    while alvo.weekday() >= 5:  # fim de semana → semana útil anterior
        alvo -= timedelta(days=1)
        if alvo.month != mes:
            return None
    chave = f"{alvo:%d/%m}"
    for semana in gerar_semanas(mes, ano):
        inicio, fim = semana.split(" a ")
        if _ddmm(inicio) <= _ddmm(chave) <= _ddmm(fim):
            return semana
    return None


def _ddmm(texto: str) -> tuple[int, int]:
    d, m = texto.split("/")
    return int(m), int(d)


@dataclass(frozen=True)
class Periodo:
    ano: int
    mes: int  # 1..12

    @property
    def nome_mes(self) -> str:
        return mes_nome(self.mes)

    @property
    def rotulo(self) -> str:
        return f"{self.nome_mes} de {self.ano}"

    @property
    def semanas(self) -> list[str]:
        return gerar_semanas(self.mes, self.ano)

    @property
    def anterior(self) -> Periodo:
        return Periodo(self.ano - 1, 12) if self.mes == 1 else Periodo(self.ano, self.mes - 1)

    @property
    def seguinte(self) -> Periodo:
        return Periodo(self.ano + 1, 1) if self.mes == 12 else Periodo(self.ano, self.mes + 1)

    def args(self) -> dict[str, int]:
        return {"ano": self.ano, "mes": self.mes}

    @classmethod
    def hoje(cls) -> Periodo:
        h = tempo.hoje()
        return cls(h.year, h.month)

    @classmethod
    def da_requisicao(cls, args) -> Periodo:
        """Lê ?ano=&mes= aceitando o mês como número (7) ou nome ("Julho")."""
        padrao = cls.hoje()
        ano = args.get("ano", type=int) or padrao.ano
        bruto = (args.get("mes") or "").strip()
        mes = padrao.mes
        if bruto.isdigit() and 1 <= int(bruto) <= 12:
            mes = int(bruto)
        elif bruto.capitalize() in MESES:
            mes = mes_numero(bruto.capitalize())
        ano = min(max(ano, 2000), 2100)
        return cls(ano, mes)
