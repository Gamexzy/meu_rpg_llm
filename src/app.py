# src/app.py
import logging
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from src import config
from src.database.central_db_manager import CentralDbManager
from src.utils.logging_config import setup_logging
from src.utils.auth import set_user_id_from_token
from src.utils.request_logger import log_request

# --- Importar os Blueprints das Rotas ---
from src.routes.universes import universes_bp
# Futuramente:
# from src.routes.characters import characters_bp
# from src.routes.adventures import adventures_bp

# --- Inicialização ---
setup_logging()
app = Flask(__name__)
CORS(app)
app.config["JWT_SECRET_KEY"] = config.JWT_SECRET_KEY

# --- Registrar os Blueprints na Aplicação ---
app.register_blueprint(universes_bp, url_prefix='/api')
# Futuramente:
# app.register_blueprint(characters_bp, url_prefix='/api')
# app.register_blueprint(adventures_bp, url_prefix='/api')

# --- Gerenciadores ---
central_db_manager = CentralDbManager()

# --- Middlewares ---
app.before_request(set_user_id_from_token)
app.after_request(log_request)

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    try:
        central_db_manager.register_user(username, password)
        return jsonify({"message": f"Usuário '{username}' registrado com sucesso!"}), 201
    except Exception as e:
        logging.error(f"Erro ao registrar usuário {username}: {e}", exc_info=True)
        return jsonify({"error": "Este nome de usuário já existe ou ocorreu um erro."}), 409

@app.route("/api/auth/login", methods=["POST"])
def login():
    from src.utils.auth import generate_token # Importação local para evitar dependência circular
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    user_id = central_db_manager.authenticate_user(username, password)
    if not user_id:
        return jsonify({"error": "Credenciais inválidas."}), 401

    token = generate_token(user_id)
    return jsonify({"message": "Login bem-sucedido!", "token": token})


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # Garante que o banco de dados central exista ao iniciar
    if not os.path.exists(config.DB_PATH_CENTRAL):
        logging.warning("Banco de dados central não encontrado. Criando agora...")
        os.system(f'python "{os.path.join("scripts", "build_world.py")}" --target central')

    logging.info("===========================================")
    logging.info(f"=    SERVIDOR DE RPG (v{config.CONFIG_VERSION})   =")
    logging.info("===========================================")
    app.run(host="0.0.0.0", port=5000, debug=True)
