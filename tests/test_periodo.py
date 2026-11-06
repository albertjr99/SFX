import calendar
from datetime import date, datetime, timedelta

from werkzeug.datastructures import MultiDict

from sfx.services.periodo import Periodo, gerar_semanas, semana_atual


def gerar_semanas_v1(mes_num, ano):
    """Cópia literal da função da versão 1 — as chaves gravadas no banco dependem dela."""
    semanas = []
    primeiro_dia = datetime(ano, mes_num, 1)
    ultimo_dia = datetime(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
    semana = []
    dia = primeiro_dia
    while dia <= ultimo_dia:
        if dia.weekday() < 5:
            semana.append(dia.strftime("%d/%m"))
        if dia.weekday() == 4 or dia == ultimo_dia:
            if semana:
                semanas.append(f"{semana[0]} a {semana[-1]}")
                semana = []
        dia += timedelta(days=1)
    return semanas


def test_semanas_identicas_a_v1_em_varios_anos():
    for ano in (2024, 2025, 2026, 2028):
        for mes in range(1, 13):
            assert gerar_semanas(mes, ano) == gerar_semanas_v1(mes, ano), (mes, ano)


def test_exemplo_julho_2025():
    assert gerar_semanas(7, 2025) == [
        "01/07 a 04/07",
        "07/07 a 11/07",
        "14/07 a 18/07",
        "21/07 a 25/07",
        "28/07 a 31/07",
    ]


def test_navegacao_entre_anos():
    assert Periodo(2025, 12).seguinte == Periodo(2026, 1)
    assert Periodo(2026, 1).anterior == Periodo(2025, 12)
    assert Periodo(2025, 3).rotulo == "Março de 2025"


def test_da_requisicao_aceita_nome_ou_numero():
    assert Periodo.da_requisicao(MultiDict({"mes": "Julho", "ano": "2025"})) == Periodo(2025, 7)
    assert Periodo.da_requisicao(MultiDict({"mes": "3", "ano": "2024"})) == Periodo(2024, 3)
    padrao = Periodo.da_requisicao(MultiDict({"mes": "xyz"}))
    assert 1 <= padrao.mes <= 12


def test_semana_atual():
    assert semana_atual(7, 2025, hoje=date(2025, 7, 9)) == "07/07 a 11/07"
    assert semana_atual(7, 2025, hoje=date(2025, 7, 12)) == "07/07 a 11/07"  # sábado
    assert semana_atual(7, 2025, hoje=date(2025, 8, 1)) is None
