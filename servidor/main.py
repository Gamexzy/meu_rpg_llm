import os
import sys
import asyncio
import aiohttp
import time

# Adiciona o diretório raiz do projeto ao sys.path para tornar todos os módulos acessíveis
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from config import config
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager
from servidor.engine.context_builder import ContextBuilder
from servidor.engine.tool_processor import ToolProcessor
from servidor.engine.game_engine import GameEngine
from servidor.llm.client import LLMClient

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
        # Temporariamente cria um DataManager para verificar o estado do jogo
        temp_data_manager = DataManager(supress_success_message=True)
        is_empty = not temp_data_manager.get_all_entities_from_table('jogador')
        del temp_data_manager
        return is_empty
    except Exception as e:
        print(f"Erro ao verificar o estado do jogo: {e}", file=sys.stderr)
        return True

async def main():
    """Função principal para inicializar e executar o jogo."""
    
    initialize_db_schema()
    new_game = is_new_game()

    if new_game:
        print("--- Nenhum jogo salvo detectado. Preparando para um novo universo... ---")
    else:
        print("--- Jogo salvo encontrado. Carregando universo... ---")
    
    try:
        # --- Tela de Carregamento Integrada ---
        print("\n\033[1;34m===========================================\033[0m")
        print("\033[1;34m=    INICIANDO SIMULAÇÃO DE UNIVERSO    =\033[0m")
        print("\033[1;34m===========================================\033[0m\n")

        # Passo 1: Conectar ao Pilar B (SQLite)
        sys.stdout.write("  \033[1;36m[ ]\033[0m Conectando ao Pilar B (SQLite)...\n")
        sys.stdout.flush()
        time.sleep(0.2)
        data_manager = DataManager() # A inicialização imprimirá seus próprios logs aqui
        time.sleep(0.3)
        sys.stdout.write("      \033[1;32m↳ Conexão estabelecida com sucesso.\033[0m\n\n")

        # Passo 2: Conectar ao Pilar A (ChromaDB)
        sys.stdout.write("  \033[1;36m[ ]\033[0m Conectando ao Pilar A (ChromaDB)...\n")
        sys.stdout.flush()
        time.sleep(0.2)
        chromadb_manager = ChromaDBManager() # A inicialização imprimirá seus próprios logs aqui
        time.sleep(0.5)
        sys.stdout.write("      \033[1;32m↳ Conexão estabelecida com sucesso.\033[0m\n\n")

        # Passo 3: Conectar ao Pilar C (Neo4j)
        sys.stdout.write("  \033[1;36m[ ]\033[0m Conectando ao Pilar C (Neo4j)...\n")
        sys.stdout.flush()
        time.sleep(0.2)
        neo4j_manager = Neo4jManager() # A inicialização imprimirá seus próprios logs aqui
        time.sleep(0.4)
        sys.stdout.write("      \033[1;32m↳ Conexão estabelecida com sucesso.\033[0m\n\n")

        # Passo 4: Inicializar Motores e Agentes de IA
        sys.stdout.write("  \033[1;36m[ ]\033[0m Acordando Agentes e Motores de IA...\n")
        sys.stdout.flush()
        time.sleep(0.2)
        context_builder = ContextBuilder(data_manager, chromadb_manager)
        tool_processor = ToolProcessor(data_manager, chromadb_manager, neo4j_manager)
        time.sleep(0.8)
        sys.stdout.write("      \033[1;32m↳ Sistemas de IA operacionais.\033[0m\n")

        print("\n\033[1;32mSISTEMA PRONTO. BEM-VINDO AO UNIVERSO!\033[0m")
        print("\033[1;34m===========================================\033[0m\n")

        async with aiohttp.ClientSession() as session:
            llm_client = LLMClient(session, tool_processor)
            game_engine = GameEngine(context_builder, llm_client)
            
            if new_game:
                print("--- O MUNDO É UMA FOLHA EM BRANCO. ---")
                print("    O Mestre de Jogo irá criar o seu personagem e o local inicial.")
                print("    Para começar, apenas pressione Enter ou descreva o que você gostaria de ser.")
            else:
                initial_context = await context_builder.get_current_context()
                player_name = initial_context.get('jogador', {}).get('base', {}).get('nome', 'Aventureiro')
                print(f"\033[1;32m--- Bem-vindo de volta, {player_name}. Continue sua jornada. ---\033[0m")

            while True:
                player_action = await asyncio.to_thread(input, "\n\033[1;33mSua ação: \033[0m")
                if player_action.lower() in ['sair', 'exit', 'quit']:
                    break
                await game_engine.execute_turn(player_action)

    except Exception as e:
        print("\n\n\033[1;31mERRO CRÍTICO DURANTE A EXECUÇÃO:\033[0m", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nEncerrando a simulação...")

if __name__ == '__main__':
    # Garante que o loop de eventos correto seja usado no Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
