from datetime import datetime, timedelta

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from extensions import db, limiter
from models import Competencia, Redacao
from services.ia import corrigir_redacao, transcrever_imagens
from . import redacoes_bp

MIN_CHARS = 400
MAX_CHARS = 6000
MAX_TEMA = 255

# Transcrição por foto. O navegador já reduz a foto antes de enviar (~0,5 MB cada).
MAX_FOTOS = 3
MAX_BYTES_FOTO = 4 * 1024 * 1024
MAX_BYTES_TRANSCRICAO = MAX_FOTOS * MAX_BYTES_FOTO + 64 * 1024  # usado em app.py

# Assinaturas dos formatos aceitos (não confia na extensão nem no mimetype do navegador).
ASSINATURAS_IMAGEM = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def _tipo_imagem(conteudo: bytes) -> str | None:
    for assinatura, mimetype in ASSINATURAS_IMAGEM:
        if conteudo.startswith(assinatura):
            return mimetype
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    return None

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
            "redacoes/criar.html", tema=tema, texto=texto, min_chars=MIN_CHARS, max_chars=MAX_CHARS,
            max_fotos=MAX_FOTOS,
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
    except Exception:
        current_app.logger.exception("Falha ao corrigir a redação %s", redacao_id)
        db.session.rollback()
        falhou = db.session.get(Redacao, redacao_id)
        if falhou:
            db.session.delete(falhou)  # libera o envio: o aluno pode tentar de novo
            db.session.commit()
        return recusar("Não foi possível corrigir agora. Seu texto foi mantido, tente de novo em instantes.")

    return redirect(url_for("redacoes.resultado", redacao_id=redacao_id))


@redacoes_bp.route("/transcrever", methods=["POST"])
@login_required
@limiter.limit("5 per minute;30 per day", key_func=lambda: f"transcrever:{current_user.id}")
def transcrever():
    """Recebe fotos da redação manuscrita e devolve o texto transcrito para o aluno revisar."""
    fotos = [f for f in request.files.getlist("fotos") if f and f.filename]
    if not fotos:
        return jsonify(erro="Envie pelo menos uma foto da redação."), 400
    if len(fotos) > MAX_FOTOS:
        return jsonify(erro=f"Envie no máximo {MAX_FOTOS} fotos."), 400

    imagens = []
    for foto in fotos:
        conteudo = foto.read(MAX_BYTES_FOTO + 1)
        if len(conteudo) > MAX_BYTES_FOTO:
            return jsonify(erro="Uma das fotos é grande demais. Tente outra foto."), 400
        mimetype = _tipo_imagem(conteudo)
        if not mimetype:
            return jsonify(erro="Formato de imagem não suportado. Use JPG, PNG ou WEBP."), 400
        imagens.append((conteudo, mimetype))

    try:
        resultado = transcrever_imagens(imagens)
    except Exception:
        current_app.logger.exception("Falha ao transcrever fotos do usuário %s", current_user.id)
        return jsonify(erro="Não foi possível ler a foto agora. Tente de novo em instantes."), 502

    if not resultado["texto"]:
        aviso = resultado["aviso"] or "Não encontramos texto na foto."
        return jsonify(erro=f"{aviso} Tente uma foto mais nítida, com boa luz e a folha inteira."), 422

    return jsonify(texto=resultado["texto"][:MAX_CHARS], aviso=resultado["aviso"])


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