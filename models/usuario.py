from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(225), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    redacoes = db.relationship(
        "Redacao", back_populates="usuario", cascade="all, delete-orphan"
    )

    def set_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<Usuario {self.email}>"