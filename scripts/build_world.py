import yaml
import sqlite3
import os
import json

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
LORE_SOURCE_DIR = os.path.join(PROJECT_ROOT, 'lore_fonte')
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

def setup_database():
    """
    Cria a estrutura da base de dados (v3) com chaves primárias INTEGER,
    IDs canónicos de texto, tabelas de ligação e índices para performance.
    """
    print("--- Configurando a Base de Dados (v3.0) ---")
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # --- Tabelas de Entidades Canónicas com Chaves Híbridas ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            parent_id INTEGER,
            perfil_yaml TEXT,
            FOREIGN KEY (parent_id) REFERENCES locais(id) ON DELETE RESTRICT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tecnologias (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            perfil_yaml TEXT
        )
    ''')
    # ... (outras tabelas como pnjs, jogador, etc., seguiriam este padrão)

    # --- Tabela de Ligação para Locais e Tecnologias ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS local_tecnologias (
            local_id INTEGER NOT NULL,
            tecnologia_id INTEGER NOT NULL,
            PRIMARY KEY (local_id, tecnologia_id),
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
            FOREIGN KEY (tecnologia_id) REFERENCES tecnologias(id) ON DELETE CASCADE
        )
    ''')
    
    # --- Índices para Otimização de Consultas ---
    print("Criando índices para otimização...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_locais_tipo ON locais(tipo)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tecnologias_id_canonico ON tecnologias(id_canonico)')
    
    conn.commit()
    conn.close()
    print("SUCESSO: Base de dados v3 configurada com chaves híbridas e índices.")

def load_yaml_file(file_name):
    """Carrega um ficheiro YAML da pasta lore_fonte."""
    file_path = os.path.join(LORE_SOURCE_DIR, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"AVISO: Ficheiro '{file_name}' não encontrado.")
        return None
    except yaml.YAMLError as e:
        print(f"ERRO de YAML em {file_name}: {e}")
        return None

def popular_entidades_e_mapear_ids(cursor, file_name, root_key, id_field, name_field, table_name):
    """
    Função genérica para popular uma tabela e retornar um mapa de id_canonico -> id_numerico.
    Esta versão navega por toda a estrutura de dados para encontrar entidades.
    """
    print(f"Processando '{file_name}' para a tabela '{table_name}'...")
    data = load_yaml_file(file_name)
    id_map = {}
    
    if not data or root_key not in data:
        print(f"AVISO: Chave '{root_key}' não encontrada em '{file_name}'.")
        return id_map

    entidades_para_inserir = []
    
    def pesquisar_entidades_recursivamente(node):
        """Navega recursivamente por dicionários e listas para encontrar entidades."""
        if isinstance(node, dict):
            # A chave 'nome' pode ter nomes diferentes ('tipo' em propulsores)
            node_name = node.get(name_field) or node.get('tipo')

            if id_field in node and node_name:
                id_canonico = node[id_field]
                nome = node_name
                perfil_yaml = yaml.dump(node, allow_unicode=True, sort_keys=False)
                
                if table_name == 'locais':
                    tipo = node.get('tipo', None)
                    entidades_para_inserir.append((id_canonico, nome, tipo, perfil_yaml))
                else:
                    entidades_para_inserir.append((id_canonico, nome, perfil_yaml))

            for value in node.values():
                pesquisar_entidades_recursivamente(value)
        elif isinstance(node, list):
            for item in node:
                pesquisar_entidades_recursivamente(item)

    pesquisar_entidades_recursivamente(data[root_key])

    if table_name == 'locais':
        for id_canonico, nome, tipo, perfil_yaml in entidades_para_inserir:
            cursor.execute(
                "INSERT INTO locais (id_canonico, nome, tipo, perfil_yaml) VALUES (?, ?, ?, ?)",
                (id_canonico, nome, tipo, perfil_yaml)
            )
            id_map[id_canonico] = cursor.lastrowid
    else: 
        for id_canonico, nome, perfil_yaml in entidades_para_inserir:
            cursor.execute(
                f"INSERT INTO {table_name} (id_canonico, nome, perfil_yaml) VALUES (?, ?, ?)",
                (id_canonico, nome, perfil_yaml)
            )
            id_map[id_canonico] = cursor.lastrowid
        
    print(f"INFO: {len(id_map)} registos inseridos na tabela '{table_name}'.")
    return id_map


def atualizar_relacoes_hierarquicas(cursor, file_name, locais_map):
    """
    Atualiza as chaves estrangeiras (parent_id) na tabela de locais.
    """
    print(f"\nAtualizando relações hierárquicas (parent_id) para '{file_name}'...")
    data = load_yaml_file(file_name)
    if not data or 'locais' not in data:
        return

    updates = []
    def pesquisar_parentes_recursivamente(node):
        """Navega recursivamente para encontrar relações pai-filho."""
        if isinstance(node, dict):
            if 'id' in node and 'parent_id' in node and node['parent_id']:
                child_id_canonico = node['id']
                parent_id_canonico = node['parent_id']
                
                child_db_id = locais_map.get(child_id_canonico)
                parent_db_id = locais_map.get(parent_id_canonico)
                
                if child_db_id and parent_db_id:
                    updates.append((parent_db_id, child_db_id))

            for value in node.values():
                pesquisar_parentes_recursivamente(value)
        elif isinstance(node, list):
            for item in node:
                pesquisar_parentes_recursivamente(item)
    
    pesquisar_parentes_recursivamente(data['locais'])
    
    if updates:
        cursor.executemany("UPDATE locais SET parent_id = ? WHERE id = ?", updates)
        print(f"INFO: {len(updates)} relações de parentesco atualizadas.")
    else:
        print("INFO: Nenhuma relação de parentesco para atualizar.")

def popular_tabela_ligacao(cursor, file_name, locais_map, tecnologias_nome_map):
    """
    Popula a tabela de ligação local_tecnologias.
    Usa um mapa de NOMES para encontrar o ID da tecnologia.
    """
    print(f"\nPopulando tabela de ligação 'local_tecnologias' de '{file_name}'...")
    data = load_yaml_file(file_name)
    if not data:
        return
        
    ligacoes = []
    def pesquisar_ligacoes_tecnologia_recursivamente(node):
        """Navega recursivamente para encontrar listas de tecnologias em locais."""
        if isinstance(node, dict):
            if 'id' in node and 'tecnologias_presentes' in node:
                local_id_canonico = node['id']
                local_db_id = locais_map.get(local_id_canonico)

                techs_presentes = node['tecnologias_presentes']
                if local_db_id and isinstance(techs_presentes, list):
                    for tech_nome in techs_presentes:
                        tech_db_id = tecnologias_nome_map.get(tech_nome)
                        if tech_db_id:
                            ligacoes.append((local_db_id, tech_db_id))
                        else:
                            print(f"  - AVISO: Tecnologia '{tech_nome}' listada em '{local_id_canonico}' não foi encontrada no mapa de tecnologias.")
            
            for value in node.values():
                pesquisar_ligacoes_tecnologia_recursivamente(value)
        elif isinstance(node, list):
            for item in node:
                pesquisar_ligacoes_tecnologia_recursivamente(item)

    pesquisar_ligacoes_tecnologia_recursivamente(data)

    if ligacoes:
        cursor.executemany("INSERT OR IGNORE INTO local_tecnologias (local_id, tecnologia_id) VALUES (?, ?)", ligacoes)
        print(f"INFO: {len(ligacoes)} ligações local-tecnologia inseridas.")
    else:
        print("INFO: Nenhuma ligação local-tecnologia para inserir.")


def build_world():
    """
    Lê os ficheiros YAML e povoa a base de dados otimizada (v3) dentro de uma única transação.
    """
    setup_database()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('BEGIN TRANSACTION')
        
        # 1. Popular entidades e criar mapas de ID
        locais_map = popular_entidades_e_mapear_ids(cursor, 'mapa_universo.yml', 'locais', 'id', 'nome', 'locais')
        tecnologias_map = popular_entidades_e_mapear_ids(cursor, 'conhecimentos_universais.yml', 'tecnologias', 'id', 'nome', 'tecnologias')
        
        # Criar um mapa de nome_tecnologia -> id_db para a tabela de ligação
        cursor.execute("SELECT id, nome FROM tecnologias")
        tecnologias_nome_map = {nome: db_id for db_id, nome in cursor.fetchall()}

        # ... (chamar para pnjs, civilizacoes, etc.)

        # 2. Atualizar relações e ligações usando os mapas de ID
        atualizar_relacoes_hierarquicas(cursor, 'mapa_universo.yml', locais_map)
        popular_tabela_ligacao(cursor, 'mapa_universo.yml', locais_map, tecnologias_nome_map)
        
        # ... (popular tabelas de estado do jogador, usando os mapas para FKs)
        
        conn.commit()
        print("\n--- Construção do Mundo (v3.0) Concluída com Sucesso ---")
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERRO: A construção do mundo falhou. A transação foi revertida. Erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    build_world()
