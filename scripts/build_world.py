import sqlite3
import os
import sys

# Adiciona o diretório da raiz do projeto ao sys.path para que os módulos possam ser importados
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
sys.path.append(os.path.join(PROJECT_ROOT, 'data')) # Adiciona o diretório 'data' ao sys.path

# Importa as configurações globais
import config as config 
# Importa os tipos de entidades genéricos
import entity_types_data as entity_types_data # type: ignore

def create_meta_tables(cursor):
    """
    Cria as tabelas de lookup para os tipos de entidades.
    Adicionado: display_name para nomes amigáveis e parent_tipo_id para hierarquia.
    """
    print("Criando metatables para tipos...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tipos_entidades (
            id INTEGER PRIMARY KEY,
            nome_tabela TEXT NOT NULL,   -- Ex: 'locais', 'faccoes'
            nome_tipo TEXT NOT NULL,     -- Ex: 'planeta', 'reino' (em snake_case)
            display_name TEXT NOT NULL,  -- Ex: 'Planeta', 'Reino' (nome legível)
            parent_tipo_id INTEGER,      -- ID do tipo pai para hierarquia
            UNIQUE(nome_tabela, nome_tipo),
            FOREIGN KEY (parent_tipo_id) REFERENCES tipos_entidades(id) ON DELETE RESTRICT
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
    """
    Popula as tabelas de tipos com os valores genéricos definidos em entity_types_data.py.
    Esses tipos servem como base para a IA gerar variações.
    Agora insere 'display_name' (capitalizado) e 'parent_tipo_id' (NULL para os genéricos).
    """
    print("Populando metatables com tipos iniciais genéricos do entity_types_data.py...")
    # Usa GENERIC_ENTITY_TYPES do módulo entity_types_data
    for nome_tabela, lista_tipos in entity_types_data.GENERIC_ENTITY_TYPES.items():
        for nome_tipo_snake_case in lista_tipos:
            # Capitaliza a primeira letra para o display_name (ex: 'espacial' -> 'Espacial')
            display_name = nome_tipo_snake_case[0].upper() + nome_tipo_snake_case[1:]
            cursor.execute(
                "INSERT OR IGNORE INTO tipos_entidades (nome_tabela, nome_tipo, display_name, parent_tipo_id) VALUES (?, ?, ?, ?)",
                (nome_tabela, nome_tipo_snake_case, display_name, None) # parent_tipo_id é NULL para tipos genéricos
            )

def setup_database(cursor):
    """
    Cria a estrutura completa e vazia da base de dados (v9.8).
    Versão: 9.8 - Adicionado display_name e parent_tipo_id à tipos_entidades.
    """
    print("--- Configurando a Base de Dados (v9.8) ---")
    create_meta_tables(cursor)
    create_core_tables(cursor)
    create_player_tables(cursor)
    create_relationship_tables(cursor)
    create_indexes(cursor)
    populate_meta_tables(cursor)
    print("SUCESSO: Base de dados v9.8 configurada com tabelas vazias e tipos preenchidos.")

def main():
    """
    Função principal que orquestra a criação do esquema do banco de dados.
    Cria o DB se não existe, ou garante que o esquema esteja atualizado se existe.
    """
    # Usa config.PROD_DATA_DIR e config.DB_PATH_SQLITE
    os.makedirs(config.PROD_DATA_DIR, exist_ok=True) 
    
    conn = sqlite3.connect(config.DB_PATH_SQLITE) # Usa config.DB_PATH_SQLITE
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        setup_database(cursor)
        conn.commit()
        print(f"\n--- Estrutura do Mundo (v9.8) Verificada/Criada com Sucesso ---")
        print(f"O arquivo '{config.DB_PATH_SQLITE}' está pronto para uso e seus dados serão persistidos.")
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERRO: A verificação/criação da estrutura do mundo falhou. Erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
