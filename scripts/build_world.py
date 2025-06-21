import yaml
import sqlite3
import os
import json

# --- Configuração de Caminhos ---
# Mantém a mesma estrutura de pastas que você definiu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Assumindo que o script está em /scripts, volta um nível para a raiz do projeto
PROJECT_ROOT = os.path.dirname(BASE_DIR) 
LORE_SOURCE_DIR = os.path.join(PROJECT_ROOT, 'lore_fonte')
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

def setup_database():
    """Cria a estrutura completa da base de dados relacional (SQLite)."""
    # Cria o diretório de produção se ele não existir
    os.makedirs(PROD_DATA_DIR, exist_ok=True)
    # Remove a base de dados antiga para garantir uma construção limpa
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tabela para Entidades Canónicas (Personagens) ---
    # Armazena o perfil completo em YAML para flexibilidade futura.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personagens (
            id TEXT PRIMARY KEY,
            nome_completo TEXT NOT NULL,
            tipo TEXT,
            perfil_yaml TEXT
        )
    ''')

    # Adicionar aqui tabelas para outras entidades canónicas (locais, tecnologias) no futuro.

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
            humor TEXT,
            FOREIGN KEY (personagem_id) REFERENCES personagens(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            nome_item TEXT NOT NULL,
            quantidade INTEGER DEFAULT 1,
            FOREIGN KEY (personagem_id) REFERENCES personagens(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habilidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            nome_habilidade TEXT NOT NULL,
            tipo TEXT,
            nivel TEXT,
            observacoes TEXT,
            UNIQUE(personagem_id, nome_habilidade),
            FOREIGN KEY (personagem_id) REFERENCES personagens(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conhecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personagem_id TEXT NOT NULL,
            topico TEXT NOT NULL,
            categoria TEXT,
            nivel_proficiencia INTEGER,
            UNIQUE(personagem_id, topico),
            FOREIGN KEY (personagem_id) REFERENCES personagens(id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"SUCESSO: Base de dados configurada em '{DB_PATH}'.")

def load_yaml_file(file_path):
    """Carrega um ficheiro YAML de forma segura e retorna os seus dados."""
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

    # --- 1. Processar Personagens (Fonte Canónica) ---
    personagens_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'personagens.yml'))
    if personagens_data and 'personagens' in personagens_data:
        personagens_para_inserir = []
        habilidades_para_inserir = []

        for p_data in personagens_data['personagens']:
            # Adiciona o personagem à lista para inserção na tabela 'personagens'
            personagens_para_inserir.append(
                (p_data['id'], p_data['nome'], p_data['tipo'], yaml.dump(p_data))
            )
            
            # Se o personagem for o Gabriel, extrai as suas habilidades para a tabela 'habilidades'
            if p_data['id'] == 'gabriel_oliveira' and 'ficha_habilidades' in p_data:
                for tipo, hab_list in p_data['ficha_habilidades'].items():
                    for hab in hab_list:
                        habilidades_para_inserir.append(
                            (p_data['id'], hab['nome'], tipo, hab['nivel'], hab.get('observacoes', ''))
                        )

        cursor.executemany(
            'INSERT INTO personagens (id, nome_completo, tipo, perfil_yaml) VALUES (?, ?, ?, ?)', 
            personagens_para_inserir
        )
        cursor.executemany(
            'INSERT INTO habilidades (personagem_id, nome_habilidade, tipo, nivel, observacoes) VALUES (?, ?, ?, ?, ?)',
            habilidades_para_inserir
        )
        print(f"INFO: {len(personagens_para_inserir)} personagens e {len(habilidades_para_inserir)} habilidades canónicas inseridas.")

    # --- 2. Processar Estado Inicial do Jogador e Lore Adicional ---
    # Usando o seu 'status_atual_campanha_log.yml' como fonte para o estado inicial
    estado_data = load_yaml_file(os.path.join(LORE_SOURCE_DIR, 'status_atual_campanha_log.yml'))
    if estado_data:
        char_id = 'gabriel_oliveira' # ID fixo para o jogador
        status = estado_data['status_gabriel']
        
        # Insere o estado dinâmico na tabela 'personagem_estado'
        cursor.execute('''
            INSERT INTO personagem_estado (personagem_id, localizacao_atual_id, data_estelar, horario_atual, creditos_conta_principal, creditos_pulseira_iip, fome, sede, cansaco, humor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            char_id,
            status['local'], # Idealmente, este seria um ID como 'laboratorio_4b'
            status['data_estelar'],
            status['horario_atual'],
            status['creditos']['conta_principal'],
            status['creditos']['pulseira_iip'],
            status['estado_fisico_emocional']['fome'],
            status['estado_fisico_emocional']['sede'],
            status['estado_fisico_emocional']['cansaco'],
            status['estado_fisico_emocional']['humor']
        ))
        print(f"INFO: Estado inicial do jogador '{char_id}' inserido.")

        # Inventário Inicial
        inventario_para_inserir = [(char_id, item) for item in status['posses']]
        cursor.executemany('INSERT INTO inventario (personagem_id, nome_item) VALUES (?, ?)', inventario_para_inserir)
        print(f"INFO: {len(inventario_para_inserir)} itens inseridos no inventário inicial.")

        # Conhecimentos Iniciais
        conhecimentos_para_inserir = []
        for cat, topicos in estado_data['conhecimentos_e_aptidoes_adquiridas'].items():
            if isinstance(topicos, list):
                 for topico_data in topicos:
                    if isinstance(topico_data, dict):
                        conhecimentos_para_inserir.append(
                            (char_id, topico_data['topico'], cat, topico_data['nivel'])
                        )

        cursor.executemany(
            'INSERT INTO conhecimentos (personagem_id, topico, categoria, nivel_proficiencia) VALUES (?, ?, ?, ?)',
            conhecimentos_para_inserir
        )
        print(f"INFO: {len(conhecimentos_para_inserir)} conhecimentos inseridos.")

    conn.commit()
    conn.close()
    print("\n--- Construção do Mundo Concluída ---")


if __name__ == '__main__':
    # Roda as duas funções em sequência
    setup_database()
    build_world()
