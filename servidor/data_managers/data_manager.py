# servidor/data_managers/data_manager.py
import sqlite3
import json
import os
import datetime
from langchain.tools import tool
from typing import Optional, Dict
from config import config

class DataManager:
    """
    Gerencia todas as interações com o banco de dados SQLite para uma sessão de jogo específica.
    Versão: 7.3.0 - Reforçadas as assinaturas de tipo das ferramentas para maior robustez com Pydantic.
    """
    def __init__(self, session_name: str, supress_success_message=False):
        os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
        self.session_name = session_name
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados para a sessão '{session_name}' não foi encontrada.")
        if not supress_success_message:
            print(f"DataManager (v7.3.0) conectado com sucesso à sessão: {self.session_name} ({self.db_path})")

    def _get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite '{self.db_path}': {e}")
            raise

    # --- Funções de Leitura (Não são ferramentas, são usadas internamente) ---

    def get_entity_details_by_canonical_id(self, table_name, canonical_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = [
                    'locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                    'jogador_posses', 'itens'
                ]
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido ou não suportado para busca por ID canônico: '{table_name}'.")
                
                query = f"SELECT * FROM {table_name} WHERE id_canonico = ?"
                cursor.execute(query, (canonical_id,))
                resultado = cursor.fetchone()
                
                return dict(resultado) if resultado else None
        except (sqlite3.Error, ValueError) as e:
            print(f"Erro ao buscar entidade '{canonical_id}' em '{table_name}': {e}")
            return None
            
    def get_all_entities_from_table(self, table_name):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = [
                    'locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                    'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                    'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                    'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'itens'
                ]
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido para exportação: '{table_name}'.")
                
                query = f"SELECT * FROM {table_name}"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError) as e:
            print(f"ERRO ao obter todos os dados da tabela '{table_name}': {e}")
            return []

    def get_player_full_status(self, player_canonical_id: Optional[str] = None):
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if not player_canonical_id:
                    cursor.execute("SELECT id_canonico FROM jogador LIMIT 1")
                    player_res = cursor.fetchone()
                    if not player_res:
                        return None 
                    player_canonical_id = player_res['id_canonico']
                
                player_info = self.get_entity_details_by_canonical_id('jogador', player_canonical_id)
                if not player_info: return None
                player_db_id = player_info['id']

                query_local = "SELECT l.id as local_id, l.id_canonico as local_id_canonico, l.nome as local_nome, l.tipo as local_tipo FROM locais l WHERE l.id = ?"
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

    # --- FERRAMENTAS (WRITE) EXPOSTAS PARA O LLM ---

    @tool
    def add_or_get_location(self, id_canonico: str, nome: str, tipo: str, perfil_json_data: Optional[Dict] = None, parent_id_canonico: Optional[str] = None) -> int:
        """
        Cria um novo local (planeta, estação, sala) ou obtém o ID de um local existente. É idempotente.
        Use esta ferramenta para estabelecer a existência de qualquer lugar no universo do jogo.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (id_canonico,))
            existing = cursor.fetchone()
            if existing:
                return existing['id']
            
            parent_id_numerico = None
            if parent_id_canonico:
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (parent_id_canonico,))
                parent_loc = cursor.fetchone()
                if parent_loc:
                    parent_id_numerico = parent_loc['id']
            
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO locais (id_canonico, nome, tipo, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str, parent_id_numerico))
            return cursor.lastrowid

    @tool
    def add_or_get_player(self, id_canonico: str, nome: str, local_inicial_id_canonico: str, perfil_completo_data: Dict) -> int:
        """Cria o personagem jogador principal se ele não existir, associando-o a um local inicial."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (id_canonico,))
            if cursor.fetchone():
                return self.get_entity_details_by_canonical_id('jogador', id_canonico)['id']

            cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (local_inicial_id_canonico,))
            local_res = cursor.fetchone()
            if not local_res:
                raise ValueError(f"Local inicial '{local_inicial_id_canonico}' não encontrado.")
            
            local_inicial_id_numerico = local_res['id']
            perfil_json_str = json.dumps(perfil_completo_data)
            
            cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                           (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
            return cursor.lastrowid

    @tool
    def add_player_vitals(self, jogador_id_canonico: str, fome: str = "Normal", sede: str = "Normal", cansaco: str = "Descansado", humor: str = "Neutro", motivacao: str = "Neutro") -> bool:
        """Adiciona ou atualiza os status vitais (fome, sede, etc.) do jogador."""
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
            return True

    @tool
    def add_player_skill(self, jogador_id_canonico: str, categoria: str, nome: str, nivel_subnivel: Optional[str] = None, observacoes: Optional[str] = None) -> bool:
        """Adiciona uma nova habilidade (ex: 'Combate', 'Tiro Preciso') ao jogador. Ignora se já existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel_subnivel, observacoes))
            return cursor.rowcount > 0

    @tool
    def add_player_knowledge(self, jogador_id_canonico: str, categoria: str, nome: str, nivel: int = 1, descricao: Optional[str] = None) -> bool:
        """Adiciona um novo conhecimento (ex: 'Ciência', 'Cultura Antiga') ao jogador. Ignora se já existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel, descricao))
            return cursor.rowcount > 0

    @tool
    def add_or_get_player_possession(self, jogador_id_canonico: str, item_nome: str, posse_id_canonico: str, perfil_json_data: Optional[Dict] = None) -> int:
        """Adiciona um item ao inventário do jogador, como um 'traje espacial' ou uma 'arma'."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador_posses WHERE id_canonico = ?", (posse_id_canonico,))
            if cursor.fetchone():
                return self.get_entity_details_by_canonical_id('jogador_posses', posse_id_canonico)['id']

            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res: return None
            player_db_id = player_res['id']
            
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            cursor.execute("INSERT INTO jogador_posses (id_canonico, jogador_id, item_nome, perfil_json) VALUES (?, ?, ?, ?)",
                           (posse_id_canonico, player_db_id, item_nome, perfil_json_str))
            return cursor.lastrowid

    @tool
    def update_player_location(self, player_canonical_id: str, new_local_canonical_id: str) -> bool:
        """Move o jogador para um novo local."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            local_res = self.get_entity_details_by_canonical_id('locais', new_local_canonical_id)
            if not local_res: return False
            new_local_id = local_res['id']
            cursor.execute("UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?", (new_local_id, player_canonical_id))
            return cursor.rowcount > 0

    @tool
    def add_universal_relation(self, origem_id_canonico: str, origem_tipo_tabela: str, tipo_relacao: str, destino_id_canonico: str, destino_tipo_tabela: str, propriedades_data: Optional[Dict] = None) -> int:
        """Cria uma relação genérica entre quaisquer duas entidades (ex: Gabriel 'MEMBRO_DE' Frota Estelar)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            propriedades_json_str = json.dumps(propriedades_data) if propriedades_data else None
            query = "INSERT OR IGNORE INTO relacoes_entidades (entidade_origem_id, entidade_origem_tipo, tipo_relacao, entidade_destino_id, entidade_destino_tipo, propriedades_json) VALUES (?, ?, ?, ?, ?, ?);"
            cursor.execute(query, (origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_json_str))
            return cursor.lastrowid

    @tool
    def add_or_get_personagem(self, id_canonico: str, nome: str, tipo: str, perfil_json_data: Optional[Dict] = None) -> int:
        """Cria um novo personagem (NPC) se ele não existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM personagens WHERE id_canonico = ?", (id_canonico,))
            if cursor.fetchone():
                return self.get_entity_details_by_canonical_id('personagens', id_canonico)['id']

            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO personagens (id_canonico, nome, tipo, perfil_json) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str))
            return cursor.lastrowid
            
    @tool
    def add_log_memory(self, jogador_id_canonico: str, tipo: str, conteudo: str) -> int:
        """Adiciona um novo registro de log de evento ou memória consolidada para o jogador."""
        timestamp_evento = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res:
                print(f"ERRO: Jogador '{jogador_id_canonico}' não encontrado. Log não pode ser adicionado.")
                return None
            player_db_id = player_res['id']
            query = "INSERT INTO jogador_logs_memoria (jogador_id, tipo, conteudo, timestamp_evento) VALUES (?, ?, ?, ?);"
            cursor.execute(query, (player_db_id, tipo, conteudo, timestamp_evento))
            return cursor.lastrowid
