import sqlite3
import os
import json
import yaml

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

class DataManager:
    """
    API do Mundo (v4.0) - A única camada que interage diretamente com a base de dados.
    Abstrai as consultas SQL e fornece métodos para o motor do jogo
    obter e modificar o estado do universo de forma segura e transacional.
    """

    def __init__(self, db_path=DB_PATH):
        """
        Inicializa o DataManager e estabelece a conexão com a base de dados.
        """
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados não foi encontrada em '{self.db_path}'. "
                                    "Por favor, execute o script 'scripts/build_world.py' primeiro.")
        print(f"DataManager (v4.0) conectado com sucesso a: {self.db_path}")

    def _get_connection(self):
        """Retorna uma nova conexão com a base de dados com Row Factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # --- Funções de Leitura Genéricas (Read) ---

    def get_entity_details_by_canonical_id(self, table_name, canonical_id):
        """Busca os detalhes completos de uma entidade pelo seu ID canónico."""
        print(f"Buscando entidade em '{table_name}' com ID canónico: {canonical_id}...")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Validação simples do nome da tabela para evitar SQL injection
                if table_name not in ['locais', 'tecnologias', 'personagens', 'civilizacoes', 'jogador']:
                    raise ValueError("Nome de tabela inválido.")
                
                query = f"SELECT * FROM {table_name} WHERE id_canonico = ?"
                cursor.execute(query, (canonical_id,))
                resultado = cursor.fetchone()
                return dict(resultado) if resultado else None
        except (sqlite3.Error, ValueError) as e:
            print(f"Erro ao buscar entidade '{canonical_id}' em '{table_name}': {e}")
            return None
            
    def find_entities_by_name(self, table_name, name_query, limit=5):
        """Busca entidades em uma tabela cujo nome corresponda a uma query (LIKE)."""
        print(f"Buscando em '{table_name}' por nomes como '%{name_query}%'...")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if table_name not in ['locais', 'tecnologias', 'personagens', 'civilizacoes']:
                    raise ValueError("Nome de tabela inválido para busca por nome.")

                query = f"SELECT id, id_canonico, nome, tipo FROM {table_name} WHERE nome LIKE ? LIMIT ?"
                cursor.execute(query, (f'%{name_query}%', limit))
                return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError) as e:
            print(f"Erro ao buscar entidades por nome: {e}")
            return []

    # --- Funções de Leitura de Locais (Hierarquia) ---

    def get_ancestors(self, local_id_numerico):
        """Retorna a cadeia de ancestrais de um local pelo seu ID numérico."""
        query = """
            WITH RECURSIVE get_ancestors(id, nome, tipo, parent_id, nivel) AS (
                SELECT id, nome, tipo, parent_id, 0 FROM locais WHERE id = ?
                UNION ALL
                SELECT l.id, l.nome, l.tipo, l.parent_id, ga.nivel + 1
                FROM locais l JOIN get_ancestors ga ON l.id = ga.parent_id
            )
            SELECT id, id_canonico, nome, tipo, nivel FROM get_ancestors ORDER BY nivel DESC;
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar ancestrais para o local ID {local_id_numerico}: {e}")
            return []

    def get_children(self, local_id_numerico):
        """Retorna os filhos diretos de um local pelo seu ID numérico."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, id_canonico, nome, tipo FROM locais WHERE parent_id = ?", (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar filhos para o local ID {local_id_numerico}: {e}")
            return []

    # --- Funções de Leitura do Jogador ---

    def get_player_full_status(self, player_canonical_id='pj_gabriel_oliveira'):
        """Busca e agrega todas as informações de estado do jogador."""
        print(f"\nBuscando estado completo para o jogador: {player_canonical_id}...")
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                player_info = self.get_entity_details_by_canonical_id('jogador', player_canonical_id)
                if not player_info: return None
                player_db_id = player_info['id']
                
                cursor.execute("SELECT l.nome as local_nome, l.tipo as local_tipo FROM locais l WHERE l.id = ?", (player_info['local_atual_id'],))
                local_info = cursor.fetchone()

                player_status['base'] = {**player_info, **local_info}
                
                cursor.execute("SELECT * FROM jogador_habilidades WHERE jogador_id = ?", (player_db_id,))
                player_status['habilidades'] = [dict(row) for row in cursor.fetchall()]
                
                cursor.execute("SELECT * FROM jogador_conhecimentos WHERE jogador_id = ?", (player_db_id,))
                player_status['conhecimentos'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_posses WHERE jogador_id = ?", (player_db_id,))
                player_status['posses'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
                player_status['vitals'] = dict(cursor.fetchone())

            return player_status
        except sqlite3.Error as e:
            print(f"Erro ao buscar o estado completo do jogador: {e}")
            return None

    # --- Funções de Escrita (Write) ---

    def update_player_location(self, player_canonical_id, new_local_canonical_id):
        """Atualiza a localização atual do jogador."""
        print(f"Movendo jogador '{player_canonical_id}' para o local '{new_local_canonical_id}'...")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Obter o ID numérico do novo local
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (new_local_canonical_id,))
                local_res = cursor.fetchone()
                if not local_res:
                    print(f"ERRO: Local de destino '{new_local_canonical_id}' não existe.")
                    return False
                new_local_id = local_res['id']

                # Atualizar a tabela do jogador
                cursor.execute(
                    "UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?",
                    (new_local_id, player_canonical_id)
                )
                conn.commit()
                
                if cursor.rowcount > 0:
                    print("SUCESSO: Localização do jogador atualizada.")
                    return True
                else:
                    print(f"AVISO: Jogador com ID '{player_canonical_id}' não encontrado para atualização.")
                    return False
        except sqlite3.Error as e:
            print(f"Erro ao atualizar a localização do jogador: {e}")
            conn.rollback()
            return False

    def add_location(self, id_canonico, nome, tipo, perfil_yaml, parent_id_canonico=None):
        """Adiciona um novo local ao universo (Canonização)."""
        print(f"Canonizando novo local: '{id_canonico}' ({nome})...")
        parent_id_numerico = None
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Se houver um pai, obter seu ID numérico
                if parent_id_canonico:
                    cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (parent_id_canonico,))
                    parent_res = cursor.fetchone()
                    if not parent_res:
                        print(f"ERRO: Local pai '{parent_id_canonico}' não encontrado. Canonização falhou.")
                        return None
                    parent_id_numerico = parent_res['id']
                
                # Inserir o novo local
                query = """
                    INSERT INTO locais (id_canonico, nome, tipo, perfil_yaml, parent_id)
                    VALUES (?, ?, ?, ?, ?)
                """
                cursor.execute(query, (id_canonico, nome, tipo, perfil_yaml, parent_id_numerico))
                new_local_id = cursor.lastrowid
                conn.commit()

                print(f"SUCESSO: Local '{nome}' adicionado com o ID numérico {new_local_id}.")
                return new_local_id
        except sqlite3.IntegrityError:
            print(f"ERRO: O ID canónico '{id_canonico}' já existe. Canonização falhou.")
            conn.rollback()
            return None
        except sqlite3.Error as e:
            print(f"Erro ao adicionar novo local: {e}")
            conn.rollback()
            return None


# --- Exemplo de Uso e Teste Abrangente ---
if __name__ == '__main__':
    print("--- Testando o DataManager (v4.0) ---")
    
    # Garante que a BD está limpa e atualizada para o teste
    build_script_path = os.path.join(PROJECT_ROOT, 'scripts', 'build_world.py')
    if os.path.exists(build_script_path):
        print("\nExecutando 'build_world.py' para garantir uma base de dados limpa...")
        os.system(f'python "{build_script_path}"')
    
    try:
        dm = DataManager()
        
        # --- Teste 1: Leitura de Dados ---
        print("\n--- Teste 1: Funções de Leitura ---")
        local_atual = dm.get_entity_details_by_canonical_id('locais', 'setor_lab_atmosferico_4b')
        if local_atual:
            print(f"\n[SUCESSO] Detalhes do local 'setor_lab_atmosferico_4b' recuperados.")
            local_atual_id_numerico = local_atual['id']

            ancestrais = dm.get_ancestors(local_atual_id_numerico)
            print(f"[SUCESSO] Caminho para o local (Ancestrais):")
            print(json.dumps(ancestrais, indent=2, ensure_ascii=False))

            filhos = dm.get_children(local_atual_id_numerico)
            print(f"\n[SUCESSO] Conteúdo do local (Filhos):")
            print(json.dumps(filhos, indent=2, ensure_ascii=False))
        else:
            print("[FALHA] Não foi possível obter detalhes do local inicial.")

        # --- Teste 2: Busca por Nome ---
        print("\n--- Teste 2: Busca por Nome ---")
        resultados_busca = dm.find_entities_by_name('locais', 'Laboratório')
        print(f"\n[SUCESSO] Busca por 'Laboratório' em locais:")
        print(json.dumps(resultados_busca, indent=2, ensure_ascii=False))

        # --- Teste 3: Leitura do Estado do Jogador ---
        print("\n--- Teste 3: Leitura do Estado Completo do Jogador ---")
        estado_jogador_antes = dm.get_player_full_status()
        if estado_jogador_antes:
             print("[SUCESSO] Estado inicial do jogador recuperado:")
             print(f"  - Localização: {estado_jogador_antes['base']['local_nome']}")
        else:
            print("[FALHA] Não foi possível recuperar o estado do jogador.")

        # --- Teste 4: Modificação de Estado (Mover Jogador) ---
        print("\n--- Teste 4: Modificação - Mover Jogador ---")
        NOVO_LOCAL_CANONICO = 'corredor_acesso_lab_4'
        print(f"Tentando mover jogador para '{NOVO_LOCAL_CANONICO}'...")
        sucesso_movimento = dm.update_player_location('pj_gabriel_oliveira', NOVO_LOCAL_CANONICO)
        
        if sucesso_movimento:
            estado_jogador_depois = dm.get_player_full_status()
            print("\n[SUCESSO] Verificando nova localização do jogador:")
            print(f"  - Nova Localização: {estado_jogador_depois['base']['local_nome']}")
            if estado_jogador_depois['base']['local_nome'] == 'Corredor de Acesso ao Laboratório 4':
                print("  - VERIFICAÇÃO OK!")
            else:
                print("  - VERIFICAÇÃO FALHOU!")
        else:
            print("[FALHA] Movimento do jogador não foi bem-sucedido.")
            
        # --- Teste 5: Canonização (Adicionar Novo Local) ---
        print("\n--- Teste 5: Expansão - Canonizar Novo Local ---")
        id_novo_local = 'sala_secreta_descoberta_01'
        perfil_novo_local = yaml.dump({
            'descoberta_por': 'pj_gabriel_oliveira',
            'descricao_inicial': 'Uma pequena sala de manutenção esquecida, poeirenta e com um terminal antigo piscando num canto.',
            'segredos': ['contem_log_antigo']
        })
        
        novo_local_id = dm.add_location(
            id_canonico=id_novo_local,
            nome="Sala de Manutenção Esquecida",
            tipo="sala_interna",
            perfil_yaml=perfil_novo_local,
            parent_id_canonico=NOVO_LOCAL_CANONICO # Anexado ao corredor
        )
        
        if novo_local_id:
            print(f"\n[SUCESSO] Verificando se o novo local existe...")
            local_criado = dm.get_entity_details_by_canonical_id('locais', id_novo_local)
            if local_criado:
                print(f"  - Detalhes do local criado recuperados:")
                print(f"  - Nome: {local_criado['nome']}")
                print(f"  - ID Pai (numérico): {local_criado['parent_id']}")
                print("  - VERIFICAÇÃO OK!")
            else:
                print("  - FALHA NA VERIFICAÇÃO: Não foi possível recuperar o local recém-criado.")
        else:
            print("[FALHA] Canonização do novo local não foi bem-sucedida.")

    except FileNotFoundError as e:
        print(f"\nERRO CRÍTICO: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nOcorreu um erro inesperado durante o teste: {e}")

