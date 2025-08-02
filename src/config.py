# src/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

# --- Configuração de Caminhos Globais ---
# A BASE_DIR aponta para a raiz do projeto (meu_rpg_llm)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENABLE_REQUEST_LOGGING = True

# --- ATUALIZAÇÃO: Diretórios de Dados Dedicados ---
PROD_DATA_DIR = os.path.join(BASE_DIR, 'dados_em_producao')
UNIVERSES_DATA_DIR = os.path.join(PROD_DATA_DIR, 'universos')
ADVENTURES_DATA_DIR = os.path.join(PROD_DATA_DIR, 'aventuras')

# --- ATUALIZAÇÃO: Caminhos dos Bancos de Dados ---
# Caminho para o banco de dados central (Pilar de Contas)
DB_PATH_CENTRAL = os.path.join(PROD_DATA_DIR, 'central.db')

# Template para os bancos de dados SQLite específicos de cada UNIVERSO
DB_PATH_UNIVERSE_TEMPLATE = os.path.join(UNIVERSES_DATA_DIR, 'universo_{universe_id}.db')

# Template para os bancos de dados SQLite específicos de cada AVENTURA
DB_PATH_ADVENTURE_TEMPLATE = os.path.join(ADVENTURES_DATA_DIR, 'aventura_{adventure_id}.db')

# Caminho para o diretório de persistência do ChromaDB (Pilar A)
CHROMA_PATH = os.path.join(PROD_DATA_DIR, 'chroma_db')

# --- Configuração do Neo4j (Pilar C) ---
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# --- Configuração da API Gemini (LLM e Embedding) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --- Chave para o JWT ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "default-secret-key-for-dev")

# --- Modelos de IA ---
GENERATIVE_MODEL = "gemini-2.5-flash"
AGENT_GENERATIVE_MODEL = "gemini-2.0-flash"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Configurações dos Agentes ---
MAX_AGENT_TOOL_CALLS = 5

# Versão do Arquivo de Configuração
CONFIG_VERSION = "2.0.0" # Arquitetura de Universos, Personagens e Aventuras.

def print_config_summary():
    """Imprime um resumo das configurações para depuração."""
    print("\n--- Sumário das Configurações ---")
    print(f"Versão da Configuração: {CONFIG_VERSION}")
    print(f"Diretório de Dados de Produção: {PROD_DATA_DIR}")
    print(f"Diretório de Universos: {UNIVERSES_DATA_DIR}")
    print(f"Diretório de Aventuras: {ADVENTURES_DATA_DIR}")
    print(f"Caminho do DB Central: {DB_PATH_CENTRAL}")
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
