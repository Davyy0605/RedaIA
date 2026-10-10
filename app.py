import os
from datetime import timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, redirect, url_for  # noqa: E402
from flask_login import current_user  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from auth import auth_bp  # noqa: E402
from extensions import csrf, db, limiter, login_manager  # noqa: E402
from models import Usuario  # noqa: E402  (importar os models registra as tabelas)
from redacoes import redacoes_bp  # noqa: E402


def create_app():
    app = Flask(__name__)

    db_url = os.environ.get("DATABASE_URL", "sqlite:///redaia.db")
    if db_url.startswith("postgres://"):  # prefixo antigo usado por algumas plataformas
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    em_producao = os.environ.get("APP_ENV") == "production"

    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=em_producao,
        MAX_CONTENT_LENGTH=64 * 1024,  # nenhum formulário precisa de mais que isso
        MAX_REDACOES_POR_DIA=int(os.environ.get("MAX_REDACOES_POR_DIA", 5)),
        CODIGO_CADASTRO=os.environ.get("CODIGO_CADASTRO", "").strip(),
        ALLOWED_EMAIL_DOMAIN=os.environ.get("ALLOWED_EMAIL_DOMAIN", "").strip().lower(),
    )

    if em_producao:
        # No Render há um proxy na frente: sem isso o app enxergaria o IP do proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "erro"

    @login_manager.user_loader
    def carregar_usuario(user_id):
        return db.session.get(Usuario, int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(redacoes_bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("redacoes.dashboard"))
        return redirect(url_for("auth.login"))

    @app.template_filter("data_br")
    def data_br(dt):
        if not dt:
            return ""
        local = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/Recife"))
        return local.strftime("%d/%m/%Y")

    @app.errorhandler(429)
    def muitas_tentativas(_erro):
        return "Muitas tentativas. Aguarde um minuto e tente novamente.", 429

    with app.app_context():
        db.create_all()  # suficiente para o piloto; depois considere Flask-Migrate

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)