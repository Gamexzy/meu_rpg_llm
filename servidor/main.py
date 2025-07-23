import os
import sys
import asyncio
import aiohttp
import time

# Adiciona o diretório raiz do projeto ao sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import config
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager
from servidor.engine.context_builder import ContextBuilder
from servidor.engine.tool_processor import ToolProcessor
from servidor.engine.game_engine import GameEngine
from servidor.llm.client import LLMClient

# --- CONFIGURAÇÃO DE VERSÃO ---
# Versão 1.1.0 - Adicionado endpoint de status para verificação de versão do cliente.
SERVER_VERSION = "1.1.0"
MINIMUM_CLIENT_VERSION = "1.2" # O app precisa ter no mínimo esta versão (versionName)

# --- Componentes Globais do Jogo ---
game_engine = None
data_manager = None
app = Flask(__name__)
CORS(app)

def initialize_db_schema():
    """Garante que o esquema do banco de dados exista."""
    if not os.path.exists(config.DB_PATH_SQLITE):
        print("--- Arquivo de banco de dados não encontrado. Criando esquema inicial... ---")
        build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py')
        if os.path.exists(build_script_path):
            os.system(f'python "{build_script_path}"')
        else:
            print(f"ERRO CRÍTICO: Script 'build_world.py' não encontrado.", file=sys.stderr)
            sys.exit(1)

def initialize_game():
    """Inicializa todos os componentes síncronos do motor do jogo."""
    global game_engine, data_manager
    
    initialize_db_schema()

    print("\n\033[1;34m===========================================\033[0m")
    print(f"\033[1;34m=    INICIANDO SIMULAÇÃO (Servidor v{SERVER_VERSION})    =\033[0m")
    print("\033[1;34m===========================================\033[0m\n")

    data_manager = DataManager()
    chromadb_manager = ChromaDBManager()
    neo4j_manager = Neo4jManager()
    context_builder = ContextBuilder(data_manager, chromadb_manager)
    tool_processor = ToolProcessor(data_manager, chromadb_manager, neo4j_manager)
    
    game_engine = GameEngine(context_builder, tool_processor)

    print("\n\033[1;32mSISTEMA PRONTO. AGUARDANDO CONEXÕES DO CLIENTE...\033[0m")
    print(f"\033[1;33mVersão mínima do cliente exigida: {MINIMUM_CLIENT_VERSION}\033[0m")
    print("\033[1;34m===========================================\033[0m\n")

# --- NOVO ENDPOINT DE STATUS ---
@app.route('/status', methods=['GET'])
def get_status():
    """Endpoint para o cliente verificar a versão e o status do servidor."""
    return jsonify({
        "server_version": SERVER_VERSION,
        "minimum_client_version": MINIMUM_CLIENT_VERSION,
        "status": "online"
    })

@app.route('/execute_turn', methods=['POST'])
def execute_turn_route():
    """Endpoint para receber a ação do jogador e retornar a narrativa."""
    # (O conteúdo desta função permanece o mesmo)
    if not request.json or 'player_action' not in request.json:
        return jsonify({"error": "Ação do jogador ('player_action') não encontrada no corpo da requisição"}), 400
    player_action = request.json['player_action']
    if not game_engine:
         return jsonify({"error": "O motor do jogo não foi inicializado."}), 500
    try:
        narrative = asyncio.run(game_engine.execute_turn(player_action))
        return jsonify({"narrative": narrative})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/get_game_state', methods=['GET'])
def get_game_state_route():
    """Endpoint para o app buscar o estado completo do jogador e do mundo."""
    # (O conteúdo desta função permanece o mesmo)
    if not data_manager:
        return jsonify({"error": "O DataManager não foi inicializado."}), 500
    try:
        player_status = data_manager.get_player_full_status()
        if player_status:
            return jsonify(player_status)
        else:
            return jsonify({
                'base': {'nome': 'Aguardando Criação'},
                'vitals': {}, 'habilidades': [], 'conhecimentos': [], 'posses': []
            }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    initialize_game()
    app.run(host='0.0.0.0', port=5000, debug=True)
