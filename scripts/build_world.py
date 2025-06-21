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
    """
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tabelas de Entidades Canónicas ---
    cursor.execute('CREATE TABLE IF NOT EXISTS pnjs (id TEXT PRIMARY KEY, nome_completo TEXT NOT NULL, perfil_yaml TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS jogador (id TEXT PRIMARY KEY, nome_completo TEXT NOT NULL, perfil_yaml TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS locais (id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT, parent_id TEXT, perfil_yaml TEXT, FOREIGN KEY (parent_id) REFERENCES locais(id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS civilizacoes (id TEXT PRIMARY KEY, nome TEXT NOT NULL, perfil_yaml TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS tecnologias (id TEXT PRIMARY KEY, nome TEXT NOT NULL, perfil_yaml TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS glossario (id TEXT PRIMARY KEY, termo TEXT NOT NULL, perfil_yaml TEXT)')

    # --- Tabelas de Estado Dinâmico e Logs ---
    cursor.execute('CREATE TABLE IF NOT EXISTS personagem_estado (personagem_id TEXT PRIMARY KEY, localizacao_atual_id TEXT, data_estelar TEXT, horario_atual TEXT, creditos_conta_principal INTEGER, creditos_pulseira_iip INTEGER, fome TEXT, sede TEXT, cansaco TEXT, humor_json TEXT, FOREIGN KEY (personagem_id) REFERENCES jogador(id), FOREIGN KEY (localizacao_atual_id) REFERENCES locais(id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, nome_item TEXT NOT NULL, UNIQUE(personagem_id, nome_item))')
    cursor.execute('CREATE TABLE IF NOT EXISTS habilidades (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, nome_habilidade TEXT NOT NULL, tipo TEXT, nivel TEXT, observacoes TEXT, UNIQUE(personagem_id, nome_habilidade))')
    cursor.execute('CREATE TABLE IF NOT EXISTS conhecimentos (id INTEGER PRIMARY KEY, personagem_id TEXT NOT NULL, topico TEXT NOT NULL, categoria TEXT, nivel_proficiencia INTEGER, UNIQUE(personagem_id, topico))')
    cursor.execute('CREATE TABLE IF NOT EXISTS log_narrativo_resumido (id INTEGER PRIMARY KEY, data_estelar TEXT, horario TEXT, evento TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS log_eventos_brutos (id INTEGER PRIMARY KEY, data_estelar TEXT, local TEXT, personagens_json TEXT, acao TEXT, detalhes TEXT, emocao TEXT, insight_json TEXT, item TEXT)')

    conn.commit()
    conn.close()
    print(f"SUCESSO: Base de dados configurada com todas as tabelas, incluindo lore do universo.")

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

    # --- 1. Popular Entidades Principais (Jogador, PNJs) ---
    # (Lógica para popular PNJs e Jogador permanece a mesma)
    pnjs_data = load_yaml_file('personagens.yml')
    if pnjs_data and 'personagens' in pnjs_data and 'personagens_nao_jogadores' in pnjs_data['personagens']:
        pnjs = [(p['id'], p['nome'], yaml.dump(p, allow_unicode=True)) for p in pnjs_data['personagens']['personagens_nao_jogadores']]
        cursor.executemany('INSERT INTO pnjs (id, nome_completo, perfil_yaml) VALUES (?, ?, ?)', pnjs)
        print(f"INFO: {len(pnjs)} PNJs inseridos.")
    
    gabriel_data = load_yaml_file('status_main_character.yml')
    if gabriel_data:
        gabriel_id = gabriel_data['id']
        cursor.execute('INSERT INTO jogador VALUES (?, ?, ?)', (gabriel_id, gabriel_data['personagem_principal'], yaml.dump(gabriel_data, allow_unicode=True)))
        status = gabriel_data['status_atual']
        cursor.execute('INSERT INTO personagem_estado VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (gabriel_id, "setor_lab_atmosferico_4b", status['data_estelar'], status['horario_atual'], status['creditos']['conta_principal'], status['creditos']['pulseira_iip'], status['estado_fisico_emocional']['fome'], status['estado_fisico_emocional']['sede'], status['estado_fisico_emocional']['cansaco'], json.dumps(status['estado_fisico_emocional']['humor'])))
        inventario = [(gabriel_id, item) for item in status['posses']]
        cursor.executemany('INSERT INTO inventario (personagem_id, nome_item) VALUES (?, ?)', inventario)
        habilidades = [(gabriel_id, hab['nome'], tipo.replace('_', ' ').title(), hab['nivel_subnivel'], hab.get('observacoes', '')) for tipo, hab_list in gabriel_data['ficha_habilidades'].items() if tipo in ['habilidades_tecnicas', 'habilidades_cognitivas'] for hab in hab_list]
        cursor.executemany('INSERT INTO habilidades VALUES (NULL, ?, ?, ?, ?, ?)', habilidades)
        conhecimentos = []
        for cat_key, topicos_list in gabriel_data['conhecimentos_aptidoes'].items():
            if isinstance(topicos_list, list):
                for topico in topicos_list:
                    if isinstance(topico, dict): conhecimentos.append((gabriel_id, topico['nome'], cat_key.replace('_', ' ').title(), topico.get('nivel')))
                    else: conhecimentos.append((gabriel_id, topico['nome'], cat_key.replace('_', ' ').title(), None))
        cursor.executemany('INSERT INTO conhecimentos VALUES (NULL, ?, ?, ?, ?)', conhecimentos)
        print("INFO: Dados do jogador (estado, inventário, etc.) inseridos.")

    # --- 2. Popular Entidades do Universo ---

    # CORREÇÃO: Lógica para ler a estrutura hierárquica de locais
    locais_data = load_yaml_file('mapa_universo.yml')
    if locais_data and 'locais' in locais_data:
        all_locais_to_insert = []
        locais_to_process = list(locais_data['locais'])  # Fila de locais a processar

        while locais_to_process:
            current_loc = locais_to_process.pop(0)

            if 'id' in current_loc and 'nome' in current_loc:
                all_locais_to_insert.append((
                    current_loc['id'], current_loc['nome'], current_loc.get('tipo'),
                    current_loc.get('parent_id'), yaml.dump(current_loc, allow_unicode=True)
                ))

            # Procura por sub-listas de locais e adiciona-as à fila
            for key, value in current_loc.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            locais_to_process.append(item)
        
        cursor.executemany('INSERT INTO locais (id, nome, tipo, parent_id, perfil_yaml) VALUES (?, ?, ?, ?, ?)', all_locais_to_insert)
        print(f"INFO: {len(all_locais_to_insert)} locais hierárquicos inseridos.")
        
    # (Lógica para popular Civilizações, Tecnologias, Glossário, e Logs permanece a mesma)
    civilizacoes_data = load_yaml_file('civilizacoes_galacticas.yml')
    if civilizacoes_data and 'civilizacoes_galacticas' in civilizacoes_data:
        civilizacoes = [(c['id'], c['nome'], yaml.dump(c, allow_unicode=True)) for c in civilizacoes_data['civilizacoes_galacticas']]
        cursor.executemany('INSERT INTO civilizacoes (id, nome, perfil_yaml) VALUES (?, ?, ?)', civilizacoes)
        print(f"INFO: {len(civilizacoes)} civilizações inseridas.")

    tec_data = load_yaml_file('conhecimentos_universais.yml')
    if tec_data and 'tecnologias' in tec_data:
        tecnologias = []
        for secao_valor in tec_data['tecnologias'].values():
            if isinstance(secao_valor, dict):
                for sub_secao_valor in secao_valor.values():
                    if isinstance(sub_secao_valor, list):
                        for item in sub_secao_valor:
                            if isinstance(item, dict) and 'id' in item and 'nome' in item:
                                tecnologias.append((item['id'], item['nome'], yaml.dump(item, allow_unicode=True)))
        cursor.executemany('INSERT INTO tecnologias (id, nome, perfil_yaml) VALUES (?, ?, ?)', tecnologias)
        print(f"INFO: {len(tecnologias)} tecnologias inseridas.")
        
    glossario_data = load_yaml_file('termos_glossario.yml')
    if glossario_data and 'glossario' in glossario_data:
        termos = [(t['id'], t['termo'], yaml.dump(t, allow_unicode=True)) for t in glossario_data['glossario']]
        cursor.executemany('INSERT INTO glossario (id, termo, perfil_yaml) VALUES (?, ?, ?)', termos)
        print(f"INFO: {len(termos)} termos do glossário inseridos.")
    
    logs_mem_data = load_yaml_file('logs_memorias.yml')
    if logs_mem_data and 'registro_narrativo' in logs_mem_data:
        data_geral = logs_mem_data['registro_narrativo'].get('data', 'Data Desconhecida')
        resumidos = [(data_geral, e['horario'], e['evento']) for e in logs_mem_data['registro_narrativo']['log_eventos']]
        cursor.executemany('INSERT INTO log_narrativo_resumido (data_estelar, horario, evento) VALUES (?, ?, ?)', resumidos)
        print(f"INFO: {len(resumidos)} eventos de log resumido inseridos.")

    # arquivo_bruto_rpg.yml pode ser adicionado aqui quando estiver disponível.
    
    conn.commit()
    conn.close()
    print("\n--- Construção do Mundo Concluída com Sucesso ---")

if __name__ == '__main__':
    setup_database()
    build_world()
