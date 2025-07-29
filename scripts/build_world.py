# scripts/build_world.py
import sqlite3
import os
import sys
import argparse
import traceback

# Adiciona o diretório raiz do projeto ao sys.path para que os módulos, como 'config', possam ser importados
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
from src import config

# --- FUNÇÕES DE SCHEMA PARA SESSÃO DE JOGO ---

def create_core_tables_for_session(cursor):
    """Cria as tabelas de entidades do mundo para uma sessão (locais, personagens, etc.)."""
    print("Criando tabelas de entidades principais da sessão...")
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
        CREATE TABLE IF NOT EXISTS elementos_universais ( id INTEGER PRIMARY KEY, id_canonico TEXT UNIQUE NOT NULL, nome TEXT NOT NULL, tipo TEXT, perfil_json TEXT );
        CREATE TABLE IF NOT EXISTS personagens ( id INTEGER PRIMARY KEY, id_canonico TEXT UNIQUE NOT NULL, nome TEXT NOT NULL, tipo TEXT, perfil_json TEXT );
        CREATE TABLE IF NOT EXISTS faccoes ( id INTEGER PRIMARY KEY, id_canonico TEXT UNIQUE NOT NULL, nome TEXT NOT NULL, tipo TEXT, perfil_json TEXT );
        CREATE TABLE IF NOT EXISTS itens ( id INTEGER PRIMARY KEY, id_canonico TEXT UNIQUE NOT NULL, nome TEXT NOT NULL, tipo TEXT, perfil_json TEXT );
    """)

def create_player_tables_for_session(cursor):
    """Cria todas as tabelas relacionadas ao estado do jogador para uma sessão."""
    print("Criando tabelas do jogador da sessão...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS jogador (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            local_atual_id INTEGER,
            perfil_completo_json TEXT,
            FOREIGN KEY (local_atual_id) REFERENCES locais(id)
        );
        CREATE TABLE IF NOT EXISTS jogador_habilidades ( id INTEGER PRIMARY KEY AUTOINCREMENT, jogador_id INTEGER NOT NULL, categoria TEXT NOT NULL, nome TEXT NOT NULL, nivel_subnivel TEXT, observacoes TEXT, UNIQUE(jogador_id, categoria, nome), FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS jogador_conhecimentos ( id INTEGER PRIMARY KEY AUTOINCREMENT, jogador_id INTEGER NOT NULL, categoria TEXT NOT NULL, nome TEXT NOT NULL, nivel INTEGER, descricao TEXT, UNIQUE(jogador_id, categoria, nome), FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS jogador_posses ( id INTEGER PRIMARY KEY AUTOINCREMENT, id_canonico TEXT UNIQUE NOT NULL, jogador_id INTEGER NOT NULL, item_nome TEXT NOT NULL, perfil_json TEXT, FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS jogador_status_fisico_emocional ( id INTEGER PRIMARY KEY, jogador_id INTEGER NOT NULL UNIQUE, fome TEXT, sede TEXT, cansaco TEXT, humor TEXT, motivacao TEXT, timestamp_atual TEXT, FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS jogador_logs_memoria ( id INTEGER PRIMARY KEY AUTOINCREMENT, jogador_id INTEGER NOT NULL, tipo TEXT NOT NULL, timestamp_evento TEXT, conteudo TEXT, FOREIGN KEY (jogador_id) REFERENCES jogador(id) ON DELETE CASCADE );
    """)

def create_relationship_and_meta_tables_for_session(cursor):
    """Cria tabelas de relações e metadados para uma sessão."""
    print("Criando tabelas de relações e metadados da sessão...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS local_elementos ( local_id INTEGER NOT NULL, elemento_id INTEGER NOT NULL, PRIMARY KEY (local_id, elemento_id), FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE, FOREIGN KEY (elemento_id) REFERENCES elementos_universais(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS locais_acessos_diretos ( local_origem_id INTEGER NOT NULL, local_destino_id INTEGER NOT NULL, tipo_acesso TEXT, condicoes_acesso TEXT, PRIMARY KEY (local_origem_id, local_destino_id), FOREIGN KEY (local_origem_id) REFERENCES locais(id) ON DELETE CASCADE, FOREIGN KEY (local_destino_id) REFERENCES locais(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS relacoes_entidades ( id INTEGER PRIMARY KEY AUTOINCREMENT, entidade_origem_id TEXT NOT NULL, entidade_origem_tipo TEXT NOT NULL, tipo_relacao TEXT NOT NULL, entidade_destino_id TEXT NOT NULL, entidade_destino_tipo TEXT NOT NULL, propriedades_json TEXT, UNIQUE(entidade_origem_id, tipo_relacao, entidade_destino_id) );
        CREATE TABLE IF NOT EXISTS sagas ( id INTEGER PRIMARY KEY AUTOINCREMENT, session_name TEXT UNIQUE NOT NULL, player_name TEXT, world_concept TEXT );
    """)

def create_indexes_for_session(cursor):
    """Cria índices para otimizar as consultas da sessão."""
    print("Criando índices para a sessão...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id);
        CREATE INDEX IF NOT EXISTS idx_jogador_id_canonico ON jogador(id_canonico);
    """)

def setup_session_database(cursor):
    """Executa todas as funções para criar a estrutura completa de uma base de dados de SESSÃO."""
    print("--- Configurando a Base de Dados de Sessão (v13.1.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")
    create_core_tables_for_session(cursor)
    create_player_tables_for_session(cursor)
    create_relationship_and_meta_tables_for_session(cursor)
    create_indexes_for_session(cursor)
    print("SUCESSO: Base de dados de sessão configurada com tabelas vazias.")


# --- FUNÇÕES DE SCHEMA PARA O BANCO DE DADOS CENTRAL ---

def setup_central_database(cursor):
    """
    Cria a estrutura completa da base de dados CENTRAL para usuários e sagas.
    Versão: 13.1.0 - Alterado para autenticação com username/password.
    """
    print("--- Configurando a Base de Dados Central (v13.1.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Criando tabela 'usuarios'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    print("Criando tabela 'sagas'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            session_name TEXT UNIQUE NOT NULL,
            player_name TEXT,
            world_concept TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );
    """)

    print("Criando índices para o DB Central...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sagas_usuario_id ON sagas(usuario_id);")
    print("SUCESSO: Base de dados Central configurada.")


def main():
    parser = argparse.ArgumentParser(
        description="Cria ou verifica a estrutura do banco de dados central ou de uma sessão."
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        choices=['central', 'session'],
        help="O alvo da operação: 'central' para o DB de usuários, 'session' para um DB de jogo."
    )
    parser.add_argument(
        "--session_name",
        type=str,
        help="O nome da sessão de jogo (obrigatório se target='session')."
    )
    args = parser.parse_args()

    os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
    conn = None

    if args.target == 'central':
        db_path = config.DB_PATH_CENTRAL
        print(f"\n--- Iniciando a construção do banco de dados CENTRAL ---")
        print(f"Local do arquivo: {db_path}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_central_database(cursor)
            conn.commit()
            print(f"\n--- Estrutura do DB Central (v13.1.0) Verificada/Criada com Sucesso ---")

        except Exception as e:
            if conn: conn.rollback()
            traceback.print_exc()
            print(f"\nERRO: A criação da estrutura do DB Central falhou. Erro: {e}")

    elif args.target == 'session':
        if not args.session_name:
            parser.error("--session_name é obrigatório quando target='session'")

        db_path = config.DB_PATH_SQLITE_TEMPLATE.format(session_name=args.session_name)
        print(f"\n--- Iniciando a construção do mundo para a sessão: '{args.session_name}' ---")
        print(f"Local do arquivo: {db_path}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_session_database(cursor)
            conn.commit()
            print(f"\n--- Estrutura do Mundo (v13.1.0) Verificada/Criada com Sucesso ---")
            print(f"O arquivo '{db_path}' está pronto para uso.")

        except Exception as e:
            if conn: conn.rollback()
            traceback.print_exc()
            print(f"\nERRO: A criação da estrutura do mundo para a sessão '{args.session_name}' falhou. Erro: {e}")

    if conn:
        conn.close()

if __name__ == '__main__':
    # Exemplo de como executar pela linha de comando:
    # python scripts/build_world.py --target central
    # python scripts/build_world.py --target session --session_name "minha_aventura"
    main()
