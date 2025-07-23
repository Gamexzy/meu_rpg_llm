import sqlite3
import os
import sys
import argparse

# Adiciona o diretório da raiz do projeto ao sys.path para que os módulos possam ser importados
# Isso garante que o script possa ser executado de qualquer lugar.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
from config import config

def create_core_tables(cursor):
    """
    Cria as tabelas principais de entidades do mundo (locais, personagens, etc.).
    O tipo da entidade é uma string direta para maior flexibilidade.
    """
    print("Criando tabelas de entidades principais...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            parent_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (parent_id) REFERENCES locais(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS elementos_universais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            perfil_json TEXT
        );

        CREATE TABLE IF NOT EXISTS personagens (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            perfil_json TEXT
        );

        CREATE TABLE IF NOT EXISTS faccoes (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            perfil_json TEXT
        );

        CREATE TABLE IF NOT EXISTS itens (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            perfil_json TEXT
        );
    """)

def create_player_tables(cursor):
    """Cria todas as tabelas relacionadas ao estado e progresso do jogador."""
    print("Criando tabelas do jogador...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS jogador (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            local_atual_id INTEGER,
            perfil_completo_json TEXT,
            FOREIGN KEY (local_atual_id) REFERENCES locais(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_habilidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            nome TEXT NOT NULL,
            nivel_subnivel TEXT,
            observacoes TEXT,
            UNIQUE(jogador_id, categoria, nome),
            FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jogador_conhecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            nome TEXT NOT NULL,
            nivel INTEGER,
            descricao TEXT,
            UNIQUE(jogador_id, categoria, nome),
            FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jogador_posses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_canonico TEXT UNIQUE NOT NULL,
            jogador_id INTEGER NOT NULL,
            item_nome TEXT NOT NULL,
            perfil_json TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jogador_status_fisico_emocional (
            id INTEGER PRIMARY KEY,
            jogador_id INTEGER NOT NULL UNIQUE,
            fome TEXT,
            sede TEXT,
            cansaco TEXT,
            humor TEXT,
            motivacao TEXT,
            timestamp_atual TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jogador_logs_memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- Ex: 'log_evento', 'memoria_consolidada'
            timestamp_evento TEXT,
            conteudo TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE
        );
    """)

def create_relationship_tables(cursor):
    """Cria tabelas que definem relações entre diferentes entidades."""
    print("Criando tabelas de relações...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS local_elementos (
            local_id INTEGER NOT NULL,
            elemento_id INTEGER NOT NULL,
            PRIMARY KEY (local_id, elemento_id),
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
            FOREIGN KEY (elemento_id) REFERENCES elementos_universais(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS locais_acessos_diretos (
            local_origem_id INTEGER NOT NULL,
            local_destino_id INTEGER NOT NULL,
            tipo_acesso TEXT,
            condicoes_acesso TEXT,
            PRIMARY KEY (local_origem_id, local_destino_id),
            FOREIGN KEY (local_origem_id) REFERENCES locais(id) ON DELETE CASCADE,
            FOREIGN KEY (local_destino_id) REFERENCES locais(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relacoes_entidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidade_origem_id TEXT NOT NULL,
            entidade_origem_tipo TEXT NOT NULL,
            tipo_relacao TEXT NOT NULL,
            entidade_destino_id TEXT NOT NULL,
            entidade_destino_tipo TEXT NOT NULL,
            propriedades_json TEXT,
            UNIQUE(entidade_origem_id, tipo_relacao, entidade_destino_id)
        );
    """)

def create_indexes(cursor):
    """Cria índices para otimizar a performance das consultas mais comuns."""
    print("Criando índices para otimização...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id);
        CREATE INDEX IF NOT EXISTS idx_elementos_universais_id_canonico ON elementos_universais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_personagens_id_canonico ON personagens(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_faccoes_id_canonico ON faccoes(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_itens_id_canonico ON itens(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_id_canonico ON jogador(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_posses_jogador_id ON jogador_posses(jogador_id);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_origem ON relacoes_entidades(entidade_origem_id, entidade_origem_tipo);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_destino ON relacoes_entidades(entidade_destino_id, entidade_destino_tipo);
    """)

def setup_database(cursor):
    """
    Executa todas as funções para criar a estrutura completa e vazia da base de dados.
    Versão: 11.0 - Unificado para suportar criação de DBs por sessão.
    """
    print("--- Configurando a Base de Dados (v11.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")
    create_core_tables(cursor)
    create_player_tables(cursor)
    create_relationship_tables(cursor)
    create_indexes(cursor)
    print("SUCESSO: Base de dados configurada com tabelas vazias.")

def main():
    """
    Função principal que orquestra a criação do esquema do banco de dados para uma sessão específica.
    """
    parser = argparse.ArgumentParser(
        description="Cria ou verifica a estrutura do banco de dados para uma sessão de jogo específica."
    )
    parser.add_argument(
        "--session_name", 
        type=str, 
        required=True, 
        help="O nome da sessão de jogo (será usado como nome do arquivo .db)."
    )
    args = parser.parse_args()

    # Constrói o caminho do arquivo de banco de dados da sessão
    db_path = os.path.join(config.PROD_DATA_DIR, f"{args.session_name}.db")
    
    print(f"\n--- Iniciando a construção do mundo para a sessão: '{args.session_name}' ---")
    print(f"Local do arquivo: {db_path}")

    # Garante que o diretório de dados de produção exista
    os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        setup_database(cursor)
        conn.commit()
        print(f"\n--- Estrutura do Mundo (v11.0) Verificada/Criada com Sucesso ---")
        print(f"O arquivo '{db_path}' está pronto para uso.")
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERRO: A criação da estrutura do mundo para a sessão '{args.session_name}' falhou. Erro: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
