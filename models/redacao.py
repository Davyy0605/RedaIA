from datetime import datetime
from extensions import db

class Redacao(db.Model):
    __tablename__ = "redacoes"

    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True
    )

    usuario = db.relationship("Usuario", back_populates="redacoes")
    competencia = db.relationship(
        "Competencia",
        back_populates="redacoes",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Redacao {self.id}>"