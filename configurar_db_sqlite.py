import sqlite3
import os

def setup_database():
    """
    Configura o banco de dados SQLite e garante que todas as tabelas necessárias existam.
    Esta função é idempotente, ou seja, pode ser executada várias vezes sem causar erros.
    """
    db_path = 'dados_estruturados/rpg_data.db'
    # Garante que o diretório para o banco de dados exista.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tabela de Personagens (para o jogador e PNJs)
    # Armazena perfis e o estado atual do personagem em formato JSON.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagens (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            perfil_json TEXT,
            status_json TEXT
        )
    ''')

    # Tabela de Habilidades
    # Vinculada a um personagem pelo 'personagem_id'.
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

    # Tabela do Arquivo Bruto (Log de Eventos da Campanha)
    # Registra cada evento detalhado da narrativa.
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
    print("Banco de dados SQLite 'rpg_data.db' configurado com sucesso.")

if __name__ == "__main__":
    setup_database()
