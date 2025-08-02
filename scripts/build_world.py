# scripts/build_world.py
import argparse
import os
import sqlite3
import traceback
from src import config

# --- FUNÇÕES DE SCHEMA PARA O BANCO DE DADOS CENTRAL ---
def setup_central_database(cursor):
    """Cria a estrutura completa do DB CENTRAL para gerenciar a arquitetura desacoplada."""
    print("--- Configurando a Base de Dados Central (v2.0.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Tabela de Usuários (sem grandes alterações)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tabela de Universos (Palcos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            db_path TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # Tabela de Personagens (Atores)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            background TEXT, -- Identidade do personagem
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # Tabela de Aventuras (Sessões de Jogo)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adventures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            universe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            db_path TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (universe_id) REFERENCES universes(id) ON DELETE CASCADE
        );
    """)

    # Tabela de Junção: Quem participa de qual aventura
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adventure_participants (
            adventure_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, -- O dono do personagem
            PRIMARY KEY (adventure_id, character_id),
            FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    print("SUCESSO: Base de dados Central configurada.")

# --- FUNÇÕES DE SCHEMA PARA BANCO DE DADOS DE UNIVERSO ---
def setup_universe_database(cursor):
    """Cria a estrutura de um banco de dados de UNIVERSO (regras e fatos persistentes)."""
    print("--- Configurando a Base de Dados de Universo (v2.0.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universal_laws (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            rule_name TEXT NOT NULL UNIQUE,
            description TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS major_factions (
            id INTEGER PRIMARY KEY,
            canonical_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT
        );
    """)
    print("SUCESSO: Base de dados de Universo configurada.")


# --- FUNÇÕES DE SCHEMA PARA BANCO DE DADOS DE AVENTURA ---
def setup_adventure_database(cursor):
    """Cria a estrutura de um banco de dados de AVENTURA (estado de jogo contextual)."""
    print("--- Configurando a Base de Dados de Aventura (v2.0.0) ---")
    cursor.execute("PRAGMA foreign_keys = ON;")
    # As tabelas aqui guardam o estado dos personagens DENTRO da aventura.
    # Note a adição de 'character_id' em todas as tabelas relevantes.
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS adventure_locations (
            id INTEGER PRIMARY KEY,
            canonical_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS character_status (
            character_id INTEGER PRIMARY KEY,
            current_location_id INTEGER,
            hp INTEGER,
            mana INTEGER,
            FOREIGN KEY (character_id) REFERENCES adventure_participants(character_id),
            FOREIGN KEY (current_location_id) REFERENCES adventure_locations(id)
        );
        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            description TEXT,
            FOREIGN KEY (character_id) REFERENCES adventure_participants(character_id)
        );
    """)
    print("SUCESSO: Base de dados de Aventura configurada.")


def main():
    parser = argparse.ArgumentParser(description="Cria a estrutura de um banco de dados.")
    parser.add_argument(
        "--target",
        required=True,
        choices=["central", "universe", "adventure"],
        help="O alvo da operação.",
    )
    parser.add_argument("--id", type=int, help="O ID do universo ou aventura (obrigatório para 'universe' e 'adventure').")
    args = parser.parse_args()

    # Garante que os diretórios de dados existam
    os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
    os.makedirs(config.UNIVERSES_DATA_DIR, exist_ok=True)
    os.makedirs(config.ADVENTURES_DATA_DIR, exist_ok=True)

    db_path = ""
    setup_function = None

    if args.target == "central":
        db_path = config.DB_PATH_CENTRAL
        setup_function = setup_central_database
    elif args.target == "universe":
        if not args.id:
            parser.error("--id é obrigatório para target='universe'")
        db_path = config.DB_PATH_UNIVERSE_TEMPLATE.format(universe_id=args.id)
        setup_function = setup_universe_database
    elif args.target == "adventure":
        if not args.id:
            parser.error("--id é obrigatório para target='adventure'")
        db_path = config.DB_PATH_ADVENTURE_TEMPLATE.format(adventure_id=args.id)
        setup_function = setup_adventure_database

    if db_path and setup_function:
        print(f"\n--- Construindo banco de dados '{args.target}' em {db_path} ---")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            setup_function(cursor)
            conn.commit()
            print(f"--- Estrutura '{args.target}' (v2.0.0) Verificada/Criada com Sucesso ---")
        except Exception as e:
            traceback.print_exc()
            print(f"\nERRO na criação do DB '{args.target}': {e}")
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    main()
