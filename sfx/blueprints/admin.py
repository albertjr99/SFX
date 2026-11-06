"""Gestão de usuários.

* Perfis de gestão cadastram, editam, redefinem senha e desativam a equipe.
* Administradores fazem tudo isso com qualquer pessoa (inclusive outros
  administradores), concedem/retiram o acesso de administrador e excluem
  acessos definitivamente.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from ..constants import GRUPOS_ITENS, MODALIDADES, PERFIL_ADMIN, PERFIL_ANALISTA, PERFIS
from ..extensions import db
from ..models import ItemGrade, LinhaProducao, Situacao, Usuario
from ..security import exige, senha_provisoria

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _perfis_atribuiveis() -> dict[str, str]:
    if current_user.eh_admin:
        return PERFIS
    return {k: v for k, v in PERFIS.items() if k != PERFIL_ADMIN}


def _admins_ativos(exceto: int | None = None) -> int:
    consulta = Usuario.query.filter(
        Usuario.ativo.is_(True),
        or_(Usuario.administrador.is_(True), Usuario.tipo == PERFIL_ADMIN),
    )
    if exceto is not None:
        consulta = consulta.filter(Usuario.id != exceto)
    return consulta.count()


def _lista():
    usuarios = Usuario.query.order_by(Usuario.ativo.desc(), Usuario.tipo, Usuario.nome).all()
    registros = dict(
        db.session.query(LinhaProducao.usuario_id, func.count(LinhaProducao.id))
        .group_by(LinhaProducao.usuario_id)
        .all()
    )
    return usuarios, registros


def _render(senha_gerada=None):
    usuarios, registros = _lista()
    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios,
        registros=registros,
        perfis=_perfis_atribuiveis(),
        modalidades=MODALIDADES,
        senha_gerada=senha_gerada,
    )


@bp.get("/usuarios")
@exige("eh_gestor")
def usuarios():
    return _render()


def _ler_formulario(usuario: Usuario) -> list[str]:
    erros = []
    nome = (request.form.get("nome") or "").strip()[:50]
    email = (request.form.get("email") or "").strip().lower()[:100]
    tipo = request.form.get("tipo") or ""
    modalidade = request.form.get("modalidade") or ""

    if not nome:
        erros.append("Informe o nome.")
    if "@" not in email:
        erros.append("Informe um e-mail válido.")
    if tipo not in _perfis_atribuiveis():
        erros.append("Perfil inválido.")
    if tipo == PERFIL_ANALISTA and modalidade not in MODALIDADES:
        erros.append("Analistas precisam de modalidade (presencial ou teletrabalho).")

    duplicado_nome = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower(), Usuario.id != usuario.id).first()
    if nome and duplicado_nome:
        erros.append("Já existe alguém com esse nome — ele é usado no login.")
    duplicado_email = Usuario.query.filter(func.lower(Usuario.email) == email, Usuario.id != usuario.id).first()
    if email and duplicado_email:
        erros.append("Já existe alguém com esse e-mail.")

    administrador = bool(usuario.administrador)
    if current_user.eh_admin:
        administrador = bool(request.form.get("administrador"))
        perde_admin = usuario.id is not None and usuario.eh_admin and not (administrador or tipo == PERFIL_ADMIN)
        if perde_admin and usuario.id == current_user.id:
            erros.append("Você não pode retirar o próprio acesso de administrador.")
        elif perde_admin and _admins_ativos(exceto=usuario.id) == 0:
            erros.append("O sistema precisa de pelo menos um administrador ativo.")

    if not erros:
        usuario.nome = nome
        usuario.email = email
        usuario.tipo = tipo
        usuario.modalidade = modalidade if tipo == PERFIL_ANALISTA else ""
        usuario.pode_plano_acao = bool(request.form.get("pode_plano_acao"))
        usuario.administrador = administrador
    return erros


def _render_com_senha(usuario: Usuario, senha: str):
    flash(f"Senha provisória de {usuario.nome} gerada. Ela aparece só desta vez.", "sucesso")
    return _render({"usuario": usuario, "senha": senha})


@bp.post("/usuarios/novo")
@exige("eh_gestor")
def criar():
    usuario = Usuario(ativo=True, administrador=False)
    erros = _ler_formulario(usuario)
    if erros:
        for e in erros:
            flash(e, "erro")
        return redirect(url_for("admin.usuarios"))
    senha = senha_provisoria()
    usuario.definir_senha(senha, provisoria=True)
    db.session.add(usuario)
    db.session.commit()
    return _render_com_senha(usuario, senha)


@bp.post("/usuarios/<int:usuario_id>")
@exige("eh_gestor")
def editar(usuario_id: int):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    # Só administradores mexem em contas de administrador.
    if usuario.eh_admin and not current_user.eh_admin:
        abort(403)
    acao = request.form.get("acao", "salvar")

    if acao == "redefinir_senha":
        senha = senha_provisoria()
        usuario.definir_senha(senha, provisoria=True)
        db.session.commit()
        return _render_com_senha(usuario, senha)

    if acao == "alternar_ativo":
        if usuario.id == current_user.id:
            flash("Você não pode desativar o próprio acesso.", "erro")
        elif usuario.ativo and usuario.eh_admin and _admins_ativos(exceto=usuario.id) == 0:
            flash("O sistema precisa de pelo menos um administrador ativo.", "erro")
        else:
            usuario.ativo = not usuario.ativo
            db.session.commit()
            flash(f"{usuario.nome} {'reativado' if usuario.ativo else 'desativado'}.", "sucesso")
        return redirect(url_for("admin.usuarios"))

    if acao == "excluir":
        return _excluir(usuario)

    erros = _ler_formulario(usuario)
    if erros:
        db.session.rollback()
        for e in erros:
            flash(e, "erro")
    else:
        db.session.commit()
        flash(f"Dados de {usuario.nome} atualizados.", "sucesso")
    return redirect(url_for("admin.usuarios"))


def _excluir(usuario: Usuario):
    if not current_user.eh_admin:
        abort(403)
    if usuario.id == current_user.id:
        flash("Você não pode excluir o próprio acesso.", "erro")
        return redirect(url_for("admin.usuarios"))
    if usuario.eh_admin and _admins_ativos(exceto=usuario.id) == 0:
        flash("O sistema precisa de pelo menos um administrador ativo.", "erro")
        return redirect(url_for("admin.usuarios"))
    producao = LinhaProducao.query.filter_by(usuario_id=usuario.id).count()
    if producao:
        flash(
            f"{usuario.nome} tem {producao} registro(s) de produção. Para não apagar o histórico, "
            "desative o acesso em vez de excluir.",
            "erro",
        )
        return redirect(url_for("admin.usuarios"))
    # Linhas de outras pessoas alteradas por este usuário perdem só a autoria.
    LinhaProducao.query.filter_by(atualizado_por_id=usuario.id).update({"atualizado_por_id": None})
    nome = usuario.nome
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Acesso de {nome} excluído.", "sucesso")
    return redirect(url_for("admin.usuarios"))


# ---------------------------------------------------------------------------
# Colunas da grade (atividades e documentos) e situações — só administradores
# ---------------------------------------------------------------------------
@bp.get("/colunas")
@exige("eh_admin")
def colunas():
    from ..services import itens as itens_svc

    grupos = []
    for grupo, titulo in GRUPOS_ITENS.items():
        lista = itens_svc.listar(grupo, incluir_inativos=True)
        grupos.append({"grupo": grupo, "titulo": titulo, "itens": [(i, itens_svc.uso(i)) for i in lista]})
    situacoes = [(s, itens_svc.uso_situacao(s)) for s in itens_svc.situacoes(incluir_inativas=True)]
    return render_template("admin/colunas.html", grupos=grupos, lista_situacoes=situacoes)


def _volta_colunas(ancora: str):
    return redirect(url_for("admin.colunas") + f"#{ancora}")


@bp.post("/colunas/item/novo")
@exige("eh_admin")
def coluna_nova():
    from ..services import itens as itens_svc

    grupo = request.form.get("grupo", "")
    rotulo = (request.form.get("rotulo") or "").strip()
    if grupo not in GRUPOS_ITENS or not rotulo:
        flash("Informe o nome da nova coluna.", "erro")
        return _volta_colunas(grupo or "atividade")
    item = itens_svc.criar(grupo, rotulo, request.form.get("curto") or "")
    flash(f"“{item.rotulo}” adicionada.", "sucesso")
    return _volta_colunas(grupo)


@bp.post("/colunas/item/<int:item_id>")
@exige("eh_admin")
def coluna_editar(item_id: int):
    from ..services import itens as itens_svc

    item = db.session.get(ItemGrade, item_id) or abort(404)
    acao = request.form.get("acao", "salvar")
    if acao in ("subir", "descer"):
        itens_svc.mover(item, -1 if acao == "subir" else 1)
    elif acao == "alternar":
        item.ativo = not item.ativo
        db.session.commit()
        flash(f"“{item.rotulo}” {'reexibida' if item.ativo else 'ocultada'}. O histórico foi mantido.", "sucesso")
    elif acao == "excluir":
        usos = itens_svc.uso(item)
        if usos:
            flash(f"“{item.rotulo}” já foi marcada {usos} vez(es). Oculte-a para preservar o histórico.", "erro")
        else:
            db.session.delete(item)
            db.session.commit()
            flash(f"“{item.rotulo}” excluída.", "sucesso")
    else:
        rotulo = (request.form.get("rotulo") or "").strip()
        if not rotulo:
            flash("O nome não pode ficar vazio.", "erro")
        else:
            item.rotulo = rotulo[: itens_svc.LIMITE_ROTULO]
            item.curto = ((request.form.get("curto") or "").strip() or rotulo)[: itens_svc.LIMITE_CURTO]
            db.session.commit()
            flash(f"“{item.rotulo}” atualizada.", "sucesso")
    itens_svc.limpar_cache()
    return _volta_colunas(item.grupo)


@bp.post("/colunas/situacao/nova")
@exige("eh_admin")
def situacao_nova():
    from ..services import itens as itens_svc

    rotulo = (request.form.get("rotulo") or "").strip()
    if not rotulo:
        flash("Informe o nome da nova situação.", "erro")
        return _volta_colunas("situacoes")
    st = itens_svc.criar_situacao(
        rotulo,
        request.form.get("curto") or "",
        request.form.get("simbolo") or "",
        request.form.get("cor") or "",
        bool(request.form.get("pendente")),
    )
    flash(f"Situação “{st.rotulo}” adicionada.", "sucesso")
    return _volta_colunas("situacoes")


@bp.post("/colunas/situacao/<int:situacao_id>")
@exige("eh_admin")
def situacao_editar(situacao_id: int):
    from ..services import itens as itens_svc

    st = db.session.get(Situacao, situacao_id) or abort(404)
    acao = request.form.get("acao", "salvar")
    if acao in ("subir", "descer"):
        itens_svc.mover(st, -1 if acao == "subir" else 1)
    elif acao == "alternar":
        st.ativo = not st.ativo
        db.session.commit()
        flash(f"Situação “{st.rotulo}” {'reexibida' if st.ativo else 'ocultada'}.", "sucesso")
    elif acao == "excluir":
        usos = itens_svc.uso_situacao(st)
        if usos:
            flash(f"“{st.rotulo}” está em {usos} processo(s). Oculte-a para preservar o histórico.", "erro")
        else:
            db.session.delete(st)
            db.session.commit()
            flash(f"Situação “{st.rotulo}” excluída.", "sucesso")
    else:
        rotulo = (request.form.get("rotulo") or "").strip()
        if not rotulo:
            flash("O nome não pode ficar vazio.", "erro")
        else:
            st.rotulo = rotulo[:60]
            st.curto = ((request.form.get("curto") or "").strip() or rotulo)[:20]
            st.simbolo = ((request.form.get("simbolo") or "").strip() or "•")[:4]
            st.cor = itens_svc.cor_valida(request.form.get("cor"))
            st.pendente = bool(request.form.get("pendente"))
            db.session.commit()
            flash(f"Situação “{st.rotulo}” atualizada.", "sucesso")
    itens_svc.limpar_cache()
    return _volta_colunas("situacoes")
