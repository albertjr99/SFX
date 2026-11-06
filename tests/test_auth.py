from sfx.extensions import db
from sfx.models import Usuario

from .conftest import SENHA, _usuario


def test_login_redireciona_por_perfil(client, usuarios, entrar):
    r = entrar(usuarios["analista"])
    assert r.status_code == 302 and r.headers["Location"].endswith("/producao")
    client.post("/logout")
    r = entrar(usuarios["gerente"])
    assert r.headers["Location"].endswith("/gestao/")
    client.post("/logout")
    r = entrar(usuarios["estagiaria"])
    assert r.headers["Location"].endswith("/equipe/producao")


def test_login_por_email_e_sem_diferenciar_maiusculas(client, usuarios, entrar):
    assert entrar("ANA").status_code == 302
    client.post("/logout")
    assert entrar("ana@teste.gov.br").status_code == 302


def test_login_invalido_mostra_mensagem(client, usuarios, entrar):
    r = entrar("Ana", "errada")
    assert r.status_code == 200
    assert "Usuário ou senha incorretos" in r.get_data(as_text=True)


def test_bloqueio_apos_varias_tentativas(client, usuarios, entrar):
    for _ in range(5):
        entrar("Ana", "errada")
    r = entrar("Ana", SENHA)
    assert r.status_code == 429


def test_usuario_desativado_nao_entra(client, usuarios, entrar):
    usuarios["analista"].ativo = False
    db.session.commit()
    r = entrar(usuarios["analista"])
    assert r.status_code == 200
    assert "desativado" in r.get_data(as_text=True)


def test_senha_provisoria_obriga_troca(client, app, entrar):
    u = _usuario("Novo", "analista", "presencial", provisoria=True)
    r = entrar(u)
    assert r.headers["Location"].endswith("/conta/senha")
    # qualquer outra página volta para a troca de senha
    assert client.get("/producao").headers["Location"].endswith("/conta/senha")

    r = client.post("/conta/senha", data={"senha_atual": SENHA, "nova_senha": "curta", "confirmacao": "curta"})
    assert "pelo menos" in r.get_data(as_text=True)

    r = client.post(
        "/conta/senha", data={"senha_atual": SENHA, "nova_senha": "NovaSenha9", "confirmacao": "NovaSenha9"}
    )
    assert r.status_code == 302
    assert db.session.get(Usuario, u.id).primeiro_acesso_realizado
    assert client.get("/producao").status_code == 200


def test_logout_exige_post(client, usuarios, entrar):
    entrar(usuarios["analista"])
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    assert client.get("/producao").status_code == 302


def test_next_nao_permite_redirecionamento_externo(client, usuarios):
    r = client.post("/login?next=https://malicioso.example/", data={"usuario": "Ana", "senha": SENHA})
    assert r.headers["Location"].endswith("/producao")


def test_csrf_ativo_fora_dos_testes(app, usuarios):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    r = c.post("/login", data={"usuario": "Ana", "senha": SENHA})
    assert r.status_code == 400


def test_cabecalhos_de_seguranca(client):
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
