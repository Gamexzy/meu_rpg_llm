import os
import sys
import asyncio
import traceback
import re

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

# --- CONFIGURAÇÃO DE VERSÃO ---
SERVER_VERSION = "1.2.0"
MINIMUM_CLIENT_VERSION = "1.1"

# --- GERENCIADOR DE SESSÕES ---
# Armazena as instâncias do motor de jogo para cada sessão ativa
active_game_engines = {}

app = Flask(__name__)
CORS(app)

def get_or_create_game_engine(session_name: str):
    """
    Obtém uma instância existente do GameEngine para uma sessão ou cria uma nova.
    """
    if session_name in active_game_engines:
        return active_game_engines[session_name]

    print(f"\n\033[1;34m--- INICIANDO NOVA INSTÂNCIA DE JOGO PARA A SESSÃO: {session_name} ---\033[0m")
    
    # Verifica se o arquivo .db da sessão existe
    db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Arquivo de sessão '{session_name}.db' não encontrado.")

    data_manager = DataManager(session_name)
    chromadb_manager = ChromaDBManager(session_name) # Adaptação para coleções por sessão
    neo4j_manager = Neo4jManager() # Neo4j pode ser compartilhado ou adaptado se necessário
    context_builder = ContextBuilder(data_manager, chromadb_manager)
    tool_processor = ToolProcessor(data_manager, chromadb_manager, neo4j_manager)
    
    game_engine = GameEngine(context_builder, tool_processor)
    active_game_engines[session_name] = game_engine
    
    print(f"\033[1;32m--- INSTÂNCIA PARA '{session_name}' PRONTA ---\033[0m")
    return game_engine

def sanitize_session_name(name: str) -> str:
    """Limpa e formata um nome para ser usado como nome de arquivo de sessão."""
    name = name.lower()
    name = re.sub(r'\s+', '_', name) # Substitui espaços por underscores
    name = re.sub(r'[^\w-]', '', name) # Remove caracteres não alfanuméricos (exceto underscore e hífen)
    return name[:50] # Limita o comprimento

# --- ENDPOINTS DA API ---

@app.route('/status', methods=['GET'])
def get_status():
    """Endpoint para o cliente verificar a versão e o status do servidor."""
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
        for filename in os.listdir(config.PROD_DATA_DIR):
            if filename.endswith(".db"):
                session_name = filename[:-3]
                try:
                    # Tenta ler o nome do personagem para exibir na lista
                    temp_dm = DataManager(session_name, supress_success_message=True)
                    player_info = temp_dm.get_all_entities_from_table('jogador')
                    player_name = player_info[0]['nome'] if player_info else "Nova Aventura"
                    sessions.append({"session_name": session_name, "player_name": player_name})
                except Exception as e:
                    print(f"Aviso: Não foi possível ler a sessão '{session_name}': {e}")
                    sessions.append({"session_name": session_name, "player_name": "Sessão Corrompida?"})
        return jsonify(sessions)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro ao listar sessões: {e}"}), 500

@app.route('/sessions/create', methods=['POST'])
def create_session():
    """Cria uma nova sessão de jogo."""
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
        # Cria o banco de dados e seu esquema
        print(f"Criando novo banco de dados em: {db_path}")
        build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py')
        # Passa o caminho do novo DB para o script de build
        os.system(f'python "{build_script_path}" --db_path "{db_path}"')
        
        # Inicia o motor do jogo para a nova sessão
        game_engine = get_or_create_game_engine(session_name)
        
        # Monta a ação inicial para a IA
        initial_action = f"Crie um personagem chamado {char_name}. O conceito do mundo é: {world_concept}"
        
        # Executa o primeiro turno para gerar a narrativa inicial
        narrative = asyncio.run(game_engine.execute_turn(initial_action))
        
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
    """Executa um turno para uma sessão específica."""
    try:
        game_engine = get_or_create_game_engine(session_name)
        player_action = request.json['player_action']
        narrative = asyncio.run(game_engine.execute_turn(player_action))
        return jsonify({"narrative": narrative})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<session_name>/state', methods=['GET'])
def get_game_state_route(session_name: str):
    """Busca o estado do jogo para uma sessão específica."""
    try:
        # Usa um DataManager temporário apenas para a leitura, sem iniciar o motor completo
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
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print("\n\033[1;34m===========================================\033[0m")
    print(f"\033[1;34m=    SERVIDOR DE SAGAS (v{SERVER_VERSION})    =\033[0m")
    print(f"\033[1;33mVersão mínima do cliente: {MINIMUM_CLIENT_VERSION}\033[0m")
    print("\033[1;34m===========================================\033[0m\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
