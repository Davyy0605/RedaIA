from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Sem limite global por IP: numa escola, todos os alunos saem pelo MESMO IP
# e um limite geral bloquearia a turma inteira. Os limites ficam só nas rotas sensíveis.
limiter = Limiter(get_remote_address, default_limits=[], storage_uri="memory://")


def chave_login():
    """Limita tentativas por IP + e-mail, para um aluno errando a senha não travar os colegas."""
    email = (request.form.get("email") or "").strip().lower()
    return f"{get_remote_address()}:{email}"