from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para acessar essa página", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def cuidador_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para acessar essa página", "error")
            return redirect(url_for("login"))

        if session.get("perfil") != "cuidador":
            flash("Acesso restrito ao cuidador", "error")
            return redirect(url_for("home"))

        return func(*args, **kwargs)
    return wrapper


def familiar_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para acessar essa página", "error")
            return redirect(url_for("login"))

        if session.get("perfil") != "familiar":
            flash("Acesso restrito ao familiar", "error")
            return redirect(url_for("home"))

        return func(*args, **kwargs)
    return wrapper