import sqlite3
import json
import re
import os
from markdown_it import MarkdownIt

def populate_characters_and_skills_from_md(md_personagens_path, md_status_path):
    """
    Script v3.0 para popular personagens e habilidades de documentos Markdown.
    Utiliza markdown-it-py para parsing mais robusto do Markdown.
    Assume que o Documento RPG - Personagens.md está em formato FLE com underscores escapados (\\_).
    """
    conn = sqlite3.connect('dados_estruturados/rpg_data.db')
    cursor = conn.cursor()

    # Inicializa o parser de Markdown
    md = MarkdownIt()

    try:
        with open(md_personagens_path, 'r', encoding='utf-8') as f:
            personagens_content = f.read()
        print(f"DEBUG: Conteúdo do arquivo '{md_personagens_path}' lido com sucesso. Tamanho: {len(personagens_content)} caracteres.")
    except FileNotFoundError:
        print(f"ERRO: Arquivo de personagens '{md_personagens_path}' não foi encontrado.")
        conn.close()
        return

    # Parseia o documento Markdown
    tokens = md.parse(personagens_content)

    # Dicionários temporários para armazenar dados de personagens e habilidades
    current_character_data = {}
    all_characters_data = {} # Para armazenar todos os perfis de personagem
    all_skills_data = []     # Para armazenar todas as habilidades

    # Definição dos mapeamentos de tags no início da função
    personagem_tag_mapping = {
        # Adicione mapeamentos se os nomes das tags no MD
        # forem diferentes dos campos no perfil_json ou colunas do DB.
        # Ex: 'nome_completo': 'nome'
        # Por enquanto, se não houver mapeamento, o nome da tag original será usado.
    }
    habilidade_tag_mapping = {
        'habilidade_personagem_id': 'personagem_id',
        'nome_habilidade': 'nome_habilidade',
        'nivel': 'nivel',
        'subnivel': 'subnivel',
        'observacoes': 'descricao' # Mapeia 'observacoes' do FLE para 'descricao' no DB
    }

    # Regex para extrair tags FLE e seus valores, lidando com underscores escapados (\_)
    # Pega "@tag_name:" e o conteúdo até a próxima "@" ou o final da string.
    # O `re.escape(tag.replace('_', '\\_'))` lida com o escape do underscore na tag.
    tag_value_regex = re.compile(r'@([a-zA-Z0-9\_]+?):\s*([\s\S]+?)(?=\n@|\Z)')

    # Variável para controlar qual tipo de bloco estamos parseando (personagem ou habilidade)
    # 0: Nenhum, 1: Personagem, 2: Habilidade
    parsing_block_type = 0 
    
    # Itera sobre os tokens do Markdown para encontrar nossos blocos FLE
    for token in tokens:
        if token.type == 'paragraph' or token.type == 'list_item':
            # print(f"DEBUG: Processando token de tipo: {token.type}, Conteúdo: '{token.content[:100]}...'")
            
            # Limpa o conteúdo para remover escapes de Markdown antes de aplicar a regex
            clean_content = token.content.replace('\\_', '_').replace('\\~', '~').replace('\\-', '-')

            # Tenta encontrar o marcador de início de um bloco de personagem
            if clean_content.startswith('personagem_id:'):
                if current_character_data: # Salva o anterior se houver
                    all_characters_data[current_character_data['id']] = current_character_data
                current_character_data = {'id': clean_content.split(':', 1)[1].strip()}
                parsing_block_type = 1 # Estamos em um bloco de personagem
                continue # Já pegamos o ID, vai para o próximo token

            # Tenta encontrar o marcador de início de um bloco de habilidade
            elif clean_content.startswith('habilidade_personagem_id:'):
                if current_character_data and parsing_block_type == 1: # Salva o último personagem completo
                     all_characters_data[current_character_data['id']] = current_character_data
                
                # Inicia um novo bloco de habilidade
                current_skill_data = {'personagem_id': clean_content.split(':', 1)[1].strip()}
                all_skills_data.append(current_skill_data)
                parsing_block_type = 2 # Estamos em um bloco de habilidade
                continue # Já pegamos o ID, vai para o próximo token

            # Se estamos em um bloco de personagem, extrai os campos
            if parsing_block_type == 1:
                # Regex para pegar tags do tipo @tag: valor
                matches = tag_value_regex.findall(token.content) # Usa o token.content original para a regex
                for tag_name_raw, tag_value_raw in matches:
                    tag_name = tag_name_raw.replace('\\_', '_') # Remove o escape do underscore no nome da tag
                    tag_value = tag_value_raw.strip().replace('\\~', '~').replace('\\-', '-') # Limpa o valor

                    # Mapeia para o nome da coluna do banco de dados, se aplicável
                    db_column_name = personagem_tag_mapping.get(tag_name, tag_name)
                    current_character_data[db_column_name] = tag_value
                
            # Se estamos em um bloco de habilidade, extrai os campos
            elif parsing_block_type == 2 and all_skills_data:
                # Regex para pegar tags do tipo @tag: valor
                matches = tag_value_regex.findall(token.content) # Usa o token.content original para a regex
                for tag_name_raw, tag_value_raw in matches:
                    tag_name = tag_name_raw.replace('\\_', '_') # Remove o escape do underscore no nome da tag
                    tag_value = tag_value_raw.strip().replace('\\~', '~').replace('\\-', '-') # Limpa o valor

                    # Mapeia para o nome da coluna do banco de dados, se aplicável
                    db_column_name = habilidade_tag_mapping.get(tag_name, tag_name)
                    all_skills_data[-1][db_column_name] = tag_value # Adiciona ao último item de habilidade

    # Garante que o último bloco parseado (seja personagem ou habilidade) seja salvo
    if current_character_data and parsing_block_type == 1:
        all_characters_data[current_character_data['id']] = current_character_data
    
    print(f"DEBUG: Dados de todos os personagens parseados: {len(all_characters_data)} personagens.")
    print(f"DEBUG: Dados de todas as habilidades parseadas: {len(all_skills_data)} habilidades.")


    # --- Inserir/Atualizar Personagens no DB ---
    for char_id, profile_data in all_characters_data.items():
        char_name = profile_data.get('nome', char_id)
        perfil_json = json.dumps(profile_data, ensure_ascii=False)
        status_json = None # Padrão para PNJs

        # Se for Gabriel, extrair o Status Atual (do Documento RPG - Estado Atual da Campanha e Log.md)
        if char_id == "gabriel_oliveira":
            print("DEBUG: Processando status para Gabriel Oliveira.")
            gabriel_status = {}
            try:
                with open(md_status_path, 'r', encoding='utf-8') as f_status:
                    status_md = f_status.read()
                
                # Adapte esta regex se o formato do seu documento de status mudar para FLE também.
                # Esta regex atual está configurada para o formato Markdown/texto puro que você tinha antes.
                status_lines = re.findall(
                    r'^(Local|Data Estelar|Horário Atual|Cargo|Posses|Créditos|Autorização|Estado Físico e Emocional|Fome|Sede|Cansaço|Humor|Motivação|Conhecimentos e Aptidões Adquiridas|Conhecimento de Mundo \(Lore\)|Habilidades e Aptidões Técnicas|Habilidades Cognitivas|Aptidão com Máquinas|Aptidão com Combate|Aptidão Social|Aptidão Psíquica|Conhecimentos Adquiridos):\s*([\s\S]+?)(?=\n[A-Z][a-z\s]+\s*:|\Z)',
                    status_md, re.MULTILINE | re.DOTALL
                )
                print(f"DEBUG: Encontrados {len(status_lines)} campos de status no documento de status.")
                for key, value in status_lines:
                    key_clean = key.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("\\", "")
                    value_clean = value.strip().replace('\\~', '~').replace('\\-', '-')
                    
                    if key_clean == "posses":
                        gabriel_status[key_clean] = [item.strip() for item in re.findall(r'^[*-]\s*(.+)', value_clean, re.MULTILINE)]
                    elif key_clean == "creditos":
                        main_credit = re.search(r'Conta Principal:\s*(\d+)', value_clean)
                        pulseira_credit = re.search(r'Pulseira \(IIP\):\s*(\d+)', value_clean)
                        gabriel_status[key_clean] = {
                            "principal": int(main_credit.group(1)) if main_credit else 0,
                            "pulseira": int(pulseira_credit.group(1)) if pulseira_credit else 0
                        }
                    elif key_clean in ["conhecimentos_e_aptidoes_adquiridas", "conhecimento_de_mundo_lore", "habilidades_e_aptidoes_tecnicas", "habilidades_cognitivas", "aptidao_com_maquinas", "aptidao_com_combate", "aptidao_social", "aptidao_psiquica", "conhecimentos_adquiridos"]:
                        list_items = re.findall(r'^[*-]\s*(.+)', value_clean, re.MULTILINE)
                        if list_items:
                            gabriel_status[key_clean] = [item.strip() for item in list_items]
                        else:
                            gabriel_status[key_clean] = value_clean
                    else:
                        gabriel_status[key_clean] = value_clean
                
                status_json = json.dumps(gabriel_status, ensure_ascii=False)
                print(f"DEBUG: status_json para Gabriel: {status_json[:200]}...")
            except FileNotFoundError:
                print(f"AVISO: Arquivo de status '{md_status_path}' não encontrado. Status de Gabriel não populado.")
        
        cursor.execute(
            "INSERT OR REPLACE INTO personagens (id, nome, perfil_json, status_json) VALUES (?, ?, ?, ?)",
            (char_id, char_name, perfil_json, status_json)
        )
        print(f"DEBUG: Personagem '{char_name}' (ID: {char_id}) inserido/atualizado na tabela 'personagens'.")
    
    # --- Processar Blocos de Habilidades (@habilidade_personagem_id) ---
    print("\nDEBUG: --- Iniciando processamento de habilidades ---")
    # Limpa todas as habilidades existentes antes de inserir as novas.
    # Se desejar limpar apenas de um personagem específico, ajuste o WHERE.
    cursor.execute("DELETE FROM habilidades")
    print("DEBUG: Tabela 'habilidades' limpa para reinserção.")
    
    for i, skill_data in enumerate(all_skills_data):
        personagem_id_habilidade = skill_data.get('personagem_id')
        nome_habilidade_val = skill_data.get('nome_habilidade')

        if not nome_habilidade_val:
            print(f"AVISO: Habilidade para personagem_id '{personagem_id_habilidade}' (Bloco {i+1}) ignorada por falta de 'nome_habilidade'. Dados do bloco: {skill_data}")
            continue

        print(f"DEBUG: Inserindo Habilidade {i+1}: {nome_habilidade_val} para {personagem_id_habilidade}")
        try:
            cursor.execute(
                "INSERT INTO habilidades (personagem_id, nome_habilidade, nivel, subnivel, descricao) VALUES (?, ?, ?, ?, ?)",
                (personagem_id_habilidade,
                 nome_habilidade_val,
                 skill_data.get('nivel', ''),
                 skill_data.get('subnivel', ''),
                 skill_data.get('descricao', ''))
            )
            print(f"DEBUG: Habilidade '{nome_habilidade_val}' inserida para '{personagem_id_habilidade}'.")
        except sqlite3.IntegrityError as e:
            print(f"ERRO ao inserir habilidade '{nome_habilidade_val}' para '{personagem_id_habilidade}': {e}. Dados: {skill_data}")


    conn.commit()
    conn.close()
    print("\nDEBUG: Dados de personagens e habilidades populados com sucesso.")

if __name__ == "__main__":
    from configurar_db_sqlite import setup_database
    
    md_personagens_file = "documentos_rpg_md/Documento RPG - Personagens.md"
    md_status_file = "documentos_rpg_md/Documento RPG - Estado Atual da Campanha e Log.md" # Caminho para o documento de status de Gabriel

    print("Configurando banco de dados...")
    setup_database()
    
    print("\nPopulando dados dos personagens e habilidades (usando parser de Markdown)...")
    populate_characters_and_skills_from_md(md_personagens_file, md_status_file)
