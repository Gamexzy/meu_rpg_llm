# src/app.py

import logging
import os
import re
import sqlite3
import uuid
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import config
from scripts.build_world import setup_session_database  
from src.database.sqlite_manager import SqliteManager
from src.database.chromadb_manager import ChromaDBManager
from src.database.neo4j_manager import Neo4jManager
from src.engine.context_builder import ContextBuilder
from src.engine.tool_processor import ToolProcessor
from src.engine.game_engine import GameEngine
from src.utils.request_logger import log_request
from src.utils.logging_config import setup_logging

# --- INICIALIZAÇÃO DO LOGGING ---
setup_logging()

# --- CONFIGURAÇÃO DE VERSÃO ---
SERVER_VERSION = "1.11.0" # Adicionada rota para apagar sagas.
MINIMUM_CLIENT_VERSION = "1.5"

# --- GERENCIADOR DE SESSÕES ---
active_game_engines = {}

app = Flask(__name__)
CORS(app)

# --- INICIALIZAÇÃO DOS GESTORES GLOBAIS (SINGLETON) ---
chromadb_manager_singleton = ChromaDBManager()
neo4j_manager_singleton = Neo4jManager()


# --- FUNÇÕES DE BANCO DE DADOS CENTRAL ---
def get_central_db():
    if 'central_db' not in g:
        g.central_db = sqlite3.connect(config.DB_PATH_CENTRAL)
        g.central_db.row_factory = sqlite3.Row
    return g.central_db

@app.teardown_appcontext
def close_central_db(e=None):
    db = g.pop('central_db', None)
    if db is not None:
        db.close()


# --- MIDDLEWARE E DECORADORES ---
@app.before_request
def set_user_id_for_logging():
    """
    Antes de cada requisição, tenta extrair o user_id do token JWT
    e o armazena no objeto `g` para ser usado pelo logger.
    Não bloqueia a requisição se o token for inválido ou ausente.
    """
    g.user_id = None  # Usado pelo logger
    g.current_user_id = None # Usado pela lógica de autorização
    token = None
    if 'Authorization' in request.headers:
        try:
            token = request.headers['Authorization'].split(" ")[1]
            data = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
            g.user_id = data.get('user_id')
            g.current_user_id = g.user_id
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
            pass

def token_required(f):
    """
    Decorador que verifica se um token válido foi processado pelo
    middleware @app.before_request.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.current_user_id:
            return jsonify({"error": "Token de autenticação ausente ou inválido."}), 401
        return f(*args, **kwargs)
    return decorated

@app.after_request
def after_request_func(response):
    if config.ENABLE_REQUEST_LOGGING:
        log_request(response)
    return response


# --- LÓGICA DE MOTOR DE JOGO ---
def get_or_create_game_engine(session_name: str):
    if session_name in active_game_engines:
        return active_game_engines[session_name]

    db_path = config.DB_PATH_SQLITE_TEMPLATE.format(session_name=session_name)

    if not os.path.exists(db_path):
        logging.info(f"Arquivo de sessão '{session_name}.db' não encontrado. Criando novo banco de dados...")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_session_database(cursor)
            conn.commit()
            logging.info(f"Banco de dados para a sessão '{session_name}' criado com sucesso.")
        except Exception as e:
            logging.critical(f"ERRO CRÍTICO ao criar o banco de dados da sessão '{session_name}': {e}", exc_info=True)
            if os.path.exists(db_path):
                os.remove(db_path)
            raise
        finally:
            if conn:
                conn.close()

    logging.info(f"--- INICIANDO NOVA INSTÂNCIA DE JOGO PARA A SESSÃO: {session_name} ---")

    data_manager = SqliteManager(session_name)
    context_builder = ContextBuilder(data_manager, chromadb_manager_singleton, session_name)
    tool_processor = ToolProcessor(data_manager, chromadb_manager_singleton, neo4j_manager_singleton)
    game_engine = GameEngine(context_builder, tool_processor)
    active_game_engines[session_name] = game_engine

    return game_engine

def sanitize_session_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w-]', '', name)
    name = name.strip('_-')
    return name[:50] or "personagem_sem_nome"


# --- ENDPOINTS DA API ---

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "server_version": SERVER_VERSION,
        "minimum_client_version": MINIMUM_CLIENT_VERSION,
        "status": "online"
    })


# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/register', methods=['POST'])
def register():
    """Registra um novo usuário."""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    db = get_central_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    if cursor.fetchone():
        return jsonify({"error": "Este nome de usuário já existe."}), 409

    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (?, ?)", (username, password_hash))
        db.commit()
    except sqlite3.IntegrityError:
         return jsonify({"error": "Este nome de usuário já existe."}), 409
    except Exception as e:
        logging.error(f"Erro ao registrar usuário {username}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao registrar usuário."}), 500

    return jsonify({"message": f"Usuário '{username}' registrado com sucesso!"}), 201


@app.route('/login', methods=['POST'])
def login():
    """Autentica um usuário e retorna um token JWT."""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Nome de usuário e senha são obrigatórios."}), 400

    db = get_central_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, password_hash FROM usuarios WHERE username = ?", (username,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Credenciais inválidas."}), 401
    
    stored_hash_bytes = user['password_hash'].encode('utf-8')
    password_bytes = password.encode('utf-8')

    if not bcrypt.checkpw(password_bytes, stored_hash_bytes):
        return jsonify({"error": "Credenciais inválidas."}), 401

    user_id = user['id']
    jwt_payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }
    jwt_token = jwt.encode(jwt_payload, config.JWT_SECRET_KEY, algorithm="HS256")

    return jsonify({"message": "Login bem-sucedido!", "token": jwt_token})


# --- ROTAS DE SESSÃO (AUTENTICADAS) ---
@app.route('/sessions', methods=['GET'])
@token_required
def get_sessions():
    """Lista todas as sagas do usuário autenticado."""
    try:
        db = get_central_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT session_name, player_name, world_concept FROM sagas WHERE usuario_id = ?",
            (g.current_user_id,)
        )
        sagas = [dict(row) for row in cursor.fetchall()]
        return jsonify(sagas)
    except Exception as e:
        logging.error(f"Erro ao listar sagas para o usuário {g.current_user_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao listar sagas."}), 500

@app.route('/sessions/create', methods=['POST'])
@token_required
def create_session():
    data = request.json
    char_name = data.get('character_name')
    world_concept = data.get('world_concept')

    if not char_name or not world_concept:
        return jsonify({"error": "Nome do personagem e conceito do mundo são obrigatórios."}), 400

    base_name = sanitize_session_name(char_name)
    random_suffix = uuid.uuid4().hex[:6]
    session_name = f"{base_name}_{random_suffix}"
    player_id_canonico = f"pj_{session_name}"

    try:
        game_engine = get_or_create_game_engine(session_name)

        db = get_central_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO sagas (usuario_id, session_name, player_name, world_concept) VALUES (?, ?, ?, ?)",
            (g.current_user_id, session_name, char_name, world_concept)
        )
        db.commit()
        logging.info(f"Saga '{session_name}' registrada para o usuário ID {g.current_user_id}.")

        initial_action = (
            f"META-INSTRUÇÃO DE CONSTRUÇÃO DE MUNDO: Crie o universo para uma nova saga. "
            f"O personagem principal chama-se '{char_name}' e deve ter o id_canonico '{player_id_canonico}'. "
            f"O conceito do mundo é: '{world_concept}'. "
            f"Crie um local inicial apropriado, o personagem jogador, e coloque-o no local. "
            f"Depois, gere a narrativa de abertura."
        )

        narrative = game_engine.execute_turn(initial_action)

        return jsonify({
            "message": "Sessão criada com sucesso!",
            "session_name": session_name,
            "initial_narrative": narrative
        }), 201

    except Exception as e:
        logging.error(f"Erro ao criar sessão para o usuário {g.current_user_id}: {e}", exc_info=True)
        db = get_central_db()
        db.execute("DELETE FROM sagas WHERE session_name = ?", (session_name,))
        db.commit()
        return jsonify({"error": "Erro ao criar sessão."}), 500

# --- ROTA DE EXCLUSÃO ATUALIZADA ---
@app.route('/sessions/<session_name>', methods=['DELETE'])
@token_required
def delete_session_route(session_name: str):
    """Apaga uma saga e todos os seus dados associados."""
    if not check_session_ownership(session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403

    try:
        logging.warning(f"Iniciando exclusão da saga '{session_name}' para o usuário {g.current_user_id}.")

        # --- ORDEM DE OPERAÇÕES CORRIGIDA ---

        # 1. Remover a instância do motor de jogo da memória PRIMEIRO.
        # Isto liberta qualquer bloqueio no ficheiro da base de dados.
        if session_name in active_game_engines:
            del active_game_engines[session_name]
            logging.info(f"Instância do motor de jogo para '{session_name}' removida da memória.")

        # 2. Apagar dados do Neo4j
        neo4j_manager_singleton.delete_session_data(session_name)

        # 3. Apagar coleção do ChromaDB
        chromadb_manager_singleton.delete_collection(session_name)

        # 4. Apagar o ficheiro da base de dados SQLite (agora seguro)
        temp_sqlite_manager = SqliteManager(session_name, supress_success_message=True)
        temp_sqlite_manager.delete_database_file()

        # 5. Apagar a entrada da saga na base de dados central
        db = get_central_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM sagas WHERE session_name = ? AND usuario_id = ?", (session_name, g.current_user_id))
        db.commit()
        
        logging.info(f"Saga '{session_name}' apagada com sucesso.")
        return jsonify({"message": f"Saga '{session_name}' apagada com sucesso."}), 200

    except Exception as e:
        logging.error(f"Erro crítico ao apagar a saga '{session_name}': {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado ao apagar a saga."}), 500


def check_session_ownership(session_name):
    """Verifica se a saga pertence ao usuário autenticado."""
    db = get_central_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id FROM sagas WHERE session_name = ? AND usuario_id = ?",
        (session_name, g.current_user_id)
    )
    return cursor.fetchone() is not None


# --- ROTAS DE JOGO (AUTENTICADAS) ---
@app.route('/sessions/<session_name>/tools', methods=['GET'])
@token_required
def get_contextual_tools_route(session_name: str):
    if not check_session_ownership(session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403
    game_engine = get_or_create_game_engine(session_name)
    tools = game_engine.generate_contextual_tools()
    return jsonify(tools)

@app.route('/sessions/<session_name>/execute_turn', methods=['POST'])
@token_required
def execute_turn_route(session_name: str):
    if not check_session_ownership(session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403
    game_engine = get_or_create_game_engine(session_name)
    player_action = request.json['player_action']
    narrative = game_engine.execute_turn(player_action)
    return jsonify({"narrative": narrative})

@app.route('/sessions/<session_name>/state', methods=['GET'])
@token_required
def get_game_state_route(session_name: str):
    if not check_session_ownership(session_name):
        return jsonify({"error": "Acesso não autorizado a esta saga."}), 403
    data_manager = SqliteManager(session_name, supress_success_message=True)
    player_status = data_manager.get_player_full_status()
    if player_status:
        return jsonify(player_status)
    return jsonify({'base': {'nome': 'Jogador não encontrado na sessão.'}}), 404


if __name__ == '__main__':
    if not os.path.exists(config.DB_PATH_CENTRAL):
        logging.warning("Banco de dados central não encontrado. Criando agora...")
        os.system(f'python "{os.path.join("scripts", "build_world.py")}" --target central')

    logging.info("===========================================")
    logging.info(f"=    SERVIDOR DE SAGAS (v{SERVER_VERSION})    =")
    logging.info(f"Versão mínima do cliente: {MINIMUM_CLIENT_VERSION}")
    logging.info("===========================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
