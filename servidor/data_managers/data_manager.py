import sqlite3
import json
import os
import datetime
from langchain.tools import tool
from config import config

class DataManager:
    """
    Gerencia todas as interações com o banco de dados SQLite para uma sessão de jogo.
    Versão: 7.1.0 - Adicionadas anotações @tool para expor as funções ao LLM.
    """
    def __init__(self, session_name: str, supress_success_message=False):
        os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
        self.session_name = session_name
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados para a sessão '{session_name}' não foi encontrada.")
        if not supress_success_message:
            print(f"DataManager (v7.1.0) conectado com sucesso à sessão: {self.session_name} ({self.db_path})")

    def _get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite '{self.db_path}': {e}")
            raise

    # --- Ferramentas Expostas ao LLM ---

    @tool
    def add_or_get_location(self, id_canonico: str, nome: str, tipo: str, perfil_json_data: dict = None, parent_id_canonico: str = None):
        """
        Cria um novo local no universo (planeta, cidade, sala) ou obtém os detalhes de um local existente.
        Use esta função para estabelecer a existência de qualquer local antes de interagir com ele.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM locais WHERE id_canonico = ?", (id_canonico,))
            existing = cursor.fetchone()
            if existing:
                return dict(existing)
            
            parent_id_numerico = None
            if parent_id_canonico:
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (parent_id_canonico,))
                parent_loc = cursor.fetchone()
                if parent_loc:
                    parent_id_numerico = parent_loc['id']
            
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO locais (id_canonico, nome, tipo, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str, parent_id_numerico))
            conn.commit()
            return {"id": cursor.lastrowid, "id_canonico": id_canonico, "nome": nome, "tipo": tipo}

    @tool
    def add_or_get_player(self, id_canonico: str, nome: str, local_inicial_id_canonico: str, perfil_completo_data: dict):
        """
        Cria o personagem do jogador no início do jogo, associando-o a um local inicial.
        Esta função deve ser chamada apenas uma vez por sessão, no primeiro turno.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jogador WHERE id_canonico = ?", (id_canonico,))
            existing_player = cursor.fetchone()
            if existing_player:
                return dict(existing_player)

            cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (local_inicial_id_canonico,))
            local_res = cursor.fetchone()
            if not local_res:
                raise ValueError(f"Local inicial '{local_inicial_id_canonico}' não encontrado.")
            
            local_inicial_id_numerico = local_res['id']
            perfil_json_str = json.dumps(perfil_completo_data)
            
            cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                           (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
            conn.commit()
            return {"id": cursor.lastrowid, "id_canonico": id_canonico, "nome": nome}
    
    @tool
    def add_player_vitals(self, jogador_id_canonico: str, fome: str = "Normal", sede: str = "Normal", cansaco: str = "Descansado", humor: str = "Neutro", motivacao: str = "Neutro"):
        """Adiciona ou atualiza o status físico e emocional (vitals) do jogador."""
        timestamp_atual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
            player_res = cursor.fetchone()
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

    @tool
    def add_player_skill(self, jogador_id_canonico: str, categoria: str, nome: str, nivel_subnivel: str = None, observacoes: str = None):
        """Adiciona uma nova habilidade para o jogador. A duplicatas são ignoradas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
            player_res = cursor.fetchone()
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel_subnivel, observacoes))
            conn.commit()
            return cursor.rowcount > 0

    @tool
    def add_player_knowledge(self, jogador_id_canonico: str, categoria: str, nome: str, nivel: int = 1, descricao: str = None):
        """Adiciona um novo conhecimento para o jogador. Duplicatas são ignoradas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
            player_res = cursor.fetchone()
            if not player_res: return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel, descricao))
            conn.commit()
            return cursor.rowcount > 0

    @tool
    def add_or_get_player_possession(self, jogador_id_canonico: str, item_nome: str, posse_id_canonico: str, perfil_json_data: dict = None):
        """Adiciona um item ao inventário do jogador ou obtém um item existente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jogador_posses WHERE id_canonico = ?", (posse_id_canonico,))
            existing_possession = cursor.fetchone()
            if existing_possession:
                return dict(existing_possession)

            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
            player_res = cursor.fetchone()
            if not player_res: return None
            player_db_id = player_res['id']
            
            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            cursor.execute("INSERT INTO jogador_posses (id_canonico, jogador_id, item_nome, perfil_json) VALUES (?, ?, ?, ?)",
                           (posse_id_canonico, player_db_id, item_nome, perfil_json_str))
            conn.commit()
            return {"id": cursor.lastrowid, "id_canonico": posse_id_canonico, "item_nome": item_nome}

    @tool
    def update_player_location(self, player_canonical_id: str, new_local_canonical_id: str):
        """Atualiza a localização atual do jogador. Use para movimentos explícitos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (new_local_canonical_id,))
            local_res = cursor.fetchone()
            if not local_res: return False
            new_local_id = local_res['id']
            cursor.execute("UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?", (new_local_id, player_canonical_id))
            conn.commit()
            return cursor.rowcount > 0

    @tool
    def add_or_get_personagem(self, id_canonico: str, nome: str, tipo: str, perfil_json_data: dict = None):
        """Cria um novo personagem (NPC) se ele não existir, ou obtém um existente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM personagens WHERE id_canonico = ?", (id_canonico,))
            existing_char = cursor.fetchone()
            if existing_char:
                return dict(existing_char)

            perfil_json_str = json.dumps(perfil_json_data) if perfil_json_data else None
            query = "INSERT INTO personagens (id_canonico, nome, tipo, perfil_json) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str))
            conn.commit()
            return {"id": cursor.lastrowid, "id_canonico": id_canonico, "nome": nome}

    @tool
    def add_log_memory(self, jogador_id_canonico: str, tipo: str, conteudo: str):
        """Adiciona um registro de log de evento ou memória consolidada para o jogador."""
        timestamp_evento = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
            player_res = cursor.fetchone()
            if not player_res: return None
            player_db_id = player_res['id']

            query = "INSERT INTO jogador_logs_memoria (jogador_id, tipo, conteudo, timestamp_evento) VALUES (?, ?, ?, ?);"
            cursor.execute(query, (player_db_id, tipo, conteudo, timestamp_evento))
            conn.commit()
            return cursor.lastrowid

    # --- Funções Internas (Não expostas como ferramentas) ---
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

    def get_player_full_status(self, player_canonical_id=None):
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if not player_canonical_id:
                    cursor.execute("SELECT id_canonico FROM jogador LIMIT 1")
                    player_res = cursor.fetchone()
                    if not player_res: return None
                    player_canonical_id = player_res['id_canonico']
                
                cursor.execute("SELECT * FROM jogador WHERE id_canonico = ?", (player_canonical_id,))
                player_info_res = cursor.fetchone()
                if not player_info_res: return None
                player_info = dict(player_info_res)
                player_db_id = player_info['id']

                local_info = {}
                if player_info.get('local_atual_id'):
                    cursor.execute("SELECT * FROM locais WHERE id = ?", (player_info['local_atual_id'],))
                    local_info_res = cursor.fetchone()
                    if local_info_res:
                        local_info = dict(local_info_res)

                player_status['base'] = {**player_info, 'local_nome': local_info.get('nome', 'Desconhecido')}
                
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
