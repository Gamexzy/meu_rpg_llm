import sqlite3
import os
import json
import datetime
import sys

# Adiciona o diretório da raiz do projeto ao sys.path para que o módulo config e data possam ser importados
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
sys.path.append(os.path.join(PROJECT_ROOT, 'data')) # NOVO: Adiciona o diretório 'data' ao sys.path

# Importar as configurações globais
import config as config 

# Importar a função to_snake_case (CORRIGIDO O CAMINHO)
from entity_types_data import to_snake_case

class DataManager:
    """
    API do Mundo (v5.15) - A única camada que interage DIRETAMENTE com a base de dados SQLite.
    Abstrai as consultas SQL e fornece métodos para o motor do jogo
    obter e modificar o estado do universo.
    (Change: Adaptado para nova estrutura de tipos com nome_tipo (snake_case) e display_name.
             add_new_entity_type aprimorada.
             Versão: 5.15)
    """

    def __init__(self, db_path=config.DB_PATH_SQLITE): 
        """
        Inicializa o DataManager e estabelece a conexão com a base de dados.
        """
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados não foi encontrada em '{self.db_path}'. "
                                    "Por favor, execute o script 'scripts/build_world.py' primeiro para criar o esquema vazio.")
        print(f"DataManager (v5.15) conectado com sucesso a: {self.db_path}")

    def _get_connection(self):
        """Retorna uma nova conexão com a base de dados com Row Factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _get_type_id(self, table_name, nome_tipo_snake_case):
        """
        Obtém o ID numérico de um tipo de entidade a partir da tabela tipos_entidades, usando nome_tipo (snake_case).
        Retorna None se o tipo não for encontrado.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id FROM tipos_entidades WHERE nome_tabela = ? AND nome_tipo = ?"
                cursor.execute(query, (table_name, nome_tipo_snake_case))
                result = cursor.fetchone()
                if result:
                    return result['id']
                else:
                    return None
        except sqlite3.Error as e:
            print(f"Erro ao buscar tipo_id para '{nome_tipo_snake_case}' na tabela '{table_name}': {e}")
            return None

    def _get_type_details_by_id(self, type_id):
        """
        Obtém os detalhes de um tipo de entidade pelo seu ID numérico.
        Retorna o dicionário completo da linha.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM tipos_entidades WHERE id = ?"
                cursor.execute(query, (type_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            print(f"Erro ao buscar detalhes do tipo ID {type_id}: {e}")
            return None

    def _get_table_columns(self, table_name):
        """Retorna uma lista de nomes de colunas para uma dada tabela."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            return [col[1] for col in cursor.fetchall()]

    # --- Funções de Leitura Genéricas (Read) ---

    def get_entity_details_by_canonical_id(self, table_name, canonical_id):
        """
        Busca os detalhes completos de uma entidade pelo seu ID canónico em qualquer tabela universal.
        Faz JOIN com tipos_entidades para recuperar o display_name do tipo.
        Retorna o dicionário completo da linha, incluindo o ID interno ('id').
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 'jogador_posses', 'tipos_entidades', 'locais_acessos_diretos', 'relacoes_entidades', 'jogador_habilidades', 'jogador_conhecimentos', 'jogador_status_fisico_emocional', 'jogador_logs_memoria', 'local_elementos']
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido: '{table_name}'. Use um dos seguintes: {', '.join(tabelas_validas)}")
                
                columns = self._get_table_columns(table_name)
                
                if 'tipo_id' in columns:
                    query = f"""
                        SELECT t1.*, t2.nome_tipo AS tipo_snake_case, t2.display_name AS tipo_display_name
                        FROM {table_name} t1
                        LEFT JOIN tipos_entidades t2 ON t1.tipo_id = t2.id
                        WHERE t1.id_canonico = ?
                    """
                elif 'id_canonico' in columns:
                    query = f"SELECT * FROM {table_name} WHERE id_canonico = ?"
                else:
                    return None

                cursor.execute(query, (canonical_id,))
                resultado = cursor.fetchone()
                
                if resultado:
                    result_dict = dict(resultado)
                    if 'tipo_snake_case' in result_dict:
                        result_dict['tipo'] = result_dict.pop('tipo_snake_case')
                    if 'tipo_display_name' in result_dict:
                        result_dict['tipo_display_name'] = result_dict.pop('tipo_display_name')
                    return result_dict
                return None
        except (sqlite3.Error, ValueError) as e:
            print(f"Erro ao buscar entidade '{canonical_id}' em '{table_name}': {e}")
            return None
    
    def get_all_entities_from_table(self, table_name):
        """
        Retorna todos os registros de uma tabela especificada.
        Ideal para exportação em massa para outros pilares.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                                   'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                                   'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                                   'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'tipos_entidades']
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido para exportação: '{table_name}'.")
                
                query = f"SELECT * FROM {table_name}"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError) as e:
            print(f"ERRO ao obter todos os dados da tabela '{table_name}': {e}")
            return []
            
    # --- Funções de Leitura de Locais (Hierarquia e Acessos) ---

    def get_ancestors(self, local_id_numerico):
        """Retorna a cadeia de ancestrais de um local pelo seu ID numérico."""
        query = """
            WITH RECURSIVE get_ancestors(id, id_canonico, nome, tipo_id, parent_id, nivel) AS (
                SELECT id, id_canonico, nome, tipo_id, parent_id, 0 FROM locais WHERE id = ?
                UNION ALL
                SELECT l.id, l.id_canonico, l.nome, l.tipo_id, l.parent_id, ga.nivel + 1
                FROM locais l JOIN get_ancestors ga ON l.id = ga.parent_id
            )
            SELECT ga.id, ga.id_canonico, ga.nome, te.display_name AS tipo_display_name, ga.nivel
            FROM get_ancestors ga
            LEFT JOIN tipos_entidades te ON ga.tipo_id = te.id
            ORDER BY nivel DESC;
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (local_id_numerico,))
                results = []
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    row_dict['tipo'] = row_dict.pop('tipo_display_name')
                    results.append(row_dict)
                return results
        except sqlite3.Error as e:
            print(f"Erro ao buscar ancestrais para o local ID {local_id_numerico}: {e}")
            return []

    def get_children(self, local_id_numerico):
        """Retorna os filhos diretos de um local (o que está contido nele)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo_display_name
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.parent_id = ?;
                """
                cursor.execute(query, (local_id_numerico,))
                results = []
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    row_dict['tipo'] = row_dict.pop('tipo_display_name')
                    results.append(row_dict)
                return results
        except sqlite3.Error as e:
            print(f"Erro ao buscar filhos para o local ID {local_id_numerico}: {e}")
            return []

    def get_direct_accesses(self, local_id_numerico):
        """Retorna locais acessíveis diretamente a partir de um local."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo_display_name, lad.tipo_acesso, lad.condicoes_acesso
                    FROM locais_acessos_diretos lad
                    JOIN locais l ON lad.local_destino_id = l.id
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE lad.local_origem_id = ?;
                """
                cursor.execute(query, (local_id_numerico,))
                results = []
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    row_dict['tipo'] = row_dict.pop('tipo_display_name')
                    results.append(row_dict)
                return results
        except sqlite3.Error as e:
            print(f"Erro ao buscar acessos diretos para o local ID {local_id_numerico}: {e}")
            return []

    def get_siblings(self, local_id_numerico):
        """
        Retorna os locais "vizinhos" (que partilham o mesmo pai).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT parent_id FROM locais WHERE id = ?", (local_id_numerico,))
                res = cursor.fetchone()
                if not res or res['parent_id'] is None:
                    return []
                
                parent_id = res['parent_id']
                
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo_display_name
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.parent_id = ? AND l.id != ?;
                """
                cursor.execute(query, (parent_id, local_id_numerico))
                results = []
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    row_dict['tipo'] = row_dict.pop('tipo_display_name')
                    results.append(row_dict)
                return results
        except sqlite3.Error as e:
            print(f"Erro ao buscar vizinhos para o local ID {local_id_numerico}: {e}")
            return []

    # --- Funções de Leitura do Jogador ---

    def get_player_full_status(self, player_canonical_id=config.DEFAULT_PLAYER_ID_CANONICO):
        """Busca e agrega todas as informações de estado do jogador."""
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                player_info = self.get_entity_details_by_canonical_id('jogador', player_canonical_id)
                if not player_info: return None
                player_db_id = player_info['id']

                query_local = """
                    SELECT l.id as local_id, l.id_canonico as local_id_canonico, l.nome as local_nome, te.display_name as local_tipo_display_name
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.id = ?
                """
                cursor.execute(query_local, (player_info['local_atual_id'],))
                local_info = cursor.fetchone()

                player_status['base'] = {**player_info, **(dict(local_info) if local_info else {})}
                if 'local_tipo_display_name' in player_status['base']:
                    player_status['base']['local_tipo'] = player_status['base'].pop('local_tipo_display_name')
                
                cursor.execute("SELECT * FROM jogador_habilidades WHERE jogador_id = ?", (player_db_id,))
                player_status['habilidades'] = [dict(row) for row in cursor.fetchall()]
                
                cursor.execute("SELECT * FROM jogador_conhecimentos WHERE jogador_id = ?", (player_db_id,))
                player_status['conhecimentos'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_posses WHERE jogador_id = ?", (player_db_id,))
                player_status['posses'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
                vitals = cursor.fetchone()
                player_status['vitals'] = dict(vitals) if vitals else {}

                cursor.execute("SELECT * FROM jogador_logs_memoria WHERE jogador_id = ? ORDER BY id DESC LIMIT 5", (player_db_id,))
                player_status['logs_recentes'] = [dict(row) for row in cursor.fetchall()]

            return player_status
        except sqlite3.Error as e:
            print(f"Erro ao buscar o estado completo do jogador: {e}")
            return None

    # --- Funções de Escrita (Write) para Canonização Dinâmica ---

    def add_location(self, id_canonico, nome, tipo_display_name, perfil_json_data=None, parent_id_canonico=None):
        """Adiciona um novo local ao universo (Canonização).
        'tipo_display_name' deve ser o nome legível do tipo (ex: 'Estação Espacial')."""
        
        tipo_snake_case = to_snake_case(tipo_display_name)
        tipo_id_numerico = self._get_type_id('locais', tipo_snake_case)
        if tipo_id_numerico is None:
            print(f"ERRO: Tipo '{tipo_display_name}' (snake_case: '{tipo_snake_case}') para a tabela 'locais' não encontrado em 'tipos_entidades'.")
            return None

        parent_id_numerico = None
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if parent_id_canonico:
                    cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (parent_id_canonico,))
                    parent_res = cursor.fetchone()
                    if not parent_res:
                        print(f"AVISO: Parent ID canônico '{parent_id_canonico}' não encontrado para o local '{id_canonico}'. Inserindo como raiz.")
                    else:
                        parent_id_numerico = parent_res['id']
                
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                
                query = "INSERT INTO locais (id_canonico, nome, tipo_id, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str, parent_id_numerico))
                new_local_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Local '{nome}' ({id_canonico}, Tipo: '{tipo_display_name}') adicionado com ID {new_local_id}.")
                
                return new_local_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar local '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_location(self, id_canonico, nome, tipo_display_name, perfil_json_data=None, parent_id_canonico=None):
        """
        Verifica se um local com o id_canonico já existe. Se existir, retorna seus detalhes.
        Caso contrário, cria o novo local e retorna seus detalhes.
        """
        existing_loc = self.get_entity_details_by_canonical_id('locais', id_canonico)
        if existing_loc:
            print(f"INFO: Local '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_loc['id']
        else:
            print(f"INFO: Local '{nome}' ({id_canonico}) não encontrado. Criando novo local.")
            return self.add_location(id_canonico, nome, tipo_display_name, perfil_json_data, parent_id_canonico)

    def add_player(self, id_canonico, nome, local_inicial_id_canonico, perfil_completo_data):
        """
        Adiciona um novo jogador ao banco de dados e define sua localização inicial.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (local_inicial_id_canonico,))
                local_res = cursor.fetchone()
                if not local_res:
                    print(f"ERRO: Local inicial '{local_inicial_id_canonico}' não encontrado. O jogador não pode ser criado.")
                    return None
                
                local_inicial_id_numerico = local_res['id']
                perfil_json_str = json.dumps(perfil_completo_data, ensure_ascii=False)

                cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                               (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
                player_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Jogador '{nome}' ({id_canonico}) criado com ID {player_id} no local '{local_inicial_id_canonico}'.")
                
                return player_id
        except sqlite3.IntegrityError as e:
            print(f"ERRO: Jogador com ID canônico '{id_canonico}' já existe: {e}")
            conn.rollback()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar jogador '{nome}': {e}")
            return None

    def add_or_get_player(self, id_canonico, nome, local_inicial_id_canonico, perfil_completo_data):
        """
        Verifica se um jogador com o id_canonico já existe. Se existir, retorna seus detalhes.
        Caso contrário, cria o novo jogador e retorna seus detalhes.
        """
        existing_player = self.get_entity_details_by_canonical_id('jogador', id_canonico)
        if existing_player:
            print(f"INFO: Jogador '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_player['id']
        else:
            print(f"INFO: Jogador '{nome}' ({id_canonico}) não encontrado. Criando novo jogador.")
            return self.add_player(id_canonico, nome, local_inicial_id_canonico, perfil_completo_data)

    def add_player_vitals(self, jogador_id_canonico, fome="Normal", sede="Normal", cansaco="Descansado", humor="Neutro", motivacao="Neutro", timestamp_atual=None):
        """
        Adiciona ou atualiza o status físico e emocional do jogador.
        """
        if timestamp_atual is None:
            timestamp_atual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res:
                    print(f"ERRO: Jogador com ID canônico '{jogador_id_canonico}' não encontrado para adicionar vitals.")
                    return False
                player_db_id = player_res['id']

                cursor.execute("SELECT id FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
                existing_vitals = cursor.fetchone()

                if existing_vitals:
                    query = """
                        UPDATE jogador_status_fisico_emocional
                        SET fome = ?, sede = ?, cansaco = ?, humor = ?, motivacao = ?, timestamp_atual = ?
                        WHERE jogador_id = ?;
                    """
                    cursor.execute(query, (fome, sede, cansaco, humor, motivacao, timestamp_atual, player_db_id))
                    print(f"INFO: Vitals do jogador '{jogador_id_canonico}' atualizados.")
                else:
                    query = """
                        INSERT INTO jogador_status_fisico_emocional
                        (jogador_id, fome, sede, cansaco, humor, motivacao, timestamp_atual)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """
                    cursor.execute(query, (player_db_id, fome, sede, cansaco, humor, motivacao, timestamp_atual))
                    print(f"INFO: Vitals iniciais do jogador '{jogador_id_canonico}' adicionados.")
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar/atualizar vitals do jogador '{jogador_id_canonico}': {e}")
            return False

    def add_player_skill(self, jogador_id_canonico, categoria, nome, nivel_subnivel=None, observacoes=None):
        """Adiciona uma nova habilidade ao jogador."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                               (player_db_id, categoria, nome, nivel_subnivel, observacoes))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Habilidade '{nome}' adicionada para '{jogador_id_canonico}'.")
                    return True
                else:
                    print(f"INFO: Habilidade '{nome}' para '{jogador_id_canonico}' já existe (ignorada).")
                    return False

        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar habilidade para '{jogador_id_canonico}': {e}")
            return False

    def add_player_knowledge(self, jogador_id_canonico, categoria, nome, nivel=1, descricao=None):
        """Adiciona um novo conhecimento ao jogador."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                               (player_db_id, categoria, nome, nivel, descricao))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Conhecimento '{nome}' adicionado para '{jogador_id_canonico}'.")
                    return True
                else:
                    print(f"INFO: Conhecimento '{nome}' para '{jogador_id_canonico}' já existe (ignorado).")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar conhecimento para '{jogador_id_canonico}': {e}")
            return False

    def add_player_possession(self, jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data=None):
        """Adiciona uma nova posse ao jogador."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                
                cursor.execute("INSERT INTO jogador_posses (id_canonico, jogador_id, item_nome, perfil_json) VALUES (?, ?, ?, ?)",
                               (posse_id_canonico, player_db_id, item_nome, perfil_json_str))
                conn.commit()
                print(f"INFO: Posse '{item_nome}' ({posse_id_canonico}) adicionada para '{jogador_id_canonico}'.")

                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar posse para '{jogador_id_canonico}': {e}")
            return False

    def add_or_get_player_possession(self, jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data=None):
        """
        Verifica se uma posse do jogador com o id_canonico já existe. Se existir, retorna seus detalhes.
        Caso contrário, cria a nova posse e retorna seus detalhes (ID interno).
        """
        existing_possession = self.get_entity_details_by_canonical_id('jogador_posses', posse_id_canonico)
        if existing_possession:
            print(f"INFO: Posse '{item_nome}' ({posse_id_canonico}) para '{jogador_id_canonico}' já existe. Utilizando o existente.")
            return existing_possession['id']
        else:
            print(f"INFO: Posse '{item_nome}' ({posse_id_canonico}) para '{jogador_id_canonico}' não encontrada. Criando nova posse.")
            return self.add_player_possession(jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data)


    def add_log_memory(self, jogador_id_canonico, tipo, conteudo, timestamp_evento=None):
        """
        Adiciona um log ou memória consolidada para o jogador.
        """
        if timestamp_evento is None:
            timestamp_evento = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                query = """
                    INSERT INTO jogador_logs_memoria (jogador_id, tipo, timestamp_evento, conteudo)
                    VALUES (?, ?, ?, ?);
                """
                cursor.execute(query, (player_db_id, tipo, timestamp_evento, conteudo))
                conn.commit()
                print(f"INFO: Log/Memória ({tipo}) adicionado(a) para '{jogador_id_canonico}'.")
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar log/memória para '{jogador_id_canonico}': {e}")
            return False

    def update_player_location(self, player_canonical_id, new_local_canonical_id):
        """Atualiza a localização atual do jogador."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (new_local_canonical_id,))
                local_res = cursor.fetchone()
                if not local_res:
                    print(f"ERRO: Local de destino '{new_local_canonical_id}' não encontrado para mover o jogador.")
                    return False
                new_local_id = local_res['id']

                cursor.execute("UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?", (new_local_id, player_canonical_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"INFO: Jogador '{player_canonical_id}' movido para '{new_local_canonical_id}'.")
                    return True
                else:
                    print(f"AVISO: Jogador '{player_canonical_id}' não encontrado para atualização de localização.")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao atualizar localização do jogador '{player_canonical_id}': {e}")
            return False

    def add_direct_access_relation(self, origem_id_canonico, destino_id_canonico, tipo_acesso=None, condicoes_acesso=None):
        """
        Adiciona uma relação de acesso direto entre dois locais.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                origem_entity = self.get_entity_details_by_canonical_id('locais', origem_id_canonico)
                destino_entity = self.get_entity_details_by_canonical_id('locais', destino_id_canonico)

                if not origem_entity or not destino_entity:
                    print(f"ERRO: Origem ('{origem_id_canonico}') ou Destino ('{destino_id_canonico}') não encontrados para relação de acesso.")
                    return False

                query = """
                    INSERT OR IGNORE INTO locais_acessos_diretos (local_origem_id, local_destino_id, tipo_acesso, condicoes_acesso)
                    VALUES (?, ?, ?, ?);
                """
                cursor.execute(query, (origem_entity['id'], destino_entity['id'], tipo_acesso, condicoes_acesso))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Relação de acesso direto entre '{origem_id_canonico}' e '{destino_id_canonico}' adicionada.")
                    return True
                else:
                    print(f"AVISO: Relação de acesso direto entre '{origem_id_canonico}' e '{destino_id_canonico}' já existe (ignorada).")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar relação de acesso direto: {e}")
            return False

    def add_universal_relation(self, origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_data=None):
        """
        Adiciona uma relação universal na tabela 'relacoes_entidades'.
        origem_tipo_tabela e destino_tipo_tabela devem ser os nomes das tabelas (ex: 'personagens', 'locais').
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                propriedades_json_str = json.dumps(propriedades_data, ensure_ascii=False) if propriedades_data else None

                query = """
                    INSERT OR IGNORE INTO relacoes_entidades
                    (entidade_origem_id, entidade_origem_tipo, tipo_relacao, entidade_destino_id, entidade_destino_tipo, propriedades_json)
                    VALUES (?, ?, ?, ?, ?, ?);
                """
                cursor.execute(query, (origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_json_str))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Relação universal '{tipo_relacao}' criada entre '{origem_id_canonico}' ({origem_tipo_tabela}) e '{destino_id_canonico}' ({destino_tipo_tabela}).")
                    return cursor.lastrowid
                else:
                    print(f"AVISO: Relação universal '{tipo_relacao}' entre '{origem_id_canonico}' e '{destino_id_canonico}' já existe (ignorada).")
                    return None
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar relação universal: {e}")
            return None

    def add_column_to_table(self, table_name, column_name, column_type, default_value=None):
        """
        Adiciona uma nova coluna a uma tabela existente.
        Permite que o esquema do DB seja expandido dinamicamente.
        """
        valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador',
                        'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                        'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                        'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'tipos_entidades']
        valid_types = ['TEXT', 'INTEGER', 'REAL', 'BLOB']

        if table_name not in valid_tables:
            print(f"ERRO: Tabela '{table_name}' não é válida para adicionar coluna.")
            return False
        if column_type.upper() not in valid_types:
            print(f"ERRO: Tipo de coluna '{column_type}' inválido. Use um dos seguintes: {', '.join(valid_types)}.")
            return False
        
        if not column_name.replace('_', '').isalnum(): 
            print(f"ERRO: Nome da coluna '{column_name}' inválido. Use apenas caracteres alfanuméricos e underscores.")
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"PRAGMA table_info({table_name});")
                existing_columns = [info['name'] for info in cursor.fetchall()]
                if column_name in existing_columns:
                    print(f"AVISO: Coluna '{column_name}' já existe na tabela '{table_name}'.")
                    return True

                if default_value is not None:
                    if isinstance(default_value, str):
                        default_sql = f"'{default_value}'"
                    elif isinstance(default_value, (int, float)):
                        default_sql = str(default_value)
                    else:
                        print(f"AVISO: Valor padrão de tipo não suportado diretamente para SQL: {type(default_value)}. Inserindo NULL.")
                        default_sql = "NULL"
                    query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type.upper()} DEFAULT {default_sql};"
                else:
                    query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type.upper()};"
                
                cursor.execute(query)
                conn.commit()
                print(f"INFO: Coluna '{column_name}' ({column_type}) adicionada à tabela '{table_name}'.")
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar coluna '{column_name}' à tabela '{table_name}': {e}")
            return False

    def add_element_universal(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Adiciona um novo elemento universal (tecnologia, magia, recurso, etc.)."""
        tipo_snake_case = to_snake_case(tipo_display_name)
        tipo_id_numerico = self._get_type_id('elementos_universais', tipo_snake_case)
        if tipo_id_numerico is None:
            print(f"ERRO: Tipo '{tipo_display_name}' (snake_case: '{tipo_snake_case}') para a tabela 'elementos_universais' não encontrado em 'tipos_entidades'.")
            return None
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO elementos_universais (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Elemento Universal '{nome}' ({id_canonico}, Tipo: '{tipo_display_name}') adicionado com ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar elemento universal '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_element_universal(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Verifica se um elemento universal já existe. Se existir, retorna seus detalhes. Caso contrário, cria e retorna."""
        existing_entity = self.get_entity_details_by_canonical_id('elementos_universais', id_canonico)
        if existing_entity:
            print(f"INFO: Elemento Universal '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_entity['id']
        else:
            print(f"INFO: Elemento Universal '{nome}' ({id_canonico}) não encontrado. Criando novo elemento.")
            return self.add_element_universal(id_canonico, nome, tipo_display_name, perfil_json_data)

    def add_personagem(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Adiciona um novo personagem (NPC, monstro, etc.)."""
        tipo_snake_case = to_snake_case(tipo_display_name)
        tipo_id_numerico = self._get_type_id('personagens', tipo_snake_case)
        if tipo_id_numerico is None:
            print(f"ERRO: Tipo '{tipo_display_name}' (snake_case: '{tipo_snake_case}') para a tabela 'personagens' não encontrado em 'tipos_entidades'.")
            return None
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO personagens (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Personagem '{nome}' ({id_canonico}, Tipo: '{tipo_display_name}') adicionado com ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar personagem '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_personagem(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Verifica se um personagem já existe. Se existir, retorna seus detalhes. Caso contrário, cria e retorna."""
        existing_entity = self.get_entity_details_by_canonical_id('personagens', id_canonico)
        if existing_entity:
            print(f"INFO: Personagem '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_entity['id']
        else:
            print(f"INFO: Personagem '{nome}' ({id_canonico}) não encontrado. Criando novo personagem.")
            return self.add_personagem(id_canonico, nome, tipo_display_name, perfil_json_data)

    def add_faccao(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Adiciona uma nova facção (reino, corporação, etc.)."""
        tipo_snake_case = to_snake_case(tipo_display_name)
        tipo_id_numerico = self._get_type_id('faccoes', tipo_snake_case)
        if tipo_id_numerico is None:
            print(f"ERRO: Tipo '{tipo_display_name}' (snake_case: '{tipo_snake_case}') para a tabela 'faccoes' não encontrado em 'tipos_entidades'.")
            return None
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO faccoes (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Facção '{nome}' ({id_canonico}, Tipo: '{tipo_display_name}') adicionada com ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO ao adicionar facção '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_faccao(self, id_canonico, nome, tipo_display_name, perfil_json_data=None):
        """Verifica se uma facção já existe. Se existir, retorna seus detalhes. Caso contrário, cria e retorna."""
        existing_entity = self.get_entity_details_by_canonical_id('faccoes', id_canonico)
        if existing_entity:
            print(f"INFO: Facção '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_entity['id']
        else:
            print(f"INFO: Facção '{nome}' ({id_canonico}) não encontrado. Criando nova facção.")
            return self.add_faccao(id_canonico, nome, tipo_display_name, perfil_json_data)

    def add_new_entity_type(self, nome_tabela, nome_tipo_display, parent_tipo_display=None):
        """
        Adiciona um novo tipo à tabela 'tipos_entidades' com validação e suporte a hierarquia.
        nome_tipo_display: Nome legível para o novo tipo (ex: 'Planeta Aquático').
        parent_tipo_display: Nome legível do tipo pai, se houver (ex: 'Planeta').
        Retorna o nome_tipo (snake_case) do tipo adicionado/existente, ou None em caso de falha.
        """
        if not nome_tabela or not nome_tipo_display:
            print("ERRO DE VALIDAÇÃO: 'nome_tabela' e 'nome_tipo_display' não podem ser vazios.")
            return None
        
        valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes']
        if nome_tabela not in valid_tables:
            print(f"ERRO DE VALIDAÇÃO: 'nome_tabela' '{nome_tabela}' é inválida. Use uma das seguintes: {', '.join(valid_tables)}.")
            return None

        nome_tipo_snake_case = to_snake_case(nome_tipo_display)
        
        parent_tipo_id = None
        if parent_tipo_display:
            parent_tipo_snake_case = to_snake_case(parent_tipo_display)
            parent_tipo_id = self._get_type_id(nome_tabela, parent_tipo_snake_case)
            if parent_tipo_id is None:
                print(f"AVISO: Tipo pai '{parent_tipo_display}' (snake_case: '{parent_tipo_snake_case}') para a tabela '{nome_tabela}' não encontrado. O novo tipo '{nome_tipo_display}' será adicionado sem pai.")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id, nome_tipo FROM tipos_entidades WHERE nome_tabela = ? AND nome_tipo = ?", (nome_tabela, nome_tipo_snake_case))
                existing_type_record = cursor.fetchone()

                if existing_type_record:
                    print(f"AVISO: Tipo '{nome_tipo_display}' (snake_case: '{nome_tipo_snake_case}') para a tabela '{nome_tabela}' já existe (ID: {existing_type_record['id']}).")
                    return nome_tipo_snake_case

                cursor.execute(
                    "INSERT INTO tipos_entidades (nome_tabela, nome_tipo, display_name, parent_tipo_id) VALUES (?, ?, ?, ?)",
                    (nome_tabela, nome_tipo_snake_case, nome_tipo_display, parent_tipo_id)
                )
                conn.commit()
                print(f"INFO: Novo tipo '{nome_tipo_display}' (snake_case: '{nome_tipo_snake_case}') adicionado para a tabela '{nome_tabela}'.")
                return nome_tipo_snake_case
        except sqlite3.IntegrityError as e:
            print(f"ERRO ao adicionar tipo '{nome_tipo_display}' (snake_case: '{nome_tipo_snake_case}') para '{nome_tabela}' (violou restrição UNIQUE): {e}")
            conn.rollback()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERRO inesperado ao adicionar tipo '{nome_tipo_display}' (snake_case: '{nome_tipo_snake_case}') para '{nome_tabela}': {e}")
            conn.rollback()
            return None
