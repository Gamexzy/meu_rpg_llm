# servidor/main.py
import logging
import os
import sys
import traceback
import re
import sqlite3
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

# Adiciona o diretório raiz do projeto ao sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from config import config
from scripts.build_world import setup_database
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager
from servidor.engine.context_builder import ContextBuilder
from servidor.engine.tool_processor import ToolProcessor
from servidor.engine.game_engine import GameEngine
from servidor.utils.request_logger import log_request
from servidor.utils.logging_config import setup_logging

# --- INICIALIZAÇÃO DO LOGGING ---
setup_logging()

# --- CONFIGURAÇÃO DE VERSÃO ---
SERVER_VERSION = "1.7.0" # Adicionado endpoint de ferramentas
MINIMUM_CLIENT_VERSION = "1.5"

# --- GERENCIADOR DE SESSÕES ---
active_game_engines = {}

app = Flask(__name__)
CORS(app)

# --- INICIALIZAÇÃO DOS GESTORES GLOBAIS (SINGLETON) ---
chromadb_manager_singleton = ChromaDBManager()
neo4j_manager_singleton = Neo4jManager()


def get_or_create_game_engine(session_name: str):
    """
    Obtém uma instância existente do GameEngine ou cria uma nova,
    incluindo a criação do banco de dados se ele não existir.
    """
    if session_name in active_game_engines:
        return active_game_engines[session_name]

    db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
    
    if not os.path.exists(db_path):
        logging.info(f"Arquivo de sessão '{session_name}.db' não encontrado. Criando novo banco de dados...")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_database(cursor)
            conn.commit()
            logging.info(f"Banco de dados para a sessão '{session_name}' criado com sucesso em: {db_path}")
        except Exception as e:
            logging.critical(f"ERRO CRÍTICO ao criar o banco de dados para a sessão '{session_name}': {e}", exc_info=True)
            if os.path.exists(db_path): os.remove(db_path)
            raise
        finally:
            if conn: conn.close()

    logging.info(f"--- INICIANDO NOVA INSTÂNCIA DE JOGO PARA A SESSÃO: {session_name} ---")
    
    data_manager = DataManager(session_name)
    context_builder = ContextBuilder(data_manager, chromadb_manager_singleton, session_name)
    tool_processor = ToolProcessor(data_manager, chromadb_manager_singleton, neo4j_manager_singleton)
    game_engine = GameEngine(context_builder, tool_processor)
    active_game_engines[session_name] = game_engine
    
    return game_engine

def sanitize_session_name(name: str) -> str:
    """Limpa e formata um nome para ser usado como nome de arquivo de sessão e coleção."""
    name = name.lower().strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w-]', '', name)
    name = name.strip('_-')
    return name[:50] or "personagem_sem_nome"

# --- MIDDLEWARE E ENDPOINTS DA API ---

@app.after_request
def after_request_func(response):
    if config.ENABLE_REQUEST_LOGGING:
        log_request(response)
    return response

@app.route('/status', methods=['GET'])
def get_status():
    """Endpoint para verificar a saúde e a versão do servidor."""
    return jsonify({
        "server_version": SERVER_VERSION,
        "minimum_client_version": MINIMUM_CLIENT_VERSION,
        "status": "online"
    })

@app.route('/sessions', methods=['GET'])
def get_sessions():
    """Lista todas as sessões de jogo salvas."""
    sessions = []
    try:
        os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
        for filename in os.listdir(config.PROD_DATA_DIR):
            if filename.endswith(".db"):
                session_name = filename[:-3]
                try:
                    temp_dm = DataManager(session_name, supress_success_message=True)
                    player_info_list = temp_dm.get_all_entities_from_table('jogador')
                    
                    if player_info_list:
                        player_info = player_info_list[0]
                        player_name = player_info.get('nome', "Nome Desconhecido")
                        
                        sagas_info_list = temp_dm.get_all_entities_from_table('sagas')
                        world_concept = "Uma aventura misteriosa..."
                        if sagas_info_list:
                            world_concept = sagas_info_list[0].get('world_concept', world_concept)

                        sessions.append({
                            "session_name": session_name,
                            "player_name": player_name,
                            "world_concept": world_concept
                        })
                    else:
                        sessions.append({
                            "session_name": session_name,
                            "player_name": "Nova Aventura",
                            "world_concept": "Ainda por definir..."
                        })
                except Exception as e:
                    logging.error(f"Erro ao processar a sessão '{session_name}': {e}")
                    sessions.append({
                        "session_name": session_name,
                        "player_name": "Sessão Corrompida?",
                        "world_concept": "Não foi possível carregar os detalhes."
                    })
        return jsonify(sessions)
    except Exception as e:
        logging.error(f"Erro ao listar sessões: {e}", exc_info=True)
        return jsonify({"error": f"Erro ao listar sessões: {e}"}), 500


@app.route('/sessions/create', methods=['POST'])
def create_session():
    """Cria uma nova sessão de jogo, personagem e mundo inicial."""
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
        
        initial_action = (
            f"META-INSTRUÇÃO DE CONSTRUÇÃO DE MUNDO: Crie o universo para uma nova saga. "
            f"O personagem principal chama-se '{char_name}' e deve ter o id_canonico '{player_id_canonico}'. "
            f"O conceito do mundo é: '{world_concept}'. "
            f"Por favor, crie um local inicial apropriado, crie o personagem jogador com este conceito em mente, "
            f"e coloque o jogador no local. "
            f"Depois, gere a narrativa de abertura para apresentar o personagem e o cenário ao jogador."
        )
        
        narrative = game_engine.execute_turn(initial_action)
        
        return jsonify({
            "message": "Sessão criada com sucesso!",
            "session_name": session_name,
            "initial_narrative": narrative
        }), 201

    except Exception as e:
        logging.error(f"Erro ao criar sessão: {e}", exc_info=True)
        return jsonify({"error": f"Erro ao criar sessão: {e}"}), 500

# --- CORREÇÃO: Adicionada a rota /tools ---
@app.route('/sessions/<session_name>/tools', methods=['GET'])
def get_contextual_tools_route(session_name: str):
    """Gera e retorna uma lista de ferramentas contextuais para a sessão."""
    try:
        game_engine = get_or_create_game_engine(session_name)
        tools = game_engine.generate_contextual_tools()
        return jsonify(tools)
    except Exception as e:
        logging.error(f"Erro ao gerar ferramentas para a sessão '{session_name}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<session_name>/execute_turn', methods=['POST'])
def execute_turn_route(session_name: str):
    """Executa um turno de jogo para uma sessão específica."""
    try:
        game_engine = get_or_create_game_engine(session_name)
        player_action = request.json['player_action']
        
        narrative = game_engine.execute_turn(player_action)
        return jsonify({"narrative": narrative})
    except Exception as e:
        logging.error(f"Erro no turno da sessão '{session_name}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<session_name>/state', methods=['GET'])
def get_game_state_route(session_name: str):
    """Obtém o estado completo do jogador para uma sessão."""
    try:
        data_manager = DataManager(session_name, supress_success_message=True)
        player_status = data_manager.get_player_full_status()
        if player_status:
            return jsonify(player_status)
        else:
            return jsonify({'base': {'nome': 'Jogador não encontrado na sessão.'}}), 404
    except Exception as e:
        logging.error(f"Erro ao obter estado da sessão '{session_name}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logging.info("===========================================")
    logging.info(f"=    SERVIDOR DE SAGAS (v{SERVER_VERSION})    =")
    logging.info(f"Versão mínima do cliente: {MINIMUM_CLIENT_VERSION}")
    logging.info("===========================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
