import sqlite3
import re
import os
import datetime

def parse_and_insert_raw_file_from_md(md_path):
    conn = sqlite3.connect('dados_estruturados/rpg_data.db')
    cursor = conn.cursor()

    # --- Garante que a tabela 'arquivo_bruto' exista ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arquivo_bruto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_estelar TEXT,
            local TEXT,
            personagens TEXT,
            acao TEXT,
            detalhes TEXT,
            emocao TEXT,
            insight TEXT,
            dialogo TEXT,
            timestamp_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit() 

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex para encontrar blocos FLE: Começa com @data\_estelar : e captura tudo
    # até o próximo @data\_estelar : ou o final do documento.
    # O (?m) faz com que ^ e $ correspondam ao início/fim de cada linha
    entry_pattern = r'(?m)^@data\\_estelar\s*:\s*(.*?)(?=(?:^@data\\_estelar\s*:)|(?:\Z))'
    
    fle_entries_raw = re.findall(entry_pattern, content, re.MULTILINE | re.DOTALL)

    tag_mapping = {
        'data\\_estelar': 'data_estelar',
        'local': 'local',
        'personagens': 'personagens',
        'acao': 'acao',
        'detalhes': 'detalhes',
        'emocao': 'emocao',
        'insight': 'insight',
        'dialogo': 'dialogo'
    }

    for entry_text_raw in fle_entries_raw:
        data = {}

        initial_data_estelar_match = re.match(r'^(.*?)(?=@|\Z)', entry_text_raw.strip(), re.DOTALL)
        initial_data_estelar_value = initial_data_estelar_match.group(1).strip() if initial_data_estelar_match else ""
        
        # Limpeza da barra invertida na data estelar
        data['data_estelar'] = initial_data_estelar_value.replace(r'\~', '~').replace(r'\-', '-')

        remaining_entry_text_start_index = len(initial_data_estelar_value)
        remaining_entry_text = entry_text_raw.strip()[remaining_entry_text_start_index:].strip()

        # Adiciona um marcador final para garantir que a última tag seja capturada corretamente
        clean_remaining_entry_text = remaining_entry_text.replace(r'\_', '_').strip()
        clean_remaining_entry_text += ' @END_OF_ENTRY_MARKER:' 

        # Cria um padrão de lookahead para *qualquer uma* das tags (limpas)
        all_clean_tags_lookahead = '|'.join([re.escape(t.replace(r'\_', '_')) for t in tag_mapping.keys()])
        
        for original_md_tag, db_column in tag_mapping.items():
            if original_md_tag == 'data\\_estelar':
                continue

            clean_md_tag = original_md_tag.replace(r'\_', '_')
            
            # Regex para casar com a tag e seu conteúdo até a próxima '@' ou o marcador de fim.
            tag_content_pattern = r'@' + re.escape(clean_md_tag) + r'\s*:\s*(.*?)(?=\s*@(?:' + all_clean_tags_lookahead + r')\s*:|\s*@END_OF_ENTRY_MARKER:|\Z)'
            
            tag_content_match = re.search(tag_content_pattern, clean_remaining_entry_text, re.MULTILINE | re.DOTALL)
            
            if tag_content_match:
                value = tag_content_match.group(1).strip()
                # Aplica a limpeza de barras invertidas para todos os valores extraídos
                value = value.replace(r'\~', '~').replace(r'\-', '-')
                data[db_column] = value
            else:
                data[db_column] = ""

        # Adiciona o timestamp de registro (pode ser removido se o DB tiver DEFAULT CURRENT_TIMESTAMP)
        timestamp = datetime.datetime.now().isoformat() 

        insert_data = (
            data.get('data_estelar', ''),
            data.get('local', ''),
            data.get('personagens', ''),
            data.get('acao', ''),
            data.get('detalhes', ''),
            data.get('emocao', ''),
            data.get('insight', ''),
            data.get('dialogo', '')
        )
        
        cursor.execute("INSERT INTO arquivo_bruto (data_estelar, local, personagens, acao, detalhes, emocao, insight, dialogo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", insert_data)
        
    conn.commit()
    conn.close()
    print(f"Dados de {md_path} inseridos no banco de dados 'arquivo_bruto'.")

if __name__ == "__main__":
    md_arquivo_bruto_file = "documentos_rpg_md/Documento RPG - Arquivo Bruto 11-06-2325.md"
    
    from configurar_db_sqlite import setup_database
    setup_database()

    parse_and_insert_raw_file_from_md(md_arquivo_bruto_file)
