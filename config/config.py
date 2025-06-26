import os

# --- Configuração de Caminhos Globais ---
# A BASE_DIR aponta para a raiz do projeto (meu_rpg_llm)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Caminho para o diretório onde os dados em produção serão armazenados
PROD_DATA_DIR = os.path.join(BASE_DIR, 'dados_em_producao')

# Caminho para o arquivo de banco de dados SQLite (Pilar B)
DB_PATH_SQLITE = os.path.join(PROD_DATA_DIR, 'estado.db')

# Caminho para o diretório de persistência do ChromaDB (Pilar A)
CHROMA_PATH = os.path.join(PROD_DATA_DIR, 'chroma_db')

# --- Configuração do Neo4j (Pilar C) ---
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password") # ALtere se sua senha for diferente

# --- Configuração da API Gemini (LLM e Embedding) ---
# Se estiver rodando localmente, você DEVE definir a variável de ambiente GEMINI_API_KEY.
# Ex: export GEMINI_API_KEY="SUA_CHAVE_AQUI" no Linux/macOS
#     set GEMINI_API_KEY=SUA_CHAVE_AQUI no Windows CMD
# Ou, para testes, você pode substituir os.environ.get("GEMINI_API_KEY", "") por sua chave.
# IMPORTANTE: Em produção, sempre use variáveis de ambiente.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Modelo de Geração de Conteúdo (LLM principal)
GENERATIVE_MODEL = "gemini-2.0-flash" 

# Modelo de Embedding
EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Ou "text-embedding-004" se preferir o estável

# --- Outras Configurações Globais (Exemplos) ---
DEFAULT_PLAYER_ID_CANONICO = 'pj_gabriel_oliveira'
DEFAULT_INITIAL_LOCATION_ID_CANONICO = 'estacao_base_alfa'

# Versão do Arquivo de Configuração
CONFIG_VERSION = "1.0.0"

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
    print(f"Modelo Generativo: {GENERATIVE_MODEL}")
    print(f"Modelo de Embedding: {EMBEDDING_MODEL}")
    print("---------------------------------\n")

if __name__ == "__main__":
    print_config_summary()
