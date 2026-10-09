import hmac
import re

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from extensions import chave_login, db, limiter
from models import Usuario
from . import auth_bp

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _destino_seguro(destino):
    """Aceita só caminhos internos, para o ?next= não levar o aluno a outro site."""
    if destino and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute", key_func=chave_login, methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("redacoes.dashboard"))

    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            destino = _destino_seguro(request.args.get("next"))
            return redirect(destino or url_for("redacoes.dashboard"))

        # Mesma mensagem para e-mail inexistente e senha errada.
        flash("E-mail ou senha incorretos.", "erro")

    return render_template("auth/login.html", email=email)


@auth_bp.route("/cadastro", methods=["GET", "POST"])
@limiter.limit("100 per hour", methods=["POST"])  # generoso: a turma toda usa o mesmo IP
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("redacoes.dashboard"))

    codigo_esperado = current_app.config["CODIGO_CADASTRO"]
    dominio = current_app.config["ALLOWED_EMAIL_DOMAIN"]
    campos = {"nome": "", "email": ""}

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        confirmar = request.form.get("confirmar") or ""
        codigo = (request.form.get("codigo") or "").strip()
        campos = {"nome": nome, "email": email}

        erro = None
        if codigo_esperado and not hmac.compare_digest(codigo, codigo_esperado):
            erro = "Código de cadastro inválido."
        elif not nome or len(nome) > 100:
            erro = "Informe seu nome (até 100 caracteres)."
        elif not EMAIL_RE.match(email) or len(email) > 150:
            erro = "E-mail inválido."
        elif dominio and not email.endswith("@" + dominio):
            erro = f"Use seu e-mail @{dominio}."
        elif len(senha) < 8:
            erro = "A senha deve ter pelo menos 8 caracteres."
        elif senha != confirmar:
            erro = "As senhas não conferem."

        if not erro:
            usuario = Usuario(nome=nome, email=email)
            usuario.set_senha(senha)
            db.session.add(usuario)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                erro = "Este e-mail já está cadastrado."
            else:
                login_user(usuario)
                return redirect(url_for("redacoes.dashboard"))

        flash(erro, "erro")

    return render_template("auth/cadastro.html", exige_codigo=bool(codigo_esperado), **campos)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "ok")
    return redirect(url_for("auth.login"))