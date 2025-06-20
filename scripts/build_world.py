import yaml
import sqlite3
import os
import json

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Assumindo que o script está em /scripts, volta um nível
PROJECT_ROOT = os.path.dirname(BASE_DIR) 
LORE_SOURCE_DIR = os.path.join(PROJECT_ROOT, 'lore_fonte')
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

def setup_database():
    """Cria a estrutura completa da base de dados relacional (SQLite)."""
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tabelas de Entidades Canónicas ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagens (
            id TEXT PRIMARY KEY,
            nome_completo TEXT NOT NULL,
            tipo TEXT,
            perfil_yaml TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locais (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo TEXT,
            perfil_yaml TEXT
        )
    ''')
    # Adicionar tabelas para tecnologias e facções aqui no futuro

    # --- Tabelas de Estado Dinâmico do Jogador ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagem_estado (
            id INTEGER PRIMARY KEY,
            personagem_id TEXT UNIQUE,
            nome TEXT,
            localizacao_atual_id TEXT,
            data_estelar TEXT,
            horario_atual TEXT,
            creditos_conta_principal INTEGER,
            creditos_pulseira_iip INTEGER,
            estado_fome TEXT,
            estado_sede TEXT,
            estado_cansaco TEXT,
            estado_humor TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT,
            item_id TEXT,
            quantidade INTEGER,
            FOREIGN KEY (personagem_id) REFERENCES personagem_estado(personagem_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habilidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT,
            nome_habilidade TEXT,
            tipo TEXT,
            nivel INTEGER,
            subnivel TEXT,
            observacoes TEXT,
            FOREIGN KEY (personagem_id) REFERENCES personagem_estado(personagem_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conhecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT,
            topico TEXT,
            categoria TEXT,
            nivel_proficiencia INTEGER,
            FOREIGN KEY (personagem_id) REFERENCES personagem_estado(personagem_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_eventos (
            id TEXT PRIMARY KEY,
            data_estelar TEXT,
            local_id TEXT,
            acao TEXT,
            detalhes_json TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print(f"SUCESSO: Base de dados configurada em '{DB_PATH}'.")

def load_yaml_file(file_path):
    """Carrega um ficheiro YAML e retorna os seus dados."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"AVISO: Ficheiro não encontrado: {file_path}")
    except yaml.YAMLError as e:
        print(f"ERRO de Formato YAML em {file_path}: {e}")
    return None

def build_world():
    """Lê os ficheiros YAML e povoa as bases de dados de produção."""
    print("\n--- Iniciando Construção do Mundo (Build World) ---")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Processar Entidades Canónicas ---
    # Personagens
    personagens_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'entidades_personagens.yml'))
    if personagens_data:
        personagens_para_inserir = [
            (p['personagem']['id'], p['personagem']['nome_completo'], p['personagem']['tipo'], yaml.dump(p['personagem']))
            for p in personagens_data if 'personagem' in p
        ]
        cursor.executemany('INSERT INTO personagens (id, nome_completo, tipo, perfil_yaml) VALUES (?, ?, ?, ?)', personagens_para_inserir)
        print(f"INFO: {len(personagens_para_inserir)} personagens inseridos.")

    # Locais
    locais_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'entidades_locais.yml'))
    if locais_data:
        locais_para_inserir = [
            (l['local']['id'], l['local']['nome'], l['local']['tipo'], yaml.dump(l['local']))
            for l in locais_data if 'local' in l
        ]
        cursor.executemany('INSERT INTO locais (id, nome, tipo, perfil_yaml) VALUES (?, ?, ?, ?)', locais_para_inserir)
        print(f"INFO: {len(locais_para_inserir)} locais inseridos.")

    # --- Processar Estado Inicial do Jogador ---
    estado_inicial_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'estado_inicial_jogador.yml'))
    if estado_inicial_data:
        char_id = estado_inicial_data['personagem_id']
        estado = estado_inicial_data['estado']
        
        cursor.execute('''
            INSERT INTO personagem_estado (id, personagem_id, nome, localizacao_atual_id, data_estelar, horario_atual, creditos_conta_principal, creditos_pulseira_iip, estado_fome, estado_sede, estado_cansaco, estado_humor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (1, char_id, 'Gabriel Oliveira', estado['localizacao_atual_id'], estado['data_estelar'], estado['horario_atual'], estado['creditos_conta_principal'], estado['creditos_pulseira_iip'], estado['estado_fome'], estado['estado_sede'], estado['estado_cansaco'], estado['estado_humor']))
        print(f"INFO: Estado inicial do jogador '{char_id}' inserido.")

        # Inventário Inicial
        inventario_para_inserir = [(char_id, item) for item in estado_inicial_data['inventario']]
        cursor.executemany('INSERT INTO inventario (personagem_id, item_id, quantidade) VALUES (?, ?, 1)', inventario_para_inserir)
        print(f"INFO: {len(inventario_para_inserir)} itens inseridos no inventário inicial.")

        # Habilidades Iniciais
        habilidades_para_inserir = [
            (char_id, h['nome'], h['tipo'], h['nivel'], h['subnivel'], h.get('observacoes', ''))
            for h in estado_inicial_data['habilidades']
        ]
        cursor.executemany('INSERT INTO habilidades (personagem_id, nome_habilidade, tipo, nivel, subnivel, observacoes) VALUES (?, ?, ?, ?, ?, ?)', habilidades_para_inserir)
        print(f"INFO: {len(habilidades_para_inserir)} habilidades inseridas.")

        # Conhecimentos Iniciais
        conhecimentos_para_inserir = [
            (char_id, c['topico'], c['categoria'], c['nivel_proficiencia'])
            for c in estado_inicial_data['conhecimentos']
        ]
        cursor.executemany('INSERT INTO conhecimentos (personagem_id, topico, categoria, nivel_proficiencia) VALUES (?, ?, ?, ?)', conhecimentos_para_inserir)
        print(f"INFO: {len(conhecimentos_para_inserir)} conhecimentos inseridos.")

    # --- Processar Log de Eventos Históricos ---
    log_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'log_eventos.yml'))
    if log_data:
        eventos_para_inserir = [
            (e['evento']['id'], e['evento']['data_estelar'], e['evento']['local_id'], e['evento']['acao'], json.dumps(e['evento']))
            for e in log_data if 'evento' in e
        ]
        cursor.executemany('INSERT INTO log_eventos (id, data_estelar, local_id, acao, detalhes_json) VALUES (?, ?, ?, ?, ?)', eventos_para_inserir)
        print(f"INFO: {len(eventos_para_inserir)} eventos históricos inseridos no log.")


    conn.commit()
    conn.close()
    print("\n--- Construção do Mundo Concluída ---")

if __name__ == '__main__':
    setup_database()
    build_world()
