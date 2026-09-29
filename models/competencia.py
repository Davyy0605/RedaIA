from datetime import datetime
from extensions import db

class Competencia(db.Model):
    """Resultado da correção de uma redação(JSON da I.A)"""

    __tablename__ = "competencias"

    id = db.Column(db.Integer, primary_key=True)
    redacao_id = db.Column(
        db.Integer, db.ForeignKey("redacoes.id"), nullable=False, unique=True
    )

    tema_identificado = db.Column(db.String(225))
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

    # listas de dicts: [{repertorio, pertinente, produtivo}] e [{repetorio, como_utilizar}]
    repertorios_utilizados = db.Column(db.JSON, default=list)
    repertorios_sugeridos = db.Column(db.JSON, default=list)

    fuga_ao_tema = db.Column(db.Boolean, default=False)
    tangenciamento = db.Column(db.Boolean, default=False)
    diagnostico_observacao = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    redacao = db.relationship("Redacao", back_populates="competencia")

    @classmethod
    def from_json(cls, redacao_id: int, data: dict) ->"Competencia":
        """Converte o JSON retornado pela OpenAI em um registro"""
        comps = data.get("competencias", {})
        diag = data.get("diagnostico", {})
        obj = cls(
            redacao_id=redacao_id,
            tema_identificado=data.get("tema_identificado"),
            nota_final=data.get("nota_final", 0),
            repertorios_utilizados=data.get("repertorios_utilizados", []),
            repertorios_sugeridos=data.get("repertorios_sugeridos", []),
            fuga_ao_tema=diag.get("fuga_ao_tema", False),
            tangenciamento=diag.get("tangenciamento", False),
            diagnostico_observacao=diag.get("observacao"),
        )
        for i in range (1, 6):
            c = comps.get(f"competencia_{i}", {})
            setattr(obj, f"competencia_{i}_nota", c.get("nota", 0))
            setattr(obj, f"competencia_{i}_justificativa", c.get("justificativa"))
        return obj

    def to_dict(self) -> dict:
        return{
            "tema_identificado": self.tema_identificado,
            "competencias": {
                f"competencia_{i}": {
                    "nota": getattr(self, f"competencia_{i}_nota"),
                    "justificativa": getattr(self, f"competencia_{i}_justificativa"),
                }
                for i in range(1, 6)
            },
            "repertorios_utilizados": self.repertorios_utilizados,
            "repertorios_sugeridos": self.repertorios_sugeridos,
            "nota_final": self.nota_final,
            "diagnostico": {
                "fuga_ao_tema": self.fuga_ao_tema,
                "tangeciamento": self.tangeciamento,
                "observacao": self.diagnostico_observacao,
            },
        }

    def __repr__(self):
        return f"<Competencia redacao={self.redacao_id} nota={self.nota_final}"