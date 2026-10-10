from datetime import datetime

from extensions import db


class Redacao(db.Model):
    _tablename_ = "redacoes"

    id = db.Column(db.Integer, primary_key=True)
    tema = db.Column(db.String(255))  # tema informado pelo aluno (opcional)
    texto = db.Column(db.Text, nullable=False)
    # pendente -> corrigida (se a correção falhar, a redação é removida e o aluno reenvia)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id"), nullable=False, index=True
    )

    usuario = db.relationship("Usuario", back_populates="redacoes")
    competencia = db.relationship(
        "Competencia",
        back_populates="redacao",  # corrigido: antes estava "redacoes"
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def titulo(self) -> str:
        """Título dos cards: tema do aluno > tema identificado pela IA > início do texto."""
        if self.tema:
            return self.tema
        if self.competencia and self.competencia.tema_identificado:
            return self.competencia.tema_identificado
        return (self.texto[:60] + "…") if len(self.texto) > 60 else self.texto

    def _repr_(self):
        return f"<Redacao {self.id}>"