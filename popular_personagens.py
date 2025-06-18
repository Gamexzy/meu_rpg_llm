import sqlite3
import json
import re
import os

def clean_db_before_population(cursor, personagem_id):
    """Limpa os dados antigos de um personagem antes de reinserir."""
    cursor.execute("DELETE FROM inventario WHERE personagem_id = ?", (personagem_id,))
    cursor.execute("DELETE FROM conhecimentos_aptidoes WHERE personagem_id = ?", (personagem_id,))
    print(f"DEBUG: Dados antigos de inventário e conhecimentos para '{personagem_id}' foram limpos.")

def parse_fle_file_to_dict(file_path):
    """
    Lê um ficheiro .md formatado com FLE e converte as tags para um dicionário.
    Tags duplicadas (como @conhecimento) são transformadas numa lista de valores.
    """
    data = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"AVISO: Ficheiro '{file_path}' não encontrado.")
        return data

    # Regex para encontrar todas as tags @tag: valor
    matches = re.findall(r'@(.+?):\s*([\s\S]+?)(?=\n@|\Z)', content)
    for tag_raw, value_raw in matches:
        tag = tag_raw.strip()
        value = value_raw.strip()
        if tag in data:
            if not isinstance(data[tag], list):
                data[tag] = [data[tag]]
            data[tag].append(value)
        else:
            data[tag] = value
    return data

def populate_database(md_personagens_path, md_status_path):
    """
    Script v6.0 que popula a base de dados lendo o formato FLE de todos os ficheiros de dados.
    Lógica de parsing de conhecimentos e aptidões corrigida.
    """
    conn = sqlite3.connect('dados_estruturados/rpg_data.db')
    cursor = conn.cursor()

    personagens_data = parse_fle_file_to_dict(md_personagens_path)
    status_data = parse_fle_file_to_dict(md_status_path)

    gabriel_id = "gabriel_oliveira"
    clean_db_before_population(cursor, gabriel_id)

    # --- Popula a tabela 'personagens' ---
    cursor.execute(
        "INSERT OR REPLACE INTO personagens (id, nome, localizacao_atual, humor_atual, perfil_json, status_json) VALUES (?, ?, ?, ?, ?, ?)",
        (
            gabriel_id,
            personagens_data.get('nome_completo', 'Gabriel Oliveira'),
            status_data.get('local', ''),
            status_data.get('humor', ''),
            json.dumps({k: v for k, v in personagens_data.items() if k != 'personagem_id'}, ensure_ascii=False),
            json.dumps({k: v for k, v in status_data.items() if k not in ['local', 'humor', 'posses', 'conhecimento', 'aptidao']}, ensure_ascii=False)
        )
    )
    print("INFO: Tabela 'personagens' populada.")

    # --- Popula a tabela 'inventario' ---
    if 'posses' in status_data:
        items_text = status_data['posses']
        # Regex para encontrar itens de lista, lidando com o primeiro item
        items = re.findall(r'-\s*(.+)', items_text)
        inventario_para_inserir = [(gabriel_id, item.strip(), '', 1) for item in items]
        cursor.executemany("INSERT INTO inventario (personagem_id, nome_item, descricao, quantidade) VALUES (?, ?, ?, ?)", inventario_para_inserir)
        print(f"INFO: Tabela 'inventario' populada com {len(inventario_para_inserir)} itens.")

    # --- Popula a tabela 'conhecimentos_aptidoes' ---
    conhecimentos_para_inserir = []
    
    # Processa os Conhecimentos
    if 'conhecimento' in status_data:
        knowledge_blocks = status_data['conhecimento']
        if not isinstance(knowledge_blocks, list):
            knowledge_blocks = [knowledge_blocks]  # Garante que seja uma lista

        for block in knowledge_blocks:
            categoria_match = re.search(r'@categoria:\s*(.+)', block)
            topico_match = re.search(r'@topico:\s*(.+)', block)
            nivel_match = re.search(r'@nivel:\s*(\d+)', block)
            
            if categoria_match and topico_match and nivel_match:
                conhecimentos_para_inserir.append(
                    (gabriel_id, categoria_match.group(1).strip(), topico_match.group(1).strip(), int(nivel_match.group(1)), 0)
                )

    # Processa as Aptidões
    if 'aptidao' in status_data:
        aptitude_blocks = status_data['aptidao']
        if not isinstance(aptitude_blocks, list):
            aptitude_blocks = [aptitude_blocks] # Garante que seja uma lista
        
        for block in aptitude_blocks:
            topico_match = re.search(r'@topico:\s*(.+)', block)
            if topico_match:
                # Aptidões são consideradas conhecimento de nível 3 por definição
                conhecimentos_para_inserir.append(
                    (gabriel_id, "Aptidão", topico_match.group(1).strip(), 3, 1)
                )

    if conhecimentos_para_inserir:
        cursor.executemany("INSERT OR REPLACE INTO conhecimentos_aptidoes (personagem_id, categoria, topico, nivel_proficiencia, is_aptidao) VALUES (?, ?, ?, ?, ?)", conhecimentos_para_inserir)
        print(f"INFO: Tabela 'conhecimentos_aptidoes' populada com {len(conhecimentos_para_inserir)} registos.")
    else:
        print("AVISO: Nenhum conhecimento ou aptidão foi encontrado para popular.")

    conn.commit()
    conn.close()
    print("\nSUCESSO: Base de dados populada a partir de ficheiros FLE padronizados.")


if __name__ == "__main__":
    md_personagens_file = "documentos_rpg_md/Documento RPG - Personagens.md"
    md_status_file = "documentos_rpg_md/Documento RPG - Estado Atual da Campanha e Log.md"

    print("\n--- Populando Dados a partir de Ficheiros FLE (v6.0) ---")
    populate_database(md_personagens_file, md_status_file)
