import sqlite3
import json
import os

# --- Constantes e Caminhos ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'dados_estruturados', 'rpg_data.db')
# Sugestão: Manter os ficheiros .md na mesma pasta, mas garantir que todos sigam o novo formato.
LORE_DIR = os.path.join(BASE_DIR, 'dados_lore') 

def parse_fle_v2(file_path):
    """
    Novo parser para o Formato de Log Estruturado v1.0, que lida
    com aninhamento e agrupamento por indentação.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"ERRO: Ficheiro não encontrado em '{file_path}'")
        return None

    data = {'personagens': []} # Estrutura de topo
    # Mantém o registo do contexto atual (onde estamos a adicionar dados)
    context_stack = [data]

    for line in lines:
        line = line.rstrip('\n') # Remove quebras de linha
        if not line.strip():
            continue

        # Calcula o nível de indentação
        indentation = len(line) - len(line.lstrip(' '))
        
        # Extrai a tag e o valor
        tag, _, value = line.strip().partition(':')
        tag = tag.replace('@', '', 1) # Remove o '@' inicial
        value = value.strip()

        # Ajusta o contexto com base na indentação
        while indentation < (len(context_stack) - 1) * 2:
            context_stack.pop()
        
        current_context = context_stack[-1]

        # Lida com tags de agrupamento (que não têm valor na mesma linha)
        if not value:
            # Caso especial para personagens e habilidades, que são listas
            if tag in ['personagem', 'habilidade']:
                if tag+'s' not in current_context:
                    current_context[tag+'s'] = []
                new_context = {}
                current_context[tag+'s'].append(new_context)
                context_stack.append(new_context)
            else: # Para outros agrupamentos futuros
                new_context = {}
                current_context[tag] = new_context
                context_stack.append(new_context)
        else:
            # Atribui o valor da tag ao contexto atual
            current_context[tag] = value
             
    return data

def popular_base_fle_v2():
    """
    Função principal para popular a base de dados usando o novo parser FLE v2.
    """
    print("--- Iniciando População da Base de Dados com FLE v2 ---")
    
    if not os.path.exists(DB_PATH):
        print(f"ERRO: Base de dados não encontrada. Execute 'configurar_db.py' primeiro.")
        return

    # Lê o novo ficheiro de personagens
    # Assumindo que o ficheiro 'Documento RPG - Personagens.md' foi atualizado para o novo formato
    parsed_data = parse_fle_v2(os.path.join(LORE_DIR, 'Documento RPG - Personagens.md'))
    if not parsed_data:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Limpa as tabelas para evitar dados duplicados
    print("INFO: A limpar tabelas existentes...")
    cursor.execute('DELETE FROM personagem_principal')
    cursor.execute('DELETE FROM pnjs')
    cursor.execute('DELETE FROM habilidades')
    # Pode adicionar a limpeza de outras tabelas aqui se elas também vierem de ficheiros FLE

    # --- Popular as tabelas ---
    gabriel_id = 'gabriel_oliveira'
    personagens = parsed_data.get('personagens', [])
    
    pnjs_para_inserir = []

    print(f"INFO: {len(personagens)} personagens encontrados para processar.")

    for p in personagens:
        perfil_json = json.dumps(p, ensure_ascii=False, indent=2)
        char_id = p.get('personagem_id')

        if not char_id:
            print(f"AVISO: Personagem sem ID encontrado. A ignorar: {p}")
            continue

        # Insere o Personagem Principal
        if char_id == gabriel_id:
            # Nota: Outros campos como humor, creditos, etc. teriam de vir do ficheiro de estado
            cursor.execute('''
                INSERT INTO personagem_principal (id, nome)
                VALUES (?, ?)
            ''', (char_id, p.get('nome_completo')))
            print(f"INFO: Personagem principal '{char_id}' inserido.")
            
            # Insere as Habilidades do Personagem Principal
            habilidades_para_inserir = []
            for hab in p.get('habilidades', []):
                habilidades_para_inserir.append((
                    char_id,
                    hab.get('nome_habilidade'),
                    hab.get('nivel'),
                    hab.get('subnivel'),
                    hab.get('observacoes')
                ))
            if habilidades_para_inserir:
                cursor.executemany(
                    'INSERT INTO habilidades (personagem_id, nome_habilidade, nivel, subnivel, descricao) VALUES (?,?,?,?,?)',
                    habilidades_para_inserir
                )
                print(f"INFO: {len(habilidades_para_inserir)} habilidades inseridas para '{char_id}'.")

        # Adiciona PNJs à lista para inserção em massa
        else:
            pnjs_para_inserir.append((
                char_id, p.get('nome_completo'), None, 0, perfil_json
            ))

    # Insere todos os PNJs de uma vez
    if pnjs_para_inserir:
        cursor.executemany(
            'INSERT INTO pnjs (id, nome, localizacao_atual, relacionamento_com_pc, perfil_json) VALUES (?, ?, ?, ?, ?)',
            pnjs_para_inserir
        )
        print(f"INFO: {len(pnjs_para_inserir)} PNJs inseridos.")

    # NOTA: A população de inventário e conhecimentos/aptidões ainda precisaria
    # que o ficheiro 'Documento RPG - Estado Atual da Campanha e Log.md' fosse convertido
    # para este formato e a lógica de parsing seria adicionada aqui.

    conn.commit()
    conn.close()
    print("\nSUCESSO: População com o novo formato FLE concluída.")


if __name__ == "__main__":
    popular_base_fle_v2()
