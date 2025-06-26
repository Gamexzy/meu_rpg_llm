import sqlite3
import os
import sys

# Adiciona o diretório da raiz do projeto ao sys.path para que o módulo config possa ser importado
# Assumindo que o script build_world.py está em meu_rpg_llm/scripts/
# E o config.py está em meu_rpg_llm/config/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))

# NOVO: Importar as configurações globais
import config as config 

def create_meta_tables(cursor):
    """Cria as tabelas de lookup para os tipos de entidades."""
    print("Criando metatables para tipos...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tipos_entidades (
            id INTEGER PRIMARY KEY,
            nome_tabela TEXT NOT NULL, -- Ex: 'locais', 'faccoes'
            nome_tipo TEXT NOT NULL,   -- Ex: 'Planeta', 'Reino'
            UNIQUE(nome_tabela, nome_tipo)
        );
    """)

def create_core_tables(cursor):
    """Cria as tabelas principais de entidades."""
    print("Criando tabelas de entidades principais...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo_id INTEGER,
            parent_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (tipo_id) REFERENCES tipos_entidades(id),
            FOREIGN KEY (parent_id) REFERENCES locais(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS elementos_universais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (tipo_id) REFERENCES tipos_entidades(id)
        );

        CREATE TABLE IF NOT EXISTS personagens (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (tipo_id) REFERENCES tipos_entidades(id)
        );

        CREATE TABLE IF NOT EXISTS faccoes (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (tipo_id) REFERENCES tipos_entidades(id)
        );
    """)

def create_player_tables(cursor):
    """Cria as tabelas específicas do jogador."""
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
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_conhecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            nome TEXT NOT NULL,
            nivel INTEGER,
            descricao TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_posses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_canonico TEXT UNIQUE NOT NULL, -- NOVO: ID canônico para a posse
            jogador_id INTEGER NOT NULL,
            item_nome TEXT NOT NULL,
            perfil_json TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_status_fisico_emocional (
            id INTEGER PRIMARY KEY,
            jogador_id INTEGER NOT NULL,
            fome TEXT,
            sede TEXT,
            cansaco TEXT,
            humor TEXT,
            motivacao TEXT,
            -- Data/Hora padronizada para ordenação e cálculos
            timestamp_atual TEXT, -- Formato 'YYYY-MM-DD HH:MM:SS'
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_logs_memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- 'log_evento' ou 'memoria_consolidada'
            timestamp_evento TEXT, -- Formato 'YYYY-MM-DD HH:MM:SS'
            conteudo TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );
    """)

def create_relationship_tables(cursor):
    """Cria as tabelas que definem relações entre entidades."""
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
            entidade_origem_tipo TEXT NOT NULL, -- nome da tabela da entidade (ex: "personagens")
            tipo_relacao TEXT NOT NULL,
            entidade_destino_id TEXT NOT NULL,
            entidade_destino_tipo TEXT NOT NULL, -- nome da tabela da entidade (ex: "locais")
            propriedades_json TEXT
        );
    """)

def create_indexes(cursor):
    """Cria índices para otimização de consultas."""
    print("Criando índices para otimização...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id);
        CREATE INDEX IF NOT EXISTS idx_locais_tipo_id ON locais(tipo_id);

        CREATE INDEX IF NOT EXISTS idx_elementos_universais_id_canonico ON elementos_universais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_elementos_universais_tipo_id ON elementos_universais(tipo_id);

        CREATE INDEX IF NOT EXISTS idx_personagens_id_canonico ON personagens(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_personagens_tipo_id ON personagens(tipo_id);

        CREATE INDEX IF NOT EXISTS idx_faccoes_id_canonico ON faccoes(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_faccoes_tipo_id ON faccoes(tipo_id);
        
        CREATE INDEX IF NOT EXISTS idx_jogador_id_canonico ON jogador(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_local_atual_id ON jogador(local_atual_id);
        
        CREATE INDEX IF NOT EXISTS idx_jogador_posses_id_canonico ON jogador_posses(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_posses_jogador_id ON jogador_posses(jogador_id);

        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_origem ON relacoes_entidades(entidade_origem_id, entidade_origem_tipo);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_destino ON relacoes_entidades(entidade_destino_id, entidade_destino_tipo);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_tipo_relacao ON relacoes_entidades(tipo_relacao);
    """)

def populate_meta_tables(cursor):
    """Popula as tabelas de tipos com valores iniciais."""
    print("Populando metatables com tipos iniciais...")
    tipos = {
        'locais': ["Planeta", "Cidade", "Estação Espacial", "Caverna", "Masmorra", "Sala", "Braço Espiral", "Região Galáctica", "Setor Estelar", "Sistema Estelar"],
        'elementos_universais': ["Tecnologia", "Magia", "Recurso", "Poder", "Fenomeno", "Item_Especial"],
        'personagens': ["Jogador", "NPC", "Monstro", "Entidade"],
        'faccoes': ["Reino", "Império", "Corporação", "Guilda", "Tribo", "Aliança", "Culto"]
    }
    
    for nome_tabela, lista_tipos in tipos.items():
        for nome_tipo in lista_tipos:
            cursor.execute(
                "INSERT OR IGNORE INTO tipos_entidades (nome_tabela, nome_tipo) VALUES (?, ?)", # Usar INSERT OR IGNORE para idempotência
                (nome_tabela, nome_tipo)
            )

def setup_database(cursor):
    """
    Cria a estrutura completa e vazia da base de dados (v9.4).
    Versão: 9.4 - Usa configurações de config.py e ajustado para a árvore de ficheiros.
    """
    print("--- Configurando a Base de Dados (v9.4) ---")
    create_meta_tables(cursor)
    create_core_tables(cursor)
    create_player_tables(cursor)
    create_relationship_tables(cursor)
    create_indexes(cursor)
    populate_meta_tables(cursor)
    print("SUCESSO: Base de dados v9.4 configurada com tabelas vazias e tipos preenchidos.")

def main():
    """
    Função principal que orquestra a criação do esquema do banco de dados.
    """
    # Usa config.PROD_DATA_DIR e config.DB_PATH_SQLITE
    os.makedirs(config.PROD_DATA_DIR, exist_ok=True) 
    if os.path.exists(config.DB_PATH_SQLITE): 
        os.remove(config.DB_PATH_SQLITE) # Remove o DB existente para garantir um build limpo
        print(f"INFO: Arquivo de banco de dados existente '{config.DB_PATH_SQLITE}' removido.")
        
    conn = sqlite3.connect(config.DB_PATH_SQLITE) # Usa config.DB_PATH_SQLITE
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        setup_database(cursor)
        conn.commit()
        print(f"\n--- Estrutura do Mundo (v9.4) Criada com Sucesso ---")
        print(f"O arquivo '{config.DB_PATH_SQLITE}' foi criado e está pronto para uso.")
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERRO: A criação da estrutura do mundo falhou. Erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
