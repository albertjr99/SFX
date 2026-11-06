from datetime import UTC, date, datetime

from sfx import tempo


def test_utc_vira_horario_de_sao_paulo(app):
    # 02:30 UTC de 07/11 ainda é 06/11 às 23:30 em São Paulo
    assert tempo.formatar(datetime(2026, 11, 7, 2, 30), com_hora=True) == "06/11/2026 23:30"
    assert tempo.formatar(datetime(2026, 11, 7, 2, 30, tzinfo=UTC)) == "06/11/2026"
    assert tempo.formatar(date(2026, 1, 5)) == "05/01/2026"
    assert tempo.formatar(None) == ""


def test_hoje_usa_fuso_de_sao_paulo(app):
    assert tempo.agora().utcoffset().total_seconds() == -3 * 3600
    assert tempo.hoje() == tempo.agora().date()


def test_normaliza_datas_para_padrao_brasileiro():
    assert tempo.normalizar_data_br("5/1/26") == "05/01/2026"
    assert tempo.normalizar_data_br("05-01-2026") == "05/01/2026"
    assert tempo.normalizar_data_br("2026-01-05 00:00:00") == "05/01/2026"
    assert tempo.normalizar_data_br(" 02/07/2024") == "02/07/2024"
    assert tempo.normalizar_data_br("31/02/2026") == "31/02/2026"  # inválida: mantém o texto
    assert tempo.normalizar_data_br("Fechamento") == "Fechamento"
    assert tempo.normalizar_data_br("") == ""


def test_filtros_de_template(app):
    env = app.jinja_env
    assert env.from_string("{{ d|data_hora_br }}").render(d=datetime(2026, 3, 1, 12, 0)) == "01/03/2026 09:00"
    assert env.from_string("{{ d|data_br }}").render(d=datetime(2026, 3, 1, 1, 0)) == "28/02/2026"
