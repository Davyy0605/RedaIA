from datetime import datetime

from extensions import db

NOTAS_VALIDAS = (0, 40, 80, 120, 160, 200)


def _normalizar_nota(valor) -> int:
    """Garante nota inteira de 0 a 200 em múltiplos de 40 (escala do ENEM)."""
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return 0
    n = max(0, min(200, n))
    return min(NOTAS_VALIDAS, key=lambda v: abs(v - n))


def _lista_de_dicts(valor) -> list:
    return [i for i in valor if isinstance(i, dict)] if isinstance(valor, list) else []


class Competencia(db.Model):
    """Resultado da correção de uma redação (JSON da I.A)"""

    _tablename_ = "competencias"

    id = db.Column(db.Integer, primary_key=True)
    redacao_id = db.Column(
        db.Integer, db.ForeignKey("redacoes.id"), nullable=False, unique=True
    )

    tema_identificado = db.Column(db.String(255))
    nota_final = db.Column(db.Integer, default=0)

    competencia_1_nota = db.Column(db.Integer, default=0)
    competencia_1_justificativa = db.Column(db.Text)
    competencia_2_nota = db.Column(db.Integer, default=0)
    competencia_2_justificativa = db.Column(db.Text)
    competencia_3_nota = db.Column(db.Integer, default=0)
    competencia_3_justificativa = db.Column(db.Text)
    competencia_4_nota = db.Column(db.Integer, default=0)
    competencia_4_justificativa = db.Column(db.Text)
    competencia_5_nota = db.Column(db.Integer, default=0)
    competencia_5_justificativa = db.Column(db.Text)

    # [{repertorio, pertinente, produtivo}] e [{repertorio, como_utilizar}]
    repertorios_utilizados = db.Column(db.JSON, default=list)
    repertorios_sugeridos = db.Column(db.JSON, default=list)

    fuga_ao_tema = db.Column(db.Boolean, default=False)
    tangenciamento = db.Column(db.Boolean, default=False)
    diagnostico_observacao = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    redacao = db.relationship("Redacao", back_populates="competencia")

    @classmethod
    def from_json(cls, redacao_id: int, data: dict) -> "Competencia":
        """Converte o JSON retornado pela IA em um registro, validando e normalizando."""
        comps = data.get("competencias") or {}
        diag = data.get("diagnostico") or {}

        obj = cls(
            redacao_id=redacao_id,
            tema_identificado=(str(data.get("tema_identificado") or "")[:255] or None),
            repertorios_utilizados=_lista_de_dicts(data.get("repertorios_utilizados")),
            repertorios_sugeridos=_lista_de_dicts(data.get("repertorios_sugeridos")),
            fuga_ao_tema=bool(diag.get("fuga_ao_tema", False)),
            tangenciamento=bool(diag.get("tangenciamento", False)),
            diagnostico_observacao=diag.get("observacao"),
        )

        total = 0
        for i in range(1, 6):
            c = comps.get(f"competencia_{i}") or {}
            nota = _normalizar_nota(c.get("nota"))
            total += nota
            setattr(obj, f"competencia_{i}_nota", nota)
            setattr(obj, f"competencia_{i}_justificativa", c.get("justificativa"))

        # Não confiamos na soma da IA: recalculamos a partir das 5 notas.
        obj.nota_final = total
        return obj

    def to_dict(self) -> dict:
        return {
            "tema_identificado": self.tema_identificado,
            "competencias": {
                f"competencia_{i}": {
                    "nota": getattr(self, f"competencia_{i}_nota"),
                    "justificativa": getattr(self, f"competencia_{i}_justificativa"),
                }
                for i in range(1, 6)
            },
            "repertorios_utilizados": self.repertorios_utilizados or [],
            "repertorios_sugeridos": self.repertorios_sugeridos or [],
            "nota_final": self.nota_final,
            "diagnostico": {
                "fuga_ao_tema": self.fuga_ao_tema,
                "tangenciamento": self.tangenciamento,  # corrigido: antes "tangeciamento"
                "observacao": self.diagnostico_observacao,
            },
        }

    def _repr_(self):
        return f"<Competencia redacao={self.redacao_id} nota={self.nota_final}>"