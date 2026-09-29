from flask import Flask
from auth import auth_bp
from redacoes import redacoes_bp

app = Flask(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(redacoes_bp)

if __name__ == "__main__":
    app.run(debug=True)