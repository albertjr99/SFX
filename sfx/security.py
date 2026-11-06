"""Controle de acesso, política de senha e limitação de tentativas de login."""

from __future__ import annotations

import secrets
import string
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app
from flask_login import current_user, login_required


def perfis_requeridos(*perfis: str):
    """Restringe a rota a perfis específicos (ou a um predicado do usuário)."""

    def decorador(view):
        @wraps(view)
        @login_required
        def envoltorio(*args, **kwargs):
            if current_user.tipo not in perfis:
                abort(403)
            return view(*args, **kwargs)

        return envoltorio

    return decorador


def exige(predicado_nome: str):
    """Ex.: ``@exige("eh_gestor")`` — usa as propriedades de ``Usuario``."""

    def decorador(view):
        @wraps(view)
        @login_required
        def envoltorio(*args, **kwargs):
            if not getattr(current_user, predicado_nome, False):
                abort(403)
            return view(*args, **kwargs)

        return envoltorio

    return decorador


def problemas_senha(senha: str, confirmacao: str | None = None) -> list[str]:
    minimo = current_app.config.get("SFX_SENHA_MINIMA", 8)
    erros = []
    if len(senha) < minimo:
        erros.append(f"A senha precisa ter pelo menos {minimo} caracteres.")
    if senha.isdigit() or senha.isalpha():
        erros.append("Combine letras e números.")
    if confirmacao is not None and senha != confirmacao:
        erros.append("A confirmação não confere com a nova senha.")
    return erros


def senha_provisoria(tamanho: int = 10) -> str:
    alfabeto = string.ascii_letters + string.digits
    alfabeto = "".join(c for c in alfabeto if c not in "0OolI1")
    while True:
        senha = "".join(secrets.choice(alfabeto) for _ in range(tamanho))
        if any(c.isdigit() for c in senha) and any(c.isalpha() for c in senha):
            return senha


class LimitadorLogin:
    """Bloqueio simples em memória por (IP, usuário) após falhas seguidas.

    Suficiente para um único processo/worker. Para vários workers, use um
    proxy reverso com limitação de taxa ou um backend compartilhado.
    """

    def __init__(self) -> None:
        self._falhas: dict[str, deque[float]] = defaultdict(deque)
        self._trava = threading.Lock()

    def _limpar(self, chave: str, janela: float) -> deque[float]:
        fila = self._falhas[chave]
        limite = time.monotonic() - janela
        while fila and fila[0] < limite:
            fila.popleft()
        return fila

    def bloqueado(self, chave: str) -> bool:
        cfg = current_app.config
        with self._trava:
            fila = self._limpar(chave, cfg["SFX_JANELA_LOGIN_MIN"] * 60)
            return len(fila) >= cfg["SFX_TENTATIVAS_LOGIN"]

    def falhou(self, chave: str) -> None:
        with self._trava:
            self._falhas[chave].append(time.monotonic())

    def sucesso(self, chave: str) -> None:
        with self._trava:
            self._falhas.pop(chave, None)


limitador_login = LimitadorLogin()
