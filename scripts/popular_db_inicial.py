import sqlite3
import json
import re
import os

# --- Constantes e Caminhos ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'dados_estruturados', 'rpg_data.db')
LORE_DIR = os.path.join(BASE_DIR, 'dados_lore')

# --- Funções de Parsing (O nosso "Extrator de Dados") ---

def parse_fle_from_file(file_path):
    """Lê um ficheiro .md e extrai todos os blocos de dados FLE num dicionário."""
    data = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"AVISO: Ficheiro não encontrado em '{file_path}'")
        return data

    matches = re.findall(r'@(.+?):\s*([\s\S]+?)(?=\n@|\Z)', content)
    for tag_raw, value_raw in matches:
        tag = tag_raw.strip().replace('\\_', '_')
        value = value_raw.strip()

        if tag in data:
            if not isinstance(data[tag], list):
                data[tag] = [data[tag]]
            data[tag].append(value)
        else:
            data[tag] = value
    return data

def parse_personagens_fle(content):
    """
    Parseia um ficheiro de personagens com múltiplos blocos,
    extraindo o perfil e as habilidades de forma separada e estruturada.
    """
    personagens = {}
    # Divide o conteúdo em blocos, cada um começando com @personagem_id
    character_blocks = re.split(r'(?=@personagem_id:)', content)
    
    for block in character_blocks:
        if not block.strip() or not block.startswith('@personagem_id:'):
            continue
        
        # Extrai o ID para usar como chave
        id_match = re.search(r'@personagem_id:\s*(\S+)', block)
        if not id_match:
            continue
        char_id = id_match.group(1).strip()
        
        personagens[char_id] = {'perfil': {}, 'habilidades': []}
        
        # Extrai todas as tags do bloco
        tags = re.findall(r'@(habilidade_personagem_id|.+?):\s*([\s\S]+?)(?=\n@|\Z)', block)
        
        # Separa as habilidades do resto do perfil
        habilidade_blocks = re.split(r'(?=@habilidade_personagem_id:)', block)
        perfil_block = habilidade_blocks[0]
        
        # Parse do Perfil
        perfil_tags = re.findall(r'@(.+?):\s*([\s\S]+?)(?=\n@|\Z)', perfil_block)
        for tag_raw, value_raw in perfil_tags:
            tag = tag_raw.strip().replace('\\_', '_')
            value = value_raw.strip()
            personagens[char_id]['perfil'][tag] = value

        # Parse das Habilidades
        for hab_block_raw in habilidade_blocks[1:]:
            hab_block = "@habilidade_personagem_id:" + hab_block_raw
            hab_data = {}
            hab_tags = re.findall(r'@(.+?):\s*([\s\S]+?)(?=\n@|\Z)', hab_block)
            for tag_raw, value_raw in hab_tags:
                tag = tag_raw.strip().replace('\\_', '_')
                value = value_raw.strip()
                hab_data[tag] = value
            if hab_data:
                personagens[char_id]['habilidades'].append(hab_data)
                
    return personagens

# --- Funções de Inserção no Banco de Dados ---

def popular_base_inicial():
    """Função principal para ler os ficheiros de lore e popular a base de dados."""
    print("--- Iniciando População Inicial da Base de Dados v3 ---")
    
    if not os.path.exists(DB_PATH):
        print(f"ERRO: Base de dados não encontrada em '{DB_PATH}'. Execute 'scripts/configurar_db.py' primeiro.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- 1. Ler e Parsear Ficheiros de Lore ---
    status_data = parse_fle_from_file(os.path.join(LORE_DIR, 'Documento RPG - Estado Atual da Campanha e Log.md'))
    
    personagens_content = ""
    try:
        with open(os.path.join(LORE_DIR, 'Documento RPG - Personagens.md'), 'r', encoding='utf-8') as f:
            personagens_content = f.read()
    except FileNotFoundError:
        print("AVISO: Ficheiro de Personagens não encontrado.")

    personagens_data = parse_personagens_fle(personagens_content)
    
    # --- 2. Popular Tabela `personagem_principal` ---
    gabriel_id = 'gabriel_oliveira'
    if gabriel_id in personagens_data and status_data:
        gabriel_perfil = personagens_data[gabriel_id]['perfil']
        cursor.execute('''
            INSERT OR REPLACE INTO personagem_principal (id, nome, localizacao_atual, humor_atual, creditos_conta, creditos_pulseira)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            gabriel_id,
            gabriel_perfil.get('nome_completo', 'Gabriel Oliveira'),
            status_data.get('local', 'Desconhecido'),
            status_data.get('humor', 'Neutro'),
            int(status_data.get('creditos_conta_principal', 0)),
            int(status_data.get('creditos_pulseira', 0))
        ))
        print(f"INFO: Personagem principal '{gabriel_id}' inserido.")
    else:
        print(f"ERRO: Não foi possível encontrar os dados de '{gabriel_id}' ou do ficheiro de status.")

    # --- 3. Popular Tabela `pnjs` ---
    pnjs_para_inserir = []
    for pnj_id, pnj_full_data in personagens_data.items():
        if pnj_id != gabriel_id:
            pnj_perfil = pnj_full_data['perfil']
            perfil_json = json.dumps(pnj_perfil, ensure_ascii=False, indent=2)
            pnjs_para_inserir.append((
                pnj_id, pnj_perfil.get('nome_completo', pnj_id), None, 0, perfil_json
            ))
    if pnjs_para_inserir:
        cursor.executemany('''
            INSERT OR REPLACE INTO pnjs (id, nome, localizacao_atual, relacionamento_com_pc, perfil_json)
            VALUES (?, ?, ?, ?, ?)
        ''', pnjs_para_inserir)
        print(f"INFO: {len(pnjs_para_inserir)} PNJs inseridos.")

    # --- 4. Popular Tabelas Componentes (Habilidades, Inventário, etc. para Gabriel) ---
    if gabriel_id in personagens_data:
        # Habilidades
        hab_para_inserir = []
        for hab_data in personagens_data[gabriel_id]['habilidades']:
            hab_para_inserir.append((
                gabriel_id,
                hab_data.get('nome_habilidade', 'N/A'),
                hab_data.get('nivel', ''),
                hab_data.get('subnivel', ''),
                hab_data.get('observacoes', '')
            ))
        if hab_para_inserir:
            cursor.executemany('INSERT OR REPLACE INTO habilidades (personagem_id, nome_habilidade, nivel, subnivel, descricao) VALUES (?,?,?,?,?)', hab_para_inserir)
            print(f"INFO: {len(hab_para_inserir)} habilidades inseridas para Gabriel.")

    # Inventário
    if 'posses' in status_data:
        # Regex para encontrar todos os itens de lista que começam com '*' ou '-'
        items = re.findall(r'[\*-]\s*(.+)', status_data['posses'])
        inv_para_inserir = [(gabriel_id, item.strip(), '', 1) for item in items]
        if inv_para_inserir:
            cursor.executemany('INSERT OR REPLACE INTO inventario (personagem_id, nome_item, descricao, quantidade) VALUES (?, ?, ?, ?)', inv_para_inserir)
            print(f"INFO: {len(inv_para_inserir)} itens inseridos no inventário de Gabriel.")

    # Conhecimentos e Aptidões
    conhecimentos_para_inserir = []
    if 'conhecimento' in status_data:
        knowledge_blocks = status_data['conhecimento'] if isinstance(status_data['conhecimento'], list) else [status_data['conhecimento']]
        for block in knowledge_blocks:
            cat = re.search(r'@categoria:\s*(.+)', block)
            top = re.search(r'@topico:\s*(.+)', block)
            niv = re.search(r'@nivel:\s*(\d+)', block)
            if cat and top and niv:
                conhecimentos_para_inserir.append((gabriel_id, cat.group(1).strip(), top.group(1).strip(), int(niv.group(1)), 0))

    if 'aptidao' in status_data:
        aptitude_blocks = status_data['aptidao'] if isinstance(status_data['aptidao'], list) else [status_data['aptidao']]
        for block in aptitude_blocks:
            top = re.search(r'@topico:\s*(.+)', block)
            if top:
                conhecimentos_para_inserir.append((gabriel_id, "Aptidão", top.group(1).strip(), 3, 1))

    if conhecimentos_para_inserir:
        cursor.executemany('INSERT OR REPLACE INTO conhecimentos_aptidoes (personagem_id, categoria, topico, nivel_proficiencia, is_aptidao) VALUES (?,?,?,?,?)', conhecimentos_para_inserir)
        print(f"INFO: {len(conhecimentos_para_inserir)} conhecimentos/aptidões inseridos.")

    # --- Finalizar ---
    conn.commit()
    conn.close()
    print("\nSUCESSO: População inicial da base de dados concluída.")


if __name__ == "__main__":
    popular_base_inicial()

