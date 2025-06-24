import yaml
import sqlite3
import os
import json
import sys
import time

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
LORE_SOURCE_DIR = os.path.join(PROJECT_ROOT, 'lore_fonte')
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

def setup_database(cursor):
    """
    Cria a estrutura completa da base de dados (v6.2).
    Refatorado para usar blocos de script únicos para criação de tabelas e índices.
    """
    print("--- Configurando a Base de Dados (v6.2) ---")
    
    # --- Criação de Tabelas ---
    print("Criando todas as tabelas...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT,
            parent_id INTEGER,
            perfil_yaml TEXT,
            FOREIGN KEY (parent_id) REFERENCES locais(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS tecnologias (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            perfil_yaml TEXT
        );
        CREATE TABLE IF NOT EXISTS personagens (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            perfil_yaml TEXT
        );
        CREATE TABLE IF NOT EXISTS civilizacoes (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            perfil_yaml TEXT
        );
        CREATE TABLE IF NOT EXISTS jogador (
            id INTEGER PRIMARY KEY,
            id_canonico TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            local_atual_id INTEGER,
            creditos_conta INTEGER,
            creditos_iip INTEGER,
            perfil_completo_yaml TEXT,
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
            jogador_id INTEGER NOT NULL,
            item_nome TEXT UNIQUE NOT NULL,
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
            data_estelar TEXT,
            horario_atual TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );
        CREATE TABLE IF NOT EXISTS jogador_logs_memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- 'log_evento' ou 'memoria_consolidada'
            data_estelar TEXT,
            horario TEXT,
            conteudo TEXT,
            FOREIGN KEY (jogador_id) REFERENCES jogador(id)
        );
        CREATE TABLE IF NOT EXISTS local_tecnologias (
            local_id INTEGER NOT NULL,
            tecnologia_id INTEGER NOT NULL,
            PRIMARY KEY (local_id, tecnologia_id),
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
            FOREIGN KEY (tecnologia_id) REFERENCES tecnologias(id) ON DELETE CASCADE
        );
    """)

    # --- Criação de Índices ---
    print("Criando índices para otimização...")
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_locais_id_canonico ON locais(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_locais_parent_id ON locais(parent_id);
        CREATE INDEX IF NOT EXISTS idx_locais_tipo ON locais(tipo);
        CREATE INDEX IF NOT EXISTS idx_tecnologias_id_canonico ON tecnologias(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_personagens_id_canonico ON personagens(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_civilizacoes_id_canonico ON civilizacoes(id_canonico);
        CREATE INDEX IF NOT EXISTS idx_jogador_id_canonico ON jogador(id_canonico);
    """)
    print("SUCESSO: Base de dados v6.2 configurada.")

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

def _execute_many_with_progress(cursor, statement, data, description=""):
    """Executa 'executemany' mostrando uma barra de progresso simples."""
    total = len(data)
    if total == 0:
        return
    print(f"INFO: Inserindo {total} registos em '{description}'...")
    for i, item in enumerate(data):
        cursor.execute(statement, item)
        # Atualiza a barra de progresso
        progress = (i + 1) / total
        bar_length = 30
        block = int(round(bar_length * progress))
        text = f"\rProgresso: [{'#' * block + '-' * (bar_length - block)}] {i+1}/{total}"
        sys.stdout.write(text)
        sys.stdout.flush()
    print("\n") # Nova linha após a conclusão

def popular_entidades_e_mapear_ids(cursor, file_name, root_keys, id_field, name_field, table_name):
    """Função genérica para popular tabelas de entidades canónicas."""
    print(f"Processando '{file_name}' para a tabela '{table_name}'...")
    data = load_yaml_file(file_name)
    id_map = {}
    if not data: return id_map
    
    start_node = data
    for key in root_keys:
        if isinstance(start_node, dict) and key in start_node:
            start_node = start_node[key]
        else:
            print(f"AVISO: Chave '{key}' na sequência {root_keys} não encontrada em '{file_name}'.")
            return id_map
            
    entidades_para_inserir = []
    def pesquisar_entidades_recursivamente(node):
        if isinstance(node, dict):
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
            for value in node.values(): pesquisar_entidades_recursivamente(value)
        elif isinstance(node, list):
            for item in node: pesquisar_entidades_recursivamente(item)
            
    pesquisar_entidades_recursivamente(start_node)
    
    if table_name == 'locais':
        for id_canonico, nome, tipo, perfil_yaml in entidades_para_inserir:
            cursor.execute("INSERT INTO locais (id_canonico, nome, tipo, perfil_yaml) VALUES (?, ?, ?, ?)", (id_canonico, nome, tipo, perfil_yaml))
            id_map[id_canonico] = cursor.lastrowid
    else: 
        for id_canonico, nome, perfil_yaml in entidades_para_inserir:
            cursor.execute(f"INSERT INTO {table_name} (id_canonico, nome, perfil_yaml) VALUES (?, ?, ?)", (id_canonico, nome, perfil_yaml))
            id_map[id_canonico] = cursor.lastrowid
            
    print(f"INFO: {len(id_map)} registos inseridos na tabela '{table_name}'.")
    return id_map

def popular_jogador_status(cursor, locais_map):
    """Lê os ficheiros de status e log para popular todas as tabelas do jogador."""
    print("\nProcessando dados do jogador...")
    data_status = load_yaml_file('status_main_character.yml')
    if not data_status: return
    
    jogador_db_id = 1
    local_atual_canonico = 'setor_lab_atmosferico_4b'
    cursor.execute("INSERT INTO jogador (id, id_canonico, nome, local_atual_id, creditos_conta, creditos_iip, perfil_completo_yaml) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (jogador_db_id, data_status['id'], data_status['personagem_principal'], locais_map.get(local_atual_canonico), data_status['status_atual']['creditos']['conta_principal'], data_status['status_atual']['creditos']['pulseira_iip'], yaml.dump(data_status, allow_unicode=True, sort_keys=False)))
    
    status = data_status['status_atual']['estado_fisico_emocional']
    humor_str = ', '.join(status.get('humor', []))
    cursor.execute("INSERT INTO jogador_status_fisico_emocional (id, jogador_id, fome, sede, cansaco, humor, motivacao, data_estelar, horario_atual) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, jogador_db_id, status.get('fome'), status.get('sede'), status.get('cansaco'), humor_str, status.get('motivacao'), data_status['status_atual'].get('data_estelar'), data_status['status_atual'].get('horario_atual')))
    
    habilidades = [(jogador_db_id, 'tecnica', h['nome'], h['nivel_subnivel'], h.get('observacoes')) for h in data_status['ficha_habilidades']['habilidades_tecnicas']]
    habilidades.extend([(jogador_db_id, 'cognitiva', h['nome'], h['nivel_subnivel'], h.get('observacoes')) for h in data_status['ficha_habilidades']['habilidades_cognitivas']])
    habilidades.extend([(jogador_db_id, 'aptidao', a['nome'], None, a.get('descricao')) for a in data_status['conhecimentos_aptidoes']['aptidoes_desenvolvidas']])
    _execute_many_with_progress(cursor, "INSERT INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)", habilidades, "jogador_habilidades")

    conhecimentos = [(jogador_db_id, 'mundo', c['nome'], c['nivel'], c.get('descricao')) for c in data_status['conhecimentos_aptidoes']['conhecimento_mundo']]
    conhecimentos.extend([(jogador_db_id, 'tecnico', c['nome'], c['nivel'], c.get('descricao')) for c in data_status['conhecimentos_aptidoes']['conhecimento_tecnico']])
    _execute_many_with_progress(cursor, "INSERT INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)", conhecimentos, "jogador_conhecimentos")

    posses = [(jogador_db_id, item) for item in data_status['status_atual']['posses']]
    _execute_many_with_progress(cursor, "INSERT INTO jogador_posses (jogador_id, item_nome) VALUES (?, ?)", posses, "jogador_posses")

    data_logs = load_yaml_file('logs_memorias.yml')
    if data_logs and 'registro_narrativo' in data_logs:
        logs, registro = [], data_logs['registro_narrativo']
        data_log = registro.get('data')
        logs.extend([(jogador_db_id, 'log_evento', data_log, e.get('horario'), e.get('evento')) for e in registro.get('log_eventos', [])])
        if 'entrada' in registro.get('memorias_consolidadas', {}):
            logs.append((jogador_db_id, 'memoria_consolidada', data_log, None, registro['memorias_consolidadas'].get('entrada')))
        _execute_many_with_progress(cursor, "INSERT INTO jogador_logs_memoria (jogador_id, tipo, data_estelar, horario, conteudo) VALUES (?, ?, ?, ?, ?)", logs, "jogador_logs_memoria")

def atualizar_relacoes_hierarquicas(cursor, file_name, locais_map):
    """Atualiza as chaves estrangeiras (parent_id) na tabela de locais."""
    print(f"\nAtualizando relações hierárquicas para '{file_name}'...")
    data = load_yaml_file(file_name)
    if not data or 'locais' not in data: return
    updates = []
    def pesquisar_parentes_recursivamente(node):
        if isinstance(node, dict):
            if 'id' in node and 'parent_id' in node and node['parent_id']:
                child_db_id, parent_db_id = locais_map.get(node['id']), locais_map.get(node['parent_id'])
                if child_db_id and parent_db_id: updates.append((parent_db_id, child_db_id))
            for value in node.values(): pesquisar_parentes_recursivamente(value)
        elif isinstance(node, list):
            for item in node: pesquisar_parentes_recursivamente(item)
    pesquisar_parentes_recursivamente(data['locais'])
    if updates:
        _execute_many_with_progress(cursor, "UPDATE locais SET parent_id = ? WHERE id = ?", updates, "relações hierárquicas")

def popular_tabela_ligacao(cursor, file_name, locais_map, tecnologias_map):
    """Popula a tabela de ligação local_tecnologias usando IDs."""
    print(f"Populando tabela de ligação 'local_tecnologias' de '{file_name}'...")
    data = load_yaml_file(file_name)
    if not data: return
    ligacoes = []
    def pesquisar_ligacoes_recursivamente(node):
        if isinstance(node, dict):
            if 'id' in node and 'tecnologias_presentes' in node:
                local_db_id = locais_map.get(node['id'])
                techs_presentes = node['tecnologias_presentes']
                if local_db_id and isinstance(techs_presentes, list):
                    for tech_id_canonico in techs_presentes:
                        tech_db_id = tecnologias_map.get(tech_id_canonico)
                        if tech_db_id:
                            ligacoes.append((local_db_id, tech_db_id))
                        else:
                            print(f"  - AVISO: ID de Tecnologia '{tech_id_canonico}' listado em '{node['id']}' não foi encontrado.")
            for value in node.values(): pesquisar_ligacoes_recursivamente(value)
        elif isinstance(node, list):
            for item in node: pesquisar_ligacoes_recursivamente(item)
    pesquisar_ligacoes_recursivamente(data)
    if ligacoes:
        _execute_many_with_progress(cursor, "INSERT OR IGNORE INTO local_tecnologias (local_id, tecnologia_id) VALUES (?, ?)", ligacoes, "local_tecnologias")

def main():
    """Função principal que orquestra a construção do mundo."""
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        setup_database(cursor)
        
        cursor.execute('BEGIN TRANSACTION')
        
        print("\n--- Fase 1: Populando Entidades Canónicas ---")
        entidades_a_popular = [
            ('mapa_universo.yml', ['locais'], 'id', 'nome', 'locais'),
            ('conhecimentos_universais.yml', ['tecnologias'], 'id', 'nome', 'tecnologias'),
            ('personagens.yml', ['personagens', 'personagens_nao_jogadores'], 'id', 'nome', 'personagens'),
            ('civilizacoes_galacticas.yml', ['civilizacoes_galacticas'], 'id', 'nome', 'civilizacoes')
        ]
        mapas_de_id = {
            tabela: popular_entidades_e_mapear_ids(cursor, *args, tabela)
            for *args, tabela in entidades_a_popular
        }
        
        print("\n--- Fase 2: Populando Estado do Jogador ---")
        popular_jogador_status(cursor, mapas_de_id['locais'])
        
        print("\n--- Fase 3: Relações e Ligações ---")
        atualizar_relacoes_hierarquicas(cursor, 'mapa_universo.yml', mapas_de_id['locais'])
        popular_tabela_ligacao(cursor, 'mapa_universo.yml', mapas_de_id['locais'], mapas_de_id['tecnologias'])
        
        conn.commit()
        print("\n--- Construção do Mundo (v6.2) Concluída com Sucesso ---")
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERRO: A construção do mundo falhou. Erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
