from flask import Blueprint

redacoes_bp = Blueprint(
    "redacoes", __name__, url_prefix="/redacoes", template_folder="../templates/redacoes"
)

from . import routes  # noqa: E402,F401