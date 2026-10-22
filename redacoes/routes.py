from datetime import datetime, timedelta

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from extensions import db
from models import Competencia, Redacao
from services.ia import corrigir_redacao
from . import redacoes_bp

MIN_CHARS = 400
MAX_CHARS = 6000
MAX_TEMA = 255

NOMES_COMPETENCIAS = [
    "Domínio da norma culta",
    "Compreensão da proposta",
    "Argumentação e repertório",
    "Coesão textual",
    "Proposta de intervenção",
]


@redacoes_bp.route("/")
@login_required
def dashboard():
    redacoes = (
        Redacao.query.options(joinedload(Redacao.competencia))
        .filter_by(usuario_id=current_user.id)
        .order_by(Redacao.criado_em.desc())
        .all()
    )
    return render_template("redacoes/dashboard.html", redacoes=redacoes)


@redacoes_bp.route("/criar", methods=["GET", "POST"])
@login_required
def criar():
    def formulario(tema="", texto=""):
        return render_template(
            "redacoes/criar.html", tema=tema, texto=texto, min_chars=MIN_CHARS, max_chars=MAX_CHARS
        )

    if request.method == "GET":
        return formulario()

    tema = (request.form.get("tema") or "").strip()
    texto = (request.form.get("texto") or "").strip()

    def recusar(mensagem):
        flash(mensagem, "erro")
        return formulario(tema, texto)  # devolve o texto: o aluno não perde o que escreveu

    if len(texto) < MIN_CHARS:
        return recusar(f"A redação precisa ter pelo menos {MIN_CHARS} caracteres.")
    if len(texto) > MAX_CHARS:
        return recusar(f"A redação pode ter no máximo {MAX_CHARS} caracteres.")

    if len(tema) > MAX_TEMA:
        return recusar(f"O tema pode ter no máximo {MAX_TEMA} caracteres.")

    agora = datetime.utcnow()

    # Impede envio duplicado (clique duplo / duas abas) enquanto uma correção está em andamento.
    em_andamento = Redacao.query.filter(
        Redacao.usuario_id == current_user.id,
        Redacao.status == "pendente",
        Redacao.criado_em >= agora - timedelta(minutes=3),
    ).first()
    if em_andamento:
        return recusar("Você já tem uma redação sendo corrigida. Aguarde o resultado.")

    # Limite diário por aluno (protege a cota de API; funciona com vários workers).
    limite = current_app.config["MAX_REDACOES_POR_DIA"]
    enviadas = Redacao.query.filter(
        Redacao.usuario_id == current_user.id,
        Redacao.criado_em >= agora - timedelta(hours=24),
    ).count()
    if enviadas >= limite:
        return recusar(f"Você atingiu o limite de {limite} redações por dia. Tente novamente amanhã.")

    redacao = Redacao(usuario_id=current_user.id, tema=tema or None, texto=texto, status="pendente")
    db.session.add(redacao)
    db.session.commit()
    redacao_id = redacao.id

    try:
        dados = corrigir_redacao(texto, tema)
        db.session.add(Competencia.from_json(redacao_id, dados))
        redacao.status = "corrigida"
        db.session.commit()
    except Exception as erro:
        # Linha curta e fácil de achar nos logs do Render (busque por "FALHA NA CORRECAO").
        current_app.logger.error(
            "FALHA NA CORRECAO da redação %s: %s: %s", redacao_id, type(erro).__name__, erro
        )
        current_app.logger.exception("Detalhes da falha na redação %s", redacao_id)
        db.session.rollback()
        falhou = db.session.get(Redacao, redacao_id)
        if falhou:
            db.session.delete(falhou)  # libera o envio: o aluno pode tentar de novo
            db.session.commit()
        return recusar("Não foi possível corrigir agora. Seu texto foi mantido, tente de novo em instantes.")

    return redirect(url_for("redacoes.resultado", redacao_id=redacao_id))


@redacoes_bp.route("/resultado/<int:redacao_id>")
@login_required
def resultado(redacao_id):
    redacao = db.session.get(Redacao, redacao_id)
    # 404 (e não 403) também para redação de outro aluno: não revela que o número existe.
    if not redacao or redacao.usuario_id != current_user.id:
        abort(404)

    if not redacao.competencia:
        flash("Esta redação ainda não foi corrigida.", "erro")
        return redirect(url_for("redacoes.dashboard"))

    c = redacao.competencia
    dados = c.to_dict()
    competencias = [
        (nome, dados["competencias"][f"competencia_{i}"]["nota"],
         dados["competencias"][f"competencia_{i}"]["justificativa"])
        for i, nome in enumerate(NOMES_COMPETENCIAS, start=1)
    ]
    return render_template(
        "redacoes/resultado.html", redacao=redacao, c=c, competencias=competencias
    )