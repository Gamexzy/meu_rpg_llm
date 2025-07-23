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

# --- Componentes Globais do Jogo ---
# Serão inicializados uma vez quando o servidor iniciar.
game_engine = None
app = Flask(__name__)
CORS(app)  # Permite requisições de outras origens (como o app Android)

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

def is_new_game():
    """Verifica se um jogo está em andamento."""
    try:
        temp_data_manager = DataManager(supress_success_message=True)
        is_empty = not temp_data_manager.get_all_entities_from_table('jogador')
        del temp_data_manager
        return is_empty
    except Exception as e:
        print(f"Erro ao verificar o estado do jogo: {e}", file=sys.stderr)
        return True

def initialize_game():
    """Inicializa todos os componentes do motor do jogo."""
    global game_engine
    
    initialize_db_schema()
    new_game = is_new_game()

    if new_game:
        print("--- Nenhum jogo salvo detectado. Preparando para um novo universo... ---")
    else:
        print("--- Jogo salvo encontrado. Carregando universo... ---")

    print("\n\033[1;34m===========================================\033[0m")
    print("\033[1;34m=    INICIANDO SIMULAÇÃO DE UNIVERSO    =\033[0m")
    print("\033[1;34m===========================================\033[0m\n")

    data_manager = DataManager()
    chromadb_manager = ChromaDBManager()
    neo4j_manager = Neo4jManager()
    context_builder = ContextBuilder(data_manager, chromadb_manager)
    tool_processor = ToolProcessor(data_manager, chromadb_manager, neo4j_manager)
    
    # O aiohttp.ClientSession deve ser criado dentro de um contexto async
    # mas para o Flask, vamos criá-lo aqui e gerenciá-lo manualmente.
    # Uma solução mais robusta usaria um servidor ASGI como Uvicorn ou Hypercorn.
    session = aiohttp.ClientSession()
    llm_client = LLMClient(session, tool_processor)
    game_engine = GameEngine(context_builder, llm_client)

    print("\n\033[1;32mSISTEMA PRONTO. AGUARDANDO CONEXÕES DO CLIENTE...\033[0m")
    print("\033[1;34m===========================================\033[0m\n")


@app.route('/execute_turn', methods=['POST'])
def execute_turn_route():
    """Endpoint para receber a ação do jogador e retornar a narrativa."""
    if not request.json or 'player_action' not in request.json:
        return jsonify({"error": "Ação do jogador ('player_action') não encontrada no corpo da requisição"}), 400

    player_action = request.json['player_action']
    
    if not game_engine:
         return jsonify({"error": "O motor do jogo não foi inicializado."}), 500

    try:
        # Executa a lógica assíncrona do jogo em um novo loop de eventos
        narrative = asyncio.run(game_engine.execute_turn(player_action))
        return jsonify({"narrative": narrative})
    except Exception as e:
        print(f"\n\033[1;31mERRO CRÍTICO DURANTE A EXECUÇÃO DO TURNO:\033[0m", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    initialize_game()
    # Executa o servidor Flask, acessível na sua rede local
    app.run(host='0.0.0.0', port=5000, debug=True)

