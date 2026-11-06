"""Comandos de linha (``flask --app wsgi <grupo> <comando>``).

Substituem os scripts avulsos da versão 1 (criar_usuario.py, resetar_banco.py…).
"""

from __future__ import annotations

import random
import shutil
from datetime import date
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import func

from . import tempo
from .constants import (
    CHAVES_ATIVIDADES,
    CHAVES_DOCUMENTOS,
    MODALIDADES,
    PERFIL_ANALISTA,
    PERFIS,
    STATUS,
)
from .extensions import db
from .models import LinhaProducao, PlanoAcaoCiclo, Usuario
from .security import senha_provisoria
from .services.periodo import Periodo
from .services.plano_acao import criar_ciclo


def registrar_comandos(app: Flask) -> None:
    app.cli.add_command(sfx)
    app.cli.add_command(usuarios)
    app.cli.add_command(plano)
    app.cli.add_command(demo)


# ---------------------------------------------------------------------------
DADOS_INICIAIS = Path(__file__).resolve().parent.parent / "dados_iniciais"


@click.group(help="Operação do sistema.")
def sfx():
    pass


@sfx.command("preparar")
def sfx_preparar():
    """Deixa o banco pronto para uso (seguro para rodar a cada inicialização).

    1. Se o banco SQLite ainda não existe e há ``dados_iniciais/producao.db``,
       copia-o (nunca sobrescreve um banco existente);
    2. aplica as migrações pendentes;
    3. se não há plano de ação e existe ``dados_iniciais/Pasta2.xlsx``, importa.
    """
    from flask_migrate import upgrade

    from .services.plano_acao import importar_planilha

    url = db.engine.url
    semente = DADOS_INICIAIS / "producao.db"
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        destino = Path(url.database)
        if not destino.exists() and semente.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(semente, destino)
            click.echo(f"Banco inicial copiado para {destino}.")
    upgrade()
    planilha = DADOS_INICIAIS / "Pasta2.xlsx"
    if planilha.exists() and not PlanoAcaoCiclo.query.first():
        anos = importar_planilha(planilha)
        click.echo(f"Plano de ação importado: {', '.join(map(str, anos)) or 'nada'}.")
    click.echo(f"Pronto. Usuários cadastrados: {Usuario.query.count()}.")


# ---------------------------------------------------------------------------
@click.group(help="Gerencia usuários.")
def usuarios():
    pass


@usuarios.command("listar")
def usuarios_listar():
    for u in Usuario.query.order_by(Usuario.tipo, Usuario.nome):
        situacao = "ativo" if u.ativo else "inativo"
        troca = " (senha provisória)" if u.precisa_trocar_senha else ""
        click.echo(f"{u.id:>4}  {u.nome:<20} {u.tipo:<11} {u.modalidade or '-':<12} {situacao}{troca}")


@usuarios.command("criar")
@click.option("--nome", required=True)
@click.option("--email", required=True)
@click.option("--tipo", type=click.Choice(list(PERFIS)), required=True)
@click.option("--modalidade", type=click.Choice(list(MODALIDADES)), default=None)
@click.option("--plano-acao", is_flag=True, help="Libera o acompanhamento do plano de ação.")
def usuarios_criar(nome, email, tipo, modalidade, plano_acao):
    if Usuario.query.filter(func.lower(Usuario.nome) == nome.lower()).first():
        raise click.ClickException(f"Já existe usuário com o nome {nome!r}.")
    if tipo == PERFIL_ANALISTA and not modalidade:
        raise click.ClickException("Analistas precisam de --modalidade.")
    senha = senha_provisoria()
    u = Usuario(
        nome=nome, email=email.lower(), tipo=tipo, modalidade=modalidade or "", ativo=True, pode_plano_acao=plano_acao
    )
    u.definir_senha(senha, provisoria=True)
    db.session.add(u)
    db.session.commit()
    click.echo(f"Usuário {nome} criado. Senha provisória: {senha}")


@usuarios.command("redefinir-senha")
@click.argument("nome")
def usuarios_redefinir(nome):
    u = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower()).first()
    if not u:
        raise click.ClickException(f"Usuário {nome!r} não encontrado.")
    senha = senha_provisoria()
    u.definir_senha(senha, provisoria=True)
    db.session.commit()
    click.echo(f"Nova senha provisória de {u.nome}: {senha}")


# ---------------------------------------------------------------------------
@click.group(help="Plano de ação (antiga planilha Pasta2.xlsx).")
def plano():
    pass


@plano.command("importar")
@click.argument("caminho", type=click.Path(exists=True, dir_okay=False))
@click.option("--substituir", is_flag=True, help="Sobrescreve ciclos já importados.")
def plano_importar(caminho, substituir):
    from .services.plano_acao import importar_planilha

    anos = importar_planilha(caminho, substituir=substituir)
    if anos:
        click.echo(f"Ciclos importados: {', '.join(map(str, anos))}.")
    else:
        click.echo("Nada importado (ciclos já existem; use --substituir para sobrescrever).")


# ---------------------------------------------------------------------------
@click.group(help="Dados fictícios para desenvolvimento e demonstração.")
def demo():
    pass


DEMO_USUARIOS = [
    ("Marina", "analista", "presencial"),
    ("Paulo", "analista", "presencial"),
    ("Renata", "analista", "presencial"),
    ("Tiago", "analista", "teletrabalho"),
    ("Helena", "gerente", ""),
    ("Bianca", "estagiaria", ""),
]
SOBRENOMES = [
    "Almeida",
    "Barbosa",
    "Cardoso",
    "Duarte",
    "Esteves",
    "Freitas",
    "Gomes",
    "Moreira",
    "Nunes",
    "Pereira",
    "Queiroz",
    "Rocha",
    "Siqueira",
    "Teixeira",
]
PRENOMES = [
    "Ana",
    "Carlos",
    "Dalva",
    "Edson",
    "Fátima",
    "Geraldo",
    "Iracema",
    "João",
    "Lúcia",
    "Márcio",
    "Neusa",
    "Osmar",
    "Rosa",
    "Sebastião",
    "Vera",
]
SETORES = ["SFX", "Conferência", "Protocolo", "Pensão", "Remessa", "SEGER"]


@demo.command("popular")
@click.option("--senha", default="demo1234", show_default=True)
@click.option("--meses", default=3, show_default=True, help="Quantos meses para trás preencher.")
@click.option("--forcar", is_flag=True, help="Permite rodar mesmo com usuários existentes.")
def demo_popular(senha, meses, forcar):
    """Cria usuários e produção fictícios (NÃO use em produção)."""
    if Usuario.query.count() and not forcar:
        raise click.ClickException("O banco já tem usuários. Use --forcar se tiver certeza.")
    rnd = random.Random(42)
    criados = []
    for nome, tipo, modalidade in DEMO_USUARIOS:
        u = Usuario.query.filter_by(nome=nome).first() or Usuario(
            nome=nome,
            email=f"{nome.lower()}@exemplo.gov.br",
            tipo=tipo,
            modalidade=modalidade,
            ativo=True,
            pode_plano_acao=(tipo == "gerente"),
        )
        u.definir_senha(senha)
        db.session.add(u)
        criados.append(u)
    db.session.flush()

    periodo = Periodo.hoje()
    for _ in range(meses):
        for u in (c for c in criados if c.tipo == PERFIL_ANALISTA):
            for semana in periodo.semanas:
                inicio = date(periodo.ano, periodo.mes, int(semana[:2]))
                if inicio > tempo.hoje():
                    continue
                for i in range(rnd.randint(6, 14)):
                    linha = LinhaProducao(
                        usuario_id=u.id,
                        ano=periodo.ano,
                        mes=periodo.nome_mes,
                        semana=semana,
                        indice_linha=i,
                        numero_processo=f"{rnd.randint(2019, periodo.ano)}-{rnd.randint(10000, 99999)}",
                        nome_do_segurado=f"{rnd.choice(PRENOMES)} {rnd.choice(SOBRENOMES)}",
                        setor=rnd.choice(SETORES),
                        status=rnd.choices([s.chave for s in STATUS], weights=[6, 2, 1, 1, 3])[0],
                    )
                    for chave in rnd.sample(CHAVES_ATIVIDADES, rnd.choice([1, 1, 1, 2])):
                        setattr(linha, chave, True)
                    for chave in rnd.sample(CHAVES_DOCUMENTOS, rnd.randint(0, 12)):
                        setattr(linha, chave, True)
                    db.session.add(linha)
        periodo = periodo.anterior
    db.session.commit()

    if not db.session.get(PlanoAcaoCiclo, tempo.hoje().year):
        ciclo = criar_ciclo(tempo.hoje().year)
        caixas = [60, 210, 140, 180]
        for mes in ciclo.meses[: tempo.hoje().month]:
            caixas = [max(0, c + rnd.randint(-25, 15)) for c in caixas]
            mes.caixa_pa, mes.caixa_in_p, mes.caixa_conferencia_p, mes.caixa_p_sem_pensao = caixas
            mes.data_extracao = f"05/{min(12, ciclo.meses.index(mes) + 1):02d}/{ciclo.ano}"
        ciclo.meses[0].observacoes = "Dados fictícios de demonstração."
        db.session.commit()
    click.echo(f"Dados de demonstração criados. Login: {', '.join(u.nome for u in criados)} / senha {senha}")
