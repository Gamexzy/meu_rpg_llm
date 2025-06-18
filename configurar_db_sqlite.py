import sqlite3
import os

def setup_database():
    """
    Configura o banco de dados SQLite e garante que todas as tabelas necessárias existam.
    Esta versão inclui tabelas normalizadas para inventário e conhecimentos para otimizar as consultas.
    """
    db_path = 'dados_estruturados/rpg_data.db'
    # Garante que o diretório para o banco de dados exista.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- Tabela de Personagens (Refinada) ---
    # Adicionamos colunas para dados frequentemente consultados para evitar parsing de JSON.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagens (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            localizacao_atual TEXT, -- Novo!
            humor_atual TEXT,       -- Novo!
            perfil_json TEXT,       -- Mantido para dados descritivos
            status_json TEXT        -- Mantido para dados de status menos frequentes
        )
    ''')

    # --- Tabela de Habilidades (Inalterada) ---
    # A estrutura atual já é eficiente.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habilidades (
            personagem_id TEXT,
            nome_habilidade TEXT NOT NULL,
            nivel TEXT,
            subnivel TEXT,
            descricao TEXT,
            PRIMARY KEY (personagem_id, nome_habilidade),
            FOREIGN KEY (personagem_id) REFERENCES personagens (id) ON DELETE CASCADE
        )
    ''')
    
    # --- Tabela de Inventário (Nova) ---
    # Para gerenciar os itens que um personagem possui de forma estruturada.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            nome_item TEXT NOT NULL,
            descricao TEXT,
            quantidade INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (personagem_id) REFERENCES personagens (id) ON DELETE CASCADE
        )
    ''')
    
    # --- Tabela de Conhecimentos e Aptidões (Nova) ---
    # Para estruturar o sistema de conhecimento do personagem.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conhecimentos_aptidoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            categoria TEXT NOT NULL,
            topico TEXT NOT NULL UNIQUE,
            nivel_proficiencia INTEGER NOT NULL,
            is_aptidao INTEGER NOT NULL DEFAULT 0, -- Usamos INTEGER 0/1 para booleano em SQLite
            FOREIGN KEY (personagem_id) REFERENCES personagens (id) ON DELETE CASCADE
        )
    ''')

    # --- Tabela do Arquivo Bruto (Inalterada) ---
    # O propósito desta tabela é ser um log completo, a sua estrutura atual é ideal.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arquivo_bruto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_estelar TEXT,
            local TEXT,
            personagens TEXT,
            acao TEXT,
            detalhes TEXT,
            emocao TEXT,
            insight TEXT,
            dialogo TEXT,
            timestamp_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados SQLite 'rpg_data.db' refinado e configurado com sucesso.")

if __name__ == "__main__":
    setup_database()

