from flask import render_template
from . import redacoes_bp

@redacoes_bp.route("/")
def dashboard():
    return render_template("redacoes/dashboard.html")

@redacoes_bp.route("/criar")
def criar():
    return render_template("redacoes/criar.html")

@redacoes_bp.route("/resultado")
def resultado():
    return render_template("redacoes/resultado.html")