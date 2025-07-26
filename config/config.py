import os
from dotenv import load_dotenv

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

# --- Configuração de Caminhos Globais ---
# A BASE_DIR aponta para a raiz do projeto (meu_rpg_llm)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENABLE_REQUEST_LOGGING = True

# Caminho para o diretório onde os dados em produção serão armazenados
PROD_DATA_DIR = os.path.join(BASE_DIR, 'dados_em_producao')

# Caminho para o arquivo de banco de dados SQLite (Pilar B)
DB_PATH_SQLITE = os.path.join(PROD_DATA_DIR, 'estado.db')

# Caminho para o diretório de persistência do ChromaDB (Pilar A)
CHROMA_PATH = os.path.join(PROD_DATA_DIR, 'chroma_db')

# --- Configuração do Neo4j (Pilar C) ---
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password") # Altere se sua senha for diferente

# --- Configuração da API Gemini (LLM e Embedding) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Modelo de Geração de Conteúdo (LLM principal e Agentes)
GENERATIVE_MODEL = "gemini-2.0-flash"
AGENT_GENERATIVE_MODEL = "gemini-2.0-flash-lite"

# Modelo de Embedding
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Configurações dos Agentes ---
# Número máximo de "tarefas" ou chamadas de função que um agente pode
# realizar em um único turno. Isto controla o processamento em lote.
MAX_AGENT_TOOL_CALLS = 5

# Versão do Arquivo de Configuração
CONFIG_VERSION = "1.3.0" # Adicionada configuração de processamento em lote para agentes.

# Exemplo de como você pode imprimir as configurações para depuração
def print_config_summary():
    print("\n--- Sumário das Configurações ---")
    print(f"Versão da Configuração: {CONFIG_VERSION}")
    print(f"Diretório Base do Projeto: {BASE_DIR}")
    print(f"Diretório de Dados de Produção: {PROD_DATA_DIR}")
    print(f"Caminho do SQLite DB: {DB_PATH_SQLITE}")
    print(f"Caminho do ChromaDB: {CHROMA_PATH}")
    print(f"Neo4j URI: {NEO4J_URI}")
    print(f"Neo4j User: {NEO4J_USER}")
    print(f"Neo4j Password: {'********' if NEO4J_PASSWORD else 'N/A (Vazio)'}")
    print(f"GEMINI_API_KEY: {'********' if GEMINI_API_KEY else 'N/A (Vazio/Não Definida)'}")
    print(f"Modelo Generativo (Principal): {GENERATIVE_MODEL}")
    print(f"Modelo Generativo (Agentes): {AGENT_GENERATIVE_MODEL}")
    print(f"Modelo de Embedding: {EMBEDDING_MODEL}")
    print(f"Máximo de Chamadas de Ferramenta por Agente: {MAX_AGENT_TOOL_CALLS}")
    print("---------------------------------\n")

if __name__ == "__main__":
    print_config_summary()
