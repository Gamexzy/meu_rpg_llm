# servidor/main.py
import os
import sys
import traceback
import re
import sqlite3
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

# --- CONFIGURAÇÃO DE VERSÃO ---
SERVER_VERSION = "1.3.0" # Atualizado para refletir as mudanças síncronas
MINIMUM_CLIENT_VERSION = "1.1"

# --- GERENCIADOR DE SESSÕES ---
active_game_engines = {}

app = Flask(__name__)
CORS(app)

def get_or_create_game_engine(session_name: str):
    """
    Obtém uma instância existente do GameEngine ou cria uma nova,
    incluindo a criação do banco de dados se ele não existir.
    """
    if session_name in active_game_engines:
        return active_game_engines[session_name]

    db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
    
    if not os.path.exists(db_path):
        print(f"Arquivo de sessão '{session_name}.db' não encontrado. Criando novo banco de dados...")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_database(cursor)
            conn.commit()
            print(f"Banco de dados para a sessão '{session_name}' criado com sucesso em: {db_path}")
        except Exception as e:
            print(f"ERRO CRÍTICO ao criar o banco de dados para a sessão '{session_name}': {e}")
            if os.path.exists(db_path): os.remove(db_path)
            raise
        finally:
            if conn: conn.close()

    print(f"\n\033[1;34m--- INICIANDO NOVA INSTÂNCIA DE JOGO PARA A SESSÃO: {session_name} ---\033[0m")
    
    data_manager = DataManager(session_name)
    chromadb_manager = ChromaDBManager(session_name)
    neo4j_manager = Neo4jManager()
    context_builder = ContextBuilder(data_manager, chromadb_manager)
    tool_processor = ToolProcessor(data_manager, chromadb_manager, neo4j_manager)
    
    game_engine = GameEngine(context_builder, tool_processor)
    active_game_engines[session_name] = game_engine
    
    return game_engine

def sanitize_session_name(name: str) -> str:
    """Limpa e formata um nome para ser usado como nome de arquivo de sessão e coleção."""
    name = name.lower().strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w-]', '', name)
    name = name.strip('_-')
    return name[:50] or "sessao_sem_nome"

# --- ENDPOINTS DA API ---

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "server_version": SERVER_VERSION,
        "minimum_client_version": MINIMUM_CLIENT_VERSION,
        "status": "online"
    })

@app.route('/sessions', methods=['GET'])
def get_sessions():
    sessions = []
    try:
        os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
        for filename in os.listdir(config.PROD_DATA_DIR):
            if filename.endswith(".db"):
                session_name = filename[:-3]
                try:
                    temp_dm = DataManager(session_name, supress_success_message=True)
                    player_info = temp_dm.get_all_entities_from_table('jogador')
                    player_name = player_info[0]['nome'] if player_info else "Nova Aventura"
                    sessions.append({"session_name": session_name, "player_name": player_name})
                except Exception:
                    sessions.append({"session_name": session_name, "player_name": "Sessão Corrompida?"})
        return jsonify(sessions)
    except Exception as e:
        return jsonify({"error": f"Erro ao listar sessões: {e}"}), 500

@app.route('/sessions/create', methods=['POST'])
def create_session():
    data = request.json
    char_name = data.get('character_name')
    world_concept = data.get('world_concept')

    if not char_name or not world_concept:
        return jsonify({"error": "Nome do personagem e conceito do mundo são obrigatórios."}), 400

    session_name = sanitize_session_name(char_name)
    db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")

    if os.path.exists(db_path):
        return jsonify({"error": f"Uma sessão com o nome '{session_name}' já existe."}), 409

    try:
        game_engine = get_or_create_game_engine(session_name)
        initial_action = f"Crie um personagem chamado {char_name}. O conceito do mundo é: {world_concept}"
        
        # Chamada síncrona
        narrative = game_engine.execute_turn(initial_action)
        
        return jsonify({
            "message": "Sessão criada com sucesso!",
            "session_name": session_name,
            "initial_narrative": narrative
        }), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro ao criar sessão: {e}"}), 500

@app.route('/sessions/<session_name>/execute_turn', methods=['POST'])
def execute_turn_route(session_name: str):
    try:
        game_engine = get_or_create_game_engine(session_name)
        player_action = request.json['player_action']
        
        # Chamada síncrona
        narrative = game_engine.execute_turn(player_action)
        return jsonify({"narrative": narrative})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<session_name>/state', methods=['GET'])
def get_game_state_route(session_name: str):
    try:
        data_manager = DataManager(session_name, supress_success_message=True)
        player_status = data_manager.get_player_full_status()
        if player_status:
            return jsonify(player_status)
        else:
            return jsonify({'base': {'nome': 'Jogador não encontrado'}}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n\033[1;34m===========================================\033[0m")
    print(f"\033[1;34m=    SERVIDOR DE SAGAS (v{SERVER_VERSION})    =\033[0m")
    print(f"\033[1;33mVersão mínima do cliente: {MINIMUM_CLIENT_VERSION}\033[0m")
    print("\033[1;34m===========================================\033[0m\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
