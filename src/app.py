# src/app.py
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
import jwt
from flask import Flask, g, jsonify, request
from flask_cors import CORS
import config
from scripts.build_world import setup_session_database
from src.database.central_database_manager import \
    CentralDatabaseManager  # NOVO IMPORT
from src.database.chromadb_manager import ChromaDBManager
from src.database.neo4j_manager import Neo4jManager
from src.database.sqlite_manager import SqliteManager
from src.engine.context_builder import ContextBuilder
from src.engine.game_engine import GameEngine
from src.engine.tool_processor import ToolProcessor
from src.utils.logging_config import setup_logging
from src.utils.request_logger import log_request



# --- INICIALIZAÇÃO ---
setup_logging()
app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÃO DE VERSÃO ---
SERVER_VERSION = "2.0.0"  # Refatorado para usar CentralDatabaseManager.
MINIMUM_CLIENT_VERSION = "1.5"

# --- GERENCIADORES SINGLETON ---
active_game_engines = {}
central_db_manager = CentralDatabaseManager()  # NOVO GESTOR
chromadb_manager_singleton = ChromaDBManager()
neo4j_manager_singleton = Neo4jManager()


# --- MIDDLEWARE E DECORADORES ---
@app.before_request
def set_user_id_from_token():
    g.current_user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
            g.current_user_id = data.get("user_id")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass  # Token inválido ou expirado, g.current_user_id permanece None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.current_user_id:
            return jsonify({"error": "Token de autenticação ausente ou inválido."}), 401
        return f(*args, **kwargs)

    return decorated


@app.after_request
def after_request_func(response):
    # Passa o user_id para o logger de requests
    user_id = g.current_user_id if hasattr(g, "current_user_id") else None
    if config.ENABLE_REQUEST_LOGGING:
        log_request(response, user_id)
    return response


# --- LÓGICA DE MOTOR DE JOGO ---
def get_or_create_game_engine(session_name: str):
    if session_name in active_game_engines:
        return active_game_engines[session_name]

    db_path = config.DB_PATH_SQLITE_TEMPLATE.format(session_name=session_name)
    if not os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_session_database(cursor)
            conn.commit()
            conn.close()
        except Exception as e:
            logging.critical(f"ERRO ao criar DB da sessão '{session_name}': {e}", exc_info=True)
            raise

    logging.info(f"--- INICIANDO NOVA INSTÂNCIA DE JOGO PARA A SESSÃO: {session_name} ---")
    data_manager = SqliteManager(session_name)
    context_builder = ContextBuilder(data_manager, chromadb_manager_singleton, session_name)
    tool_processor = ToolProcessor(data_manager, chromadb_manager_singleton, neo4j_manager_singleton)
    game_engine = GameEngine(context_builder, tool_processor)
    active_game_engines[session_name] = game_engine
    return game_engine


def sanitize_session_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w-]", "", name)
    name = name.strip("_-")
    return name[:50] or "personagem_sem_nome"


# --- ROTAS DE AUTENTICAÇÃO ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    try:
        central_db_manager.register_user(username, password)
        return jsonify({"message": f"Usuário '{username}' registrado com sucesso!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Este nome de usuário já existe."}), 409
    except Exception as e:
        logging.error(f"Erro ao registrar usuário {username}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao registrar usuário."}), 500


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    user_id = central_db_manager.authenticate_user(username, password)
    if not user_id:
        return jsonify({"error": "Credenciais inválidas."}), 401

    jwt_payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    jwt_token = jwt.encode(jwt_payload, config.JWT_SECRET_KEY, algorithm="HS256")
    return jsonify({"message": "Login bem-sucedido!", "token": jwt_token})


# --- ROTAS DE SESSÃO (AUTENTICADAS) ---
@app.route("/sessions", methods=["GET"])
@token_required
def get_sessions():
    try:
        sagas = central_db_manager.get_user_sagas(g.current_user_id)
        return jsonify(sagas)
    except Exception as e:
        logging.error(f"Erro ao listar sagas para o usuário {g.current_user_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao listar sagas."}), 500


@app.route("/sessions/create", methods=["POST"])
@token_required
def create_session():
    data = request.json
    char_name = data.get("character_name")
    world_concept = data.get("world_concept")

    if not char_name or not world_concept:
        return jsonify({"error": "Nome do personagem e conceito do mundo são obrigatórios."}), 400

    base_name = sanitize_session_name(char_name)
    random_suffix = uuid.uuid4().hex[:6]
    session_name = f"{base_name}_{random_suffix}"
    player_id_canonico = f"pj_{session_name}"

    try:
        central_db_manager.create_saga(
            g.current_user_id, session_name, char_name, world_concept
        )
        game_engine = get_or_create_game_engine(session_name)

        initial_action = (
            f"META-INSTRUÇÃO DE CONSTRUÇÃO DE MUNDO: Crie o universo para uma nova saga. "
            f"O personagem principal chama-se '{char_name}' e deve ter o id_canonico '{player_id_canonico}'. "
            f"O conceito do mundo é: '{world_concept}'. "
            f"Primeiro, defina um resumo para a saga. Depois, crie um local inicial apropriado, o personagem jogador, e coloque-o no local. "
            f"Finalmente, gere a narrativa de abertura."
        )

        narrative = game_engine.execute_turn(
            initial_action, world_concept, g.current_user_id
        )

        return jsonify(
            {
                "message": "Sessão criada com sucesso!",
                "session_name": session_name,
                "initial_narrative": narrative,
            }
        ), 201

    except Exception as e:
        logging.error(f"Erro ao criar sessão para o usuário {g.current_user_id}: {e}", exc_info=True)
        # Tenta reverter a criação da saga se algo falhar
        central_db_manager.delete_saga(g.current_user_id, session_name)
        return jsonify({"error": "Erro ao criar sessão."}), 500


@app.route("/sessions/<session_name>/execute_turn", methods=["POST"])
@token_required
def execute_turn_route(session_name: str):
    if not central_db_manager.check_saga_ownership(g.current_user_id, session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403

    world_concept = central_db_manager.get_world_concept(g.current_user_id, session_name)
    if not world_concept:
        return jsonify({"error": "Saga não encontrada ou sem conceito de mundo."}), 404

    player_action = request.json.get("player_action")
    if not player_action:
        return jsonify({"error": "player_action é obrigatório"}), 400

    game_engine = get_or_create_game_engine(session_name)
    narrative = game_engine.execute_turn(
        player_action, world_concept, g.current_user_id
    )
    return jsonify({"narrative": narrative})


@app.route("/sessions/<session_name>", methods=["DELETE"])
@token_required
def delete_session_route(session_name: str):
    if not central_db_manager.check_saga_ownership(g.current_user_id, session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403

    try:
        logging.warning(f"Iniciando exclusão da saga '{session_name}' para o usuário {g.current_user_id}.")

        if session_name in active_game_engines:
            del active_game_engines[session_name]
            logging.info(f"Instância do motor de jogo para '{session_name}' removida da memória.")

        neo4j_manager_singleton.delete_session_data(session_name)
        chromadb_manager_singleton.delete_collection(session_name)
        SqliteManager(session_name, supress_success_message=True).delete_database_file()
        central_db_manager.delete_saga(g.current_user_id, session_name)

        logging.info(f"Saga '{session_name}' apagada com sucesso.")
        return jsonify({"message": f"Saga '{session_name}' apagada com sucesso."}), 200

    except Exception as e:
        logging.error(f"Erro crítico ao apagar a saga '{session_name}': {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado ao apagar a saga."}), 500


if __name__ == "__main__":
    if not os.path.exists(config.DB_PATH_CENTRAL):
        logging.warning("Banco de dados central não encontrado. Criando agora...")
        os.system(f'python "{os.path.join("scripts", "build_world.py")}" --target central')

    logging.info("===========================================")
    logging.info(f"=    SERVIDOR DE SAGAS (v{SERVER_VERSION})    =")
    logging.info(f"Versão mínima do cliente: {MINIMUM_CLIENT_VERSION}")
    logging.info("===========================================")
    app.run(host="0.0.0.0", port=5000, debug=True)
