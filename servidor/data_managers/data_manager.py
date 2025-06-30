import sqlite3
import os
import json
import datetime
import sys

from config import config

class DataManager:
    """
    API do Mundo (v5.19) - A única camada que interage DIRETAMENTE com a base de dados SQLite.
    (Change: Adicionada a função 'add_log_memory' para registrar logs e memórias do jogador.)
    """

    def __init__(self, db_path=config.DB_PATH_SQLITE, supress_success_message=False):
        """
        Inicializa o DataManager e estabelece a conexão com a base de dados.
        """
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados não foi encontrada em '{self.db_path}'. "
                                    "Por favor, execute o script 'scripts/build_world.py' primeiro para criar o esquema vazio.")
        if not supress_success_message:
            print(f"DataManager (v5.19) conectado com sucesso a: {self.db_path}")

    def _get_connection(self):
        """Retorna uma nova conexão com a base de dados com Row Factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _get_table_columns(self, table_name):
        """Retorna uma lista de nomes de colunas para uma dada tabela."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            return [col[1] for col in cursor.fetchall()]

    # --- Funções de Leitura Genéricas (Read) ---

    def get_entity_details_by_canonical_id(self, table_name, canonical_id):
        """
        Busca os detalhes completos de uma entidade pelo seu ID canónico.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 'jogador_posses', 'locais_acessos_diretos', 'relacoes_entidades', 'jogador_habilidades', 'jogador_conhecimentos', 'jogador_status_fisico_emocional', 'jogador_logs_memoria', 'local_elementos']
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido: '{table_name}'.")
                
                query = f"SELECT * FROM {table_name} WHERE id_canonico = ?"
                cursor.execute(query, (canonical_id,))
                resultado = cursor.fetchone()
                
                if resultado:
                    return dict(resultado)
                return None
        except (sqlite3.Error, ValueError) as e:
            print(f"Erro ao buscar entidade '{canonical_id}' em '{table_name}': {e}")
            return None
    
    def get_all_entities_from_table(self, table_name):
        """
        Retorna todos os registros de uma tabela especificada.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                                   'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                                   'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                                   'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades']
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
            WITH RECURSIVE get_ancestors(id, id_canonico, nome, tipo, parent_id, nivel) AS (
                SELECT id, id_canonico, nome, tipo, parent_id, 0 FROM locais WHERE id = ?
                UNION ALL
                SELECT l.id, l.id_canonico, l.nome, l.tipo, l.parent_id, ga.nivel + 1
                FROM locais l JOIN get_ancestors ga ON l.id = ga.parent_id
            )
            SELECT ga.id, ga.id_canonico, ga.nome, ga.tipo, ga.nivel
            FROM get_ancestors ga
            ORDER BY nivel DESC;
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
        """Retorna os filhos diretos de um local (o que está contido nele)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT l.id, l.id_canonico, l.nome, l.tipo FROM locais l WHERE l.parent_id = ?;"
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar filhos para o local ID {local_id_numerico}: {e}")
            return []

    def get_direct_accesses(self, local_id_numerico):
        """Retorna locais acessíveis diretamente a partir de um local."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT l.id, l.id_canonico, l.nome, l.tipo, lad.tipo_acesso, lad.condicoes_acesso
                    FROM locais_acessos_diretos lad
                    JOIN locais l ON lad.local_destino_id = l.id
                    WHERE lad.local_origem_id = ?;
                """
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
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
                
                query = "SELECT l.id, l.id_canonico, l.nome, l.tipo FROM locais l WHERE l.parent_id = ? AND l.id != ?;"
                cursor.execute(query, (parent_id, local_id_numerico))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar vizinhos para o local ID {local_id_numerico}: {e}")
            return []

    # --- Funções de Leitura do Jogador ---

    def get_player_full_status(self, player_canonical_id=None):
        """
        Busca e agrega todas as informações de estado do jogador.
        Se nenhum ID for fornecido, busca o primeiro (e único) jogador no banco de dados.
        """
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if not player_canonical_id:
                    # Busca o primeiro jogador se nenhum ID for especificado
                    cursor.execute("SELECT id_canonico FROM jogador LIMIT 1")
                    player_res = cursor.fetchone()
                    if not player_res:
                        return None # Nenhum jogador no DB
                    player_canonical_id = player_res['id_canonico']
                
                player_info = self.get_entity_details_by_canonical_id('jogador', player_canonical_id)
                if not player_info: return None
                player_db_id = player_info['id']

                query_local = """
                    SELECT l.id as local_id, l.id_canonico as local_id_canonico, l.nome as local_nome, l.tipo as local_tipo
                    FROM locais l
                    WHERE l.id = ?
                """
                cursor.execute(query_local, (player_info['local_atual_id'],))
                local_info = cursor.fetchone()

                player_status['base'] = {**player_info, **(dict(local_info) if local_info else {})}
                
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

    def add_or_get_location(self, id_canonico, nome, tipo, perfil_json_data=None, parent_id_canonico=None):
        """
        Verifica se um local com o id_canonico já existe. Se existir, retorna o ID.
        Caso contrário, cria o novo local e retorna o ID.
        """
        existing_loc = self.get_entity_details_by_canonical_id('locais', id_canonico)
        if existing_loc:
            print(f"INFO: Local '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_loc['id']
        else:
            print(f"INFO: Local '{nome}' ({id_canonico}) não encontrado. Criando novo local.")
            parent_id_numerico = None
            if parent_id_canonico:
                parent_loc = self.get_entity_details_by_canonical_id('locais', parent_id_canonico)
                if parent_loc:
                    parent_id_numerico = parent_loc['id']
                else:
                    print(f"AVISO: Parent ID canônico '{parent_id_canonico}' não encontrado. Inserindo como raiz.")
            
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "INSERT INTO locais (id_canonico, nome, tipo, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str, parent_id_numerico))
                conn.commit()
                return cursor.lastrowid

    def add_or_get_player(self, id_canonico, nome, local_inicial_id_canonico, perfil_completo_data):
        """
        Verifica se um jogador com o id_canonico já existe. Se existir, retorna o ID.
        Caso contrário, cria o novo jogador e retorna o ID.
        """
        existing_player = self.get_entity_details_by_canonical_id('jogador', id_canonico)
        if existing_player:
            print(f"INFO: Jogador '{nome}' ({id_canonico}) já existe. Utilizando o existente.")
            return existing_player['id']
        else:
            print(f"INFO: Jogador '{nome}' ({id_canonico}) não encontrado. Criando novo jogador.")
            local_inicial = self.get_entity_details_by_canonical_id('locais', local_inicial_id_canonico)
            if not local_inicial:
                print(f"ERRO: Local inicial '{local_inicial_id_canonico}' não encontrado. O jogador não pode ser criado.")
                return None
            
            local_inicial_id_numerico = local_inicial['id']
            perfil_json_str = json.dumps(perfil_completo_data)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                               (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
                conn.commit()
                return cursor.lastrowid
    
    def add_player_vitals(self, jogador_id_canonico, fome="Normal", sede="Normal", cansaco="Descansado", humor="Neutro", motivacao="Neutro", timestamp_atual=None):
        if timestamp_atual is None:
            timestamp_atual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("SELECT id FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
            if cursor.fetchone():
                query = "UPDATE jogador_status_fisico_emocional SET fome = ?, sede = ?, cansaco = ?, humor = ?, motivacao = ?, timestamp_atual = ? WHERE jogador_id = ?;"
                cursor.execute(query, (fome, sede, cansaco, humor, motivacao, timestamp_atual, player_db_id))
            else:
                query = "INSERT INTO jogador_status_fisico_emocional (jogador_id, fome, sede, cansaco, humor, motivacao, timestamp_atual) VALUES (?, ?, ?, ?, ?, ?, ?);"
                cursor.execute(query, (player_db_id, fome, sede, cansaco, humor, motivacao, timestamp_atual))
            conn.commit()
            return True

    def add_player_skill(self, jogador_id_canonico, categoria, nome, nivel_subnivel=None, observacoes=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel_subnivel, observacoes))
            conn.commit()
            return cursor.rowcount > 0

    def add_player_knowledge(self, jogador_id_canonico, categoria, nome, nivel=1, descricao=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel, descricao))
            conn.commit()
            return cursor.rowcount > 0

    def add_or_get_player_possession(self, jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data=None):
        existing = self.get_entity_details_by_canonical_id('jogador_posses', posse_id_canonico)
        if existing: return existing['id']
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return None
            player_db_id = player_res['id']
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            cursor.execute("INSERT INTO jogador_posses (id_canonico, jogador_id, item_nome, perfil_json) VALUES (?, ?, ?, ?)",
                           (posse_id_canonico, player_db_id, item_nome, perfil_json_str))
            conn.commit()
            return cursor.lastrowid

    def update_player_location(self, player_canonical_id, new_local_canonical_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            local_res = self.get_entity_details_by_canonical_id('locais', new_local_canonical_id)
            if not local_res: return False
            new_local_id = local_res['id']
            cursor.execute("UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?", (new_local_id, player_canonical_id))
            conn.commit()
            return cursor.rowcount > 0

    def add_direct_access_relation(self, origem_id_canonico, destino_id_canonico, tipo_acesso=None, condicoes_acesso=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            origem_entity = self.get_entity_details_by_canonical_id('locais', origem_id_canonico)
            destino_entity = self.get_entity_details_by_canonical_id('locais', destino_id_canonico)
            if not origem_entity or not destino_entity: return False
            query = "INSERT OR IGNORE INTO locais_acessos_diretos (local_origem_id, local_destino_id, tipo_acesso, condicoes_acesso) VALUES (?, ?, ?, ?);"
            cursor.execute(query, (origem_entity['id'], destino_entity['id'], tipo_acesso, condicoes_acesso))
            conn.commit()
            return cursor.rowcount > 0

    def add_universal_relation(self, origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_data=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            propriedades_json_str = json.dumps(propriedades_data) if propriedades_data else None
            query = "INSERT OR IGNORE INTO relacoes_entidades (entidade_origem_id, entidade_origem_tipo, tipo_relacao, entidade_destino_id, entidade_destino_tipo, propriedades_json) VALUES (?, ?, ?, ?, ?, ?);"
            cursor.execute(query, (origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_json_str))
            conn.commit()
            return cursor.lastrowid

    def add_or_get_element_universal(self, id_canonico, nome, tipo, perfil_json_data=None):
        existing = self.get_entity_details_by_canonical_id('elementos_universais', id_canonico)
        if existing: return existing['id']
        with self._get_connection() as conn:
            cursor = conn.cursor()
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO elementos_universais (id_canonico, nome, tipo, perfil_json) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str))
            conn.commit()
            return cursor.lastrowid

    def add_or_get_personagem(self, id_canonico, nome, tipo, perfil_json_data=None):
        existing = self.get_entity_details_by_canonical_id('personagens', id_canonico)
        if existing: return existing['id']
        with self._get_connection() as conn:
            cursor = conn.cursor()
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO personagens (id_canonico, nome, tipo, perfil_json) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str))
            conn.commit()
            return cursor.lastrowid

    def add_or_get_faccao(self, id_canonico, nome, tipo, perfil_json_data=None):
        existing = self.get_entity_details_by_canonical_id('faccoes', id_canonico)
        if existing: return existing['id']
        with self._get_connection() as conn:
            cursor = conn.cursor()
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO faccoes (id_canonico, nome, tipo, perfil_json) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str))
            conn.commit()
            return cursor.lastrowid

    # --- NOVA FUNÇÃO ADICIONADA ---
    def add_log_memory(self, jogador_id_canonico, tipo, conteudo, timestamp_evento=None):
        """
        Adiciona um novo registro de log ou memória consolidada para o jogador.
        """
        if timestamp_evento is None:
            timestamp_evento = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Busca o ID numérico do jogador a partir do ID canônico
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res:
                print(f"ERRO: Jogador com ID canônico '{jogador_id_canonico}' não encontrado. Log não pode ser adicionado.")
                return None
            player_db_id = player_res['id']

            # Insere o novo log na tabela
            query = "INSERT INTO jogador_logs_memoria (jogador_id, tipo, conteudo, timestamp_evento) VALUES (?, ?, ?, ?);"
            cursor.execute(query, (player_db_id, tipo, conteudo, timestamp_evento))
            conn.commit()
            
            print(f"INFO: Log do tipo '{tipo}' adicionado para o jogador '{jogador_id_canonico}'.")
            return cursor.lastrowid
