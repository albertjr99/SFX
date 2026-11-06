import pytest

from sfx import create_app
from sfx.extensions import db
from sfx.models import Usuario

SENHA = "senha-teste-1"


@pytest.fixture()
def app():
    from sfx.security import limitador_login

    limitador_login._falhas.clear()
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        from sfx.services.itens import semear_padrao

        semear_padrao()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _usuario(nome, tipo, modalidade="", provisoria=False, **extra):
    u = Usuario(nome=nome, email=f"{nome.lower()}@teste.gov.br", tipo=tipo, modalidade=modalidade, ativo=True, **extra)
    u.definir_senha(SENHA, provisoria=provisoria)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def usuarios(app):
    return {
        "analista": _usuario("Ana", "analista", "presencial"),
        "analista2": _usuario("Beto", "analista", "teletrabalho"),
        "gerente": _usuario("Gil", "gerente"),
        "estagiaria": _usuario("Eva", "estagiaria"),
    }


@pytest.fixture()
def entrar(client):
    def _entrar(usuario_ou_nome, senha=SENHA):
        nome = getattr(usuario_ou_nome, "nome", usuario_ou_nome)
        return client.post("/login", data={"usuario": nome, "senha": senha})

    return _entrar


def marcar(linha, *chaves):
    """Marca atividades/documentos (pelas chaves) numa LinhaProducao."""
    from sfx.models import ItemGrade

    linha.itens = list(linha.itens) + ItemGrade.query.filter(ItemGrade.chave.in_(chaves)).all()
