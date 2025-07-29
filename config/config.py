# config/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

# --- Configuração de Caminhos Globais ---
# A BASE_DIR aponta para a raiz do projeto (meu_rpg_llm)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENABLE_REQUEST_LOGGING = True

# Caminho para o diretório onde os dados em produção serão armazenados
PROD_DATA_DIR = os.path.join(BASE_DIR, 'dados_em_producao')

# --- ATUALIZAÇÃO: Caminhos dos Bancos de Dados ---
# Caminho para o banco de dados central de usuários e sagas (Pilar de Contas)
DB_PATH_CENTRAL = os.path.join(PROD_DATA_DIR, 'central.db')

# O caminho do SQLite agora é um template para os DBs de sessão
DB_PATH_SQLITE_TEMPLATE = os.path.join(PROD_DATA_DIR, '{session_name}.db')


# Caminho para o diretório de persistência do ChromaDB (Pilar A)
CHROMA_PATH = os.path.join(PROD_DATA_DIR, 'chroma_db')

# --- Configuração do Neo4j (Pilar C) ---
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password") # Altere se sua senha for diferente

# --- Configuração da API Gemini (LLM e Embedding) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --- ATUALIZAÇÃO: Chave para o JWT ---
# Esta chave é usada para assinar os tokens de autenticação.
# É crucial que seja secreta e forte em um ambiente de produção.
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")


# Modelo de Geração de Conteúdo (LLM principal e Agentes)
GENERATIVE_MODEL = "gemini-2.5-flash"
AGENT_GENERATIVE_MODEL = "gemini-2.0-flash"

# Modelo de Embedding
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Configurações dos Agentes ---
# Número máximo de "tarefas" ou chamadas de função que um agente pode
# realizar em um único turno. Isto controla o processamento em lote.
MAX_AGENT_TOOL_CALLS = 5

# Versão do Arquivo de Configuração
CONFIG_VERSION = "1.4.0" # Adicionado sistema de contas com DB central e JWT.

# Exemplo de como você pode imprimir as configurações para depuração
def print_config_summary():
    print("\n--- Sumário das Configurações ---")
    print(f"Versão da Configuração: {CONFIG_VERSION}")
    print(f"Diretório Base do Projeto: {BASE_DIR}")
    print(f"Diretório de Dados de Produção: {PROD_DATA_DIR}")
    print(f"Caminho do DB Central: {DB_PATH_CENTRAL}")
    print(f"Template de Caminho do DB de Sessão: {DB_PATH_SQLITE_TEMPLATE}")
    print(f"Caminho do ChromaDB: {CHROMA_PATH}")
    print(f"Neo4j URI: {NEO4J_URI}")
    print(f"Neo4j User: {NEO4J_USER}")
    print(f"Neo4j Password: {'********' if NEO4J_PASSWORD else 'N/A (Vazio)'}")
    print(f"GEMINI_API_KEY: {'********' if GEMINI_API_KEY else 'N/A (Vazio/Não Definida)'}")
    print(f"JWT Secret Key: {'********' if JWT_SECRET_KEY else 'N/A (Vazio)'}")
    print(f"Modelo Generativo (Principal): {GENERATIVE_MODEL}")
    print(f"Modelo Generativo (Agentes): {AGENT_GENERATIVE_MODEL}")
    print(f"Modelo de Embedding: {EMBEDDING_MODEL}")
    print(f"Máximo de Chamadas de Ferramenta por Agente: {MAX_AGENT_TOOL_CALLS}")
    print("---------------------------------\n")

if __name__ == "__main__":
    print_config_summary()
