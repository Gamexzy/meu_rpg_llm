import sqlite3
import os
import sys

# Adiciona o diretório da raiz do projeto ao sys.path para que os módulos possam ser importados
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
sys.path.append(os.path.join(PROJECT_ROOT, 'data')) # Adiciona o diretório 'data' ao sys.path - ainda necessário para o config

# Importa as configurações globais
import config as config 
# entity_types_data não é mais necessário aqui, pois os tipos não serão pré-populados.
# import entity_types_data as entity_types_data # type: ignore

# create_meta_tables é removida pois a tabela tipos_entidades não será usada.

def create_core_tables(cursor):
    """
    Cria as tabelas principais de entidades.
    REMOVIDO: Coluna tipo_id e suas FOREIGN KEY. O tipo agora será uma string direta.
    """
    print("Criando tabelas de entidades principais...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT, -- O tipo agora é uma string direta, não um ID de lookup
            parent_id INTEGER,
            perfil_json TEXT,
            FOREIGN KEY (parent_id) REFERENCES locais(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS elementos_universais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT, -- O tipo agora é uma string direta
            perfil_json TEXT
        );

        CREATE TABLE IF NOT EXISTS personagens (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT, -- O tipo agora é uma string direta
            perfil_json TEXT
        );

        CREATE TABLE IF NOT EXISTS faccoes (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT, -- O tipo agora é uma string direta
            perfil_json TEXT
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
            UNIQUE(jogador_id, categoria, nome), -- Adicionando UNIQUE para idempotência
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );

        CREATE TABLE IF NOT EXISTS jogador_conhecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            nome TEXT NOT NULL,
            nivel INTEGER,
            descricao TEXT,
            UNIQUE(jogador_id, categoria, nome), -- Adicionando UNIQUE para idempotência
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
    """
    Cria índices para otimização de consultas.
    REMOVIDO: Índices relacionados a tipo_id.
    """
    print("Criando índices para otimização...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id);
        -- REMOVIDO: CREATE INDEX IF NOT EXISTS idx_locais_tipo_id ON locais(tipo); -- Agora 'tipo' é string, não precisa de índice aqui como ID

        CREATE INDEX IF NOT EXISTS idx_elementos_universais_id_canonico ON elementos_universais(id_canonico);
        -- REMOVIDO: CREATE INDEX IF NOT EXISTS idx_elementos_universais_tipo_id ON elementos_universais(tipo);

        CREATE INDEX IF NOT EXISTS idx_personagens_id_canonico ON personagens(id_canonico);
        -- REMOVIDO: CREATE INDEX IF NOT EXISTS idx_personagens_tipo_id ON personagens(tipo);

        CREATE INDEX IF NOT EXISTS idx_faccoes_id_canonico ON faccoes(id_canonico);
        -- REMOVIDO: CREATE INDEX IF NOT EXISTS idx_faccoes_tipo_id ON faccoes(tipo);
        
        CREATE INDEX IF NOT EXISTS idx_jogador_id_canonico ON jogador(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_local_atual_id ON jogador(local_atual_id);
        
        CREATE INDEX IF NOT EXISTS idx_jogador_posses_id_canonico ON jogador_posses(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_posses_jogador_id ON jogador_posses(jogador_id);

        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_origem ON relacoes_entidades(entidade_origem_id, entidade_origem_tipo);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_destino ON relacoes_entidades(entidade_destino_id, entidade_destino_tipo);
        CREATE INDEX IF NOT EXISTS idx_relacoes_entidades_tipo_relacao ON relacoes_entidades(tipo_relacao);
    """)

# populate_meta_tables é removida pois a tabela tipos_entidades não será usada.

def setup_database(cursor):
    """
    Cria a estrutura completa e vazia da base de dados (v10.0).
    Versão: 10.0 - Removida a tabela 'tipos_entidades' e a coluna 'tipo_id' das entidades principais.
    """
    print("--- Configurando a Base de Dados (v10.0) ---")
    # create_meta_tables(cursor) -- REMOVIDO
    create_core_tables(cursor)
    create_player_tables(cursor)
    create_relationship_tables(cursor)
    create_indexes(cursor)
    # populate_meta_tables(cursor) -- REMOVIDO
    print("SUCESSO: Base de dados v10.0 configurada com tabelas vazias.")

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
        print(f"\n--- Estrutura do Mundo (v10.0) Verificada/Criada com Sucesso ---")
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
