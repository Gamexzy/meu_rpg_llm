import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'dados_estruturados', 'rpg_data.db')

def setup_database_v3():
    """
    Configura a arquitetura V3 da base de dados relacional (SQLite),
    otimizada para modularidade e expansibilidade.
    """
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Diretório criado: {db_dir}")

    # Apaga a base de dados antiga para garantir uma reconstrução limpa, se ela existir.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"AVISO: Base de dados antiga '{DB_PATH}' removida para criar a nova arquitetura.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabela dedicada ao personagem principal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagem_principal (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            localizacao_atual TEXT,
            humor_atual TEXT,
            vida INTEGER DEFAULT 100,
            energia INTEGER DEFAULT 100,
            fome INTEGER DEFAULT 0,
            sede INTEGER DEFAULT 0,
            creditos_conta INTEGER DEFAULT 0,
            creditos_pulseira INTEGER DEFAULT 0
        )
    ''')

    # Tabela para todos os PNJs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pnjs (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            localizacao_atual TEXT,
            relacionamento_com_pc INTEGER DEFAULT 0,
            perfil_json TEXT
        )
    ''')

    # Tabelas de "componentes" associados a personagens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habilidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            nome_habilidade TEXT NOT NULL,
            nivel TEXT,
            subnivel TEXT,
            descricao TEXT,
            UNIQUE(personagem_id, nome_habilidade)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            nome_item TEXT NOT NULL,
            descricao TEXT,
            quantidade INTEGER NOT NULL DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conhecimentos_aptidoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            categoria TEXT NOT NULL,
            topico TEXT NOT NULL,
            nivel_proficiencia INTEGER NOT NULL,
            is_aptidao INTEGER NOT NULL DEFAULT 0,
            UNIQUE(personagem_id, topico)
        )
    ''')

    # Tabela para um sistema de missões (Quest Log)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missoes (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'INATIVA',
            is_principal INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Tabela para o log bruto de eventos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_eventos_bruto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_estelar TEXT,
            timestamp_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            detalhes_json TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print(f"SUCESSO: Base de dados SQLite com arquitetura V3 configurada em '{DB_PATH}'.")

if __name__ == "__main__":
    setup_database_v3()
