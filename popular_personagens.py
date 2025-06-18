import sqlite3
import json
import re
import os

def populate_characters_and_skills(md_personagens_path, md_status_path):
    """
    Script v2.0 para popular personagens e habilidades de documentos Markdown.
    Utiliza uma abordagem de parsing baseada em regex otimizada para o Formato de Log Estruturado (FLE).
    Este método é mais robusto para a estrutura de arquivo atual.
    """
    conn = sqlite3.connect('dados_estruturados/rpg_data.db')
    cursor = conn.cursor()

    try:
        with open(md_personagens_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"DEBUG: Conteúdo do arquivo '{md_personagens_path}' lido com sucesso.")
    except FileNotFoundError:
        print(f"ERRO: Arquivo de personagens '{md_personagens_path}' não foi encontrado.")
        conn.close()
        return

    # Regex para dividir o documento em blocos de personagem.
    # A expressão `(?=@personagem\_id:)` divide o texto ANTES de cada ocorrência de `@personagem_id:`, mantendo o delimitador.
    character_blocks = re.split(r'(?=@personagem\\_id:)', content)
    
    all_characters_data = {}
    all_skills_data = []

    for block in character_blocks:
        if not block.strip():
            continue

        # Divide o bloco do personagem entre o perfil e as habilidades
        # A expressão `(?=@habilidade\_personagem\_id:)` divide no início do primeiro bloco de habilidade.
        parts = re.split(r'(?=@habilidade\\_personagem\\_id:)', block, maxsplit=1)
        profile_text = parts[0]
        # Se houver habilidades, o resto do bloco é skills_text
        skills_text = parts[1] if len(parts) > 1 else ""

        # --- Parse do Perfil ---
        # Regex para encontrar todas as tags no formato @tag: valor
        profile_tags = re.findall(r'@(.+?):\s*([\s\S]*?)(?=\n@|\Z)', profile_text)
        
        current_profile = {}
        char_id = ""
        for tag_raw, value_raw in profile_tags:
            # Limpa a tag e o valor
            tag = tag_raw.replace('\\_', '_').strip()
            value = value_raw.strip()
            
            if tag == 'personagem_id':
                char_id = value
            current_profile[tag] = value
        
        if not char_id:
            continue
            
        all_characters_data[char_id] = current_profile

        # --- Parse das Habilidades ---
        if skills_text:
            # Adiciona o delimitador de volta para que o primeiro bloco de habilidade seja capturado
            full_skills_text = "@habilidade\\_personagem\\_id:" + skills_text
            skill_blocks_text = re.split(r'(?=@habilidade\\_personagem\\_id:)', full_skills_text)

            for skill_block in skill_blocks_text:
                if not skill_block.strip():
                    continue

                skill_tags_raw = re.findall(r'@(.+?):\s*([\s\S]*?)(?=\n@|\Z)', skill_block)
                current_skill = {}
                for tag_raw, value_raw in skill_tags_raw:
                    tag = tag_raw.replace('\\_', '_').strip()
                    value = value_raw.strip()
                    current_skill[tag] = value
                
                # Garante que a habilidade seja válida e pertença ao personagem atual
                if 'nome_habilidade' in current_skill and current_skill.get('habilidade_personagem_id') == char_id:
                    all_skills_data.append(current_skill)

    print(f"DEBUG: Dados de todos os personagens parseados: {len(all_characters_data)} personagens encontrados.")
    print(f"DEBUG: Dados de todas as habilidades parseadas: {len(all_skills_data)} habilidades encontradas.")

    # --- Inserir/Atualizar Personagens no DB ---
    for char_id, profile_data in all_characters_data.items():
        char_name = profile_data.get('nome_completo', char_id)
        perfil_json = json.dumps(profile_data, ensure_ascii=False, indent=2)
        status_json = "" # Padrão para PNJs

        if char_id == "gabriel_oliveira":
            print("DEBUG: Processando status para Gabriel Oliveira.")
            gabriel_status_data = {}
            try:
                with open(md_status_path, 'r', encoding='utf-8') as f_status:
                    status_md = f_status.read()
                
                status_lines = re.findall(
                    r'^(Local|Data Estelar|Horário Atual|Cargo|Posses|Créditos|Autorização|Estado Físico e Emocional|Fome|Sede|Cansaço|Humor|Motivação|Conhecimentos e Aptidões Adquiridas|Conhecimento de Mundo \(Lore\)|Habilidades e Aptidões Técnicas|Habilidades Cognitivas|Aptidão com Máquinas|Aptidão com Combate|Aptidão Social|Aptidão Psíquica|Conhecimentos Adquiridos):\s*([\s\S]+?)(?=\n[A-Z][a-z\s]+\s*:|\Z)',
                    status_md, re.MULTILINE
                )
                
                for key, value in status_lines:
                    key_clean = key.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("\\", "")
                    value_clean = value.strip()
                    gabriel_status_data[key_clean] = value_clean # Simplificando para guardar o texto bruto por enquanto
                
                status_json = json.dumps(gabriel_status_data, ensure_ascii=False, indent=2)
                print(f"DEBUG: status_json para Gabriel gerado.")
            except FileNotFoundError:
                print(f"AVISO: Arquivo de status '{md_status_path}' não encontrado. Status de Gabriel não populado.")
            except Exception as e:
                print(f"ERRO ao processar o status de Gabriel: {e}")

        cursor.execute(
            "INSERT OR REPLACE INTO personagens (id, nome, perfil_json, status_json) VALUES (?, ?, ?, ?)",
            (char_id, char_name, perfil_json, status_json)
        )
        print(f"DEBUG: Personagem '{char_name}' (ID: {char_id}) inserido/atualizado na tabela 'personagens'.")

    # --- Inserir/Atualizar Habilidades no DB ---
    print("\nDEBUG: --- Iniciando processamento de habilidades ---")
    cursor.execute("DELETE FROM habilidades")
    print("DEBUG: Tabela 'habilidades' limpa para reinserção.")
    
    habilidades_para_inserir = []
    for skill_data in all_skills_data:
        # A coluna no DB é 'descricao', mas no MD é 'observacoes'
        descricao = skill_data.get('observacoes', '') 
        
        habilidades_para_inserir.append((
            skill_data.get('habilidade_personagem_id'),
            skill_data.get('nome_habilidade'),
            skill_data.get('nivel'),
            skill_data.get('subnivel'),
            descricao
        ))

    cursor.executemany(
        "INSERT OR REPLACE INTO habilidades (personagem_id, nome_habilidade, nivel, subnivel, descricao) VALUES (?, ?, ?, ?, ?)",
        habilidades_para_inserir
    )
    print(f"DEBUG: {len(habilidades_para_inserir)} habilidades inseridas/atualizadas na tabela 'habilidades'.")

    conn.commit()
    conn.close()
    print("\nSUCESSO: Dados de personagens e habilidades populados no banco de dados.")

if __name__ == "__main__":
    from configurar_db_sqlite import setup_database
    
    md_personagens_file = "documentos_rpg_md/Documento RPG - Personagens.md"
    md_status_file = "documentos_rpg_md/Documento RPG - Estado Atual da Campanha e Log.md"

    print("--- Fase 1: Configurando o Banco de Dados ---")
    setup_database()
    
    print("\n--- Fase 2: Populando Dados dos Personagens e Habilidades ---")
    populate_characters_and_skills(md_personagens_file, md_status_file)
