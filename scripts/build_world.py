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
    Cria a estrutura completa da base de dados relacional (SQLite).
    Apaga a base de dados antiga para garantir uma construção limpa.
    """
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tabelas de Entidades Canónicas ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pnjs (
            id TEXT PRIMARY KEY,
            nome_completo TEXT NOT NULL,
            perfil_yaml TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jogador (
            id TEXT PRIMARY KEY,
            nome_completo TEXT NOT NULL,
            perfil_yaml TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locais (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            perfil_yaml TEXT
        )
    ''')

    # --- Tabelas de Estado Dinâmico do Jogador ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagem_estado (
            personagem_id TEXT PRIMARY KEY,
            localizacao_atual_id TEXT,
            data_estelar TEXT,
            horario_atual TEXT,
            creditos_conta_principal INTEGER,
            creditos_pulseira_iip INTEGER,
            fome TEXT,
            sede TEXT,
            cansaco TEXT,
            humor_json TEXT,
            FOREIGN KEY (personagem_id) REFERENCES jogador(id)
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, nome_item TEXT NOT NULL, UNIQUE(personagem_id, nome_item))')
    cursor.execute('CREATE TABLE IF NOT EXISTS habilidades (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, nome_habilidade TEXT NOT NULL, tipo TEXT, nivel TEXT, observacoes TEXT, UNIQUE(personagem_id, nome_habilidade))')
    cursor.execute('CREATE TABLE IF NOT EXISTS conhecimentos (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, topico TEXT NOT NULL, categoria TEXT, nivel_proficiencia INTEGER, UNIQUE(personagem_id, topico))')
    cursor.execute('CREATE TABLE IF NOT EXISTS log_narrativo_resumido (id INTEGER PRIMARY KEY, data_estelar TEXT, horario TEXT, evento TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS log_eventos_brutos (id INTEGER PRIMARY KEY, data_estelar TEXT, local TEXT, personagens_json TEXT, acao TEXT, detalhes TEXT, emocao TEXT, insight_json TEXT, item TEXT)')

    conn.commit()
    conn.close()
    print(f"SUCESSO: Base de dados configurada com tabelas 'jogador' e 'pnjs' separadas.")

def load_yaml_file(file_name):
    """Carrega um ficheiro YAML da pasta lore_fonte."""
    file_path = os.path.join(LORE_SOURCE_DIR, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"AVISO: Ficheiro não encontrado: {file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"ERRO de Formato YAML em {file_path}: {e}")
        return None

def build_world():
    """Lê todos os ficheiros YAML da lore e povoa a base de dados de produção."""
    print("\n--- Iniciando Construção do Mundo (Build World) ---")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- 1. Popular PNJs ---
    pnjs_data = load_yaml_file('personagens.yml')
    # CORREÇÃO: Acessa a estrutura aninhada correta ('personagens' -> 'personagens_nao_jogadores')
    if pnjs_data and 'personagens' in pnjs_data and 'personagens_nao_jogadores' in pnjs_data['personagens']:
        pnjs_para_inserir = [(p['id'], p['nome'], yaml.dump(p, allow_unicode=True)) for p in pnjs_data['personagens']['personagens_nao_jogadores']]
        cursor.executemany('INSERT INTO pnjs (id, nome_completo, perfil_yaml) VALUES (?, ?, ?)', pnjs_para_inserir)
        print(f"INFO: {len(pnjs_para_inserir)} PNJs inseridos na tabela 'pnjs'.")

    # --- 2. Popular Jogador e seu Estado Inicial ---
    gabriel_data = load_yaml_file('status_main_character.yml')
    if gabriel_data:
        gabriel_id = gabriel_data['id']
        cursor.execute('INSERT INTO jogador (id, nome_completo, perfil_yaml) VALUES (?, ?, ?)',
                       (gabriel_id, gabriel_data['personagem_principal'], yaml.dump(gabriel_data, allow_unicode=True)))
        print("INFO: Personagem principal 'Gabriel' inserido na tabela 'jogador'.")
        
        status = gabriel_data['status_atual']
        cursor.execute('INSERT INTO personagem_estado (personagem_id, localizacao_atual_id, data_estelar, horario_atual, creditos_conta_principal, creditos_pulseira_iip, fome, sede, cansaco, humor_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            gabriel_id, status['localizacao']['area_especifica'], status['data_estelar'],
            status['horario_atual'], status['creditos']['conta_principal'], status['creditos']['pulseira_iip'],
            status['estado_fisico_emocional']['fome'], status['estado_fisico_emocional']['sede'],
            status['estado_fisico_emocional']['cansaco'], json.dumps(status['estado_fisico_emocional']['humor'])
        ))
        print(f"INFO: Estado inicial do jogador '{gabriel_id}' inserido.")

        inventario = [(gabriel_id, item) for item in status['posses']]
        cursor.executemany('INSERT INTO inventario (personagem_id, nome_item) VALUES (?, ?)', inventario)
        print(f"INFO: {len(inventario)} itens inseridos no inventário.")
        
        habilidades = []
        for tipo, hab_list in gabriel_data['ficha_habilidades'].items():
            if tipo in ['habilidades_tecnicas', 'habilidades_cognitivas']:
                for hab in hab_list:
                    habilidades.append((gabriel_id, hab['nome'], tipo.replace('_', ' ').title(), hab['nivel_subnivel'], hab.get('observacoes', '')))
        cursor.executemany('INSERT INTO habilidades (personagem_id, nome_habilidade, tipo, nivel, observacoes) VALUES (?, ?, ?, ?, ?)', habilidades)
        print(f"INFO: {len(habilidades)} habilidades inseridas.")
        
        conhecimentos = []
        for cat_key, topicos_list in gabriel_data['conhecimentos_aptidoes'].items():
            if isinstance(topicos_list, list):
                for topico in topicos_list:
                    if isinstance(topico, dict) and 'nome' in topico:
                        conhecimentos.append((gabriel_id, topico['nome'], cat_key.replace('_', ' ').title(), topico.get('nivel')))
                    elif isinstance(topico, str):
                        conhecimentos.append((gabriel_id, topico, cat_key.replace('_', ' ').title(), None))
        cursor.executemany('INSERT INTO conhecimentos (personagem_id, topico, categoria, nivel_proficiencia) VALUES (?, ?, ?, ?)', conhecimentos)
        print(f"INFO: {len(conhecimentos)} conhecimentos e aptidões inseridos.")
    
    # --- 3. Popular Locais ---
    locais_data = load_yaml_file('layout_est_vigilancia_solaris.yml')
    if locais_data and 'layout_estacao' in locais_data and 'setores_pontos_interesse' in locais_data['layout_estacao']:
        locais_para_inserir = [(l['id'], l['nome'], yaml.dump(l, allow_unicode=True)) for l in locais_data['layout_estacao']['setores_pontos_interesse']]
        cursor.executemany('INSERT INTO locais (id, nome, perfil_yaml) VALUES (?, ?, ?)', locais_para_inserir)
        print(f"INFO: {len(locais_para_inserir)} locais inseridos.")

    # --- 4. Popular Logs ---
    logs_mem_data = load_yaml_file('logs_memorias.yml')
    if logs_mem_data and 'registro_narrativo' in logs_mem_data:
        data_geral = logs_mem_data['registro_narrativo'].get('data', 'Data Desconhecida')
        resumidos = [(data_geral, e['horario'], e['evento']) for e in logs_mem_data['registro_narrativo']['log_eventos']]
        cursor.executemany('INSERT INTO log_narrativo_resumido (data_estelar, horario, evento) VALUES (?, ?, ?)', resumidos)
        print(f"INFO: {len(resumidos)} eventos de log resumido inseridos.")

    logs_brutos_data = load_yaml_file('arquivo_bruto_rpg.yml')
    if logs_brutos_data and 'logs_campanha' in logs_brutos_data:
        brutos = [(log.get('data_estelar'), log.get('local'), json.dumps(log.get('personagens')), log.get('acao'), log.get('detalhes'), log.get('emocao'), json.dumps(log.get('insight')), log.get('item')) for log in logs_brutos_data['logs_campanha']]
        cursor.executemany('INSERT INTO log_eventos_brutos (data_estelar, local, personagens_json, acao, detalhes, emocao, insight_json, item) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', brutos)
        print(f"INFO: {len(brutos)} eventos de log bruto inseridos.")

    conn.commit()
    conn.close()
    print("\n--- Construção do Mundo Concluída com Sucesso ---")

if __name__ == '__main__':
    setup_database()
    build_world()
