# src/database/sqlite_manager.py
import sqlite3
import json
import os
import datetime
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from src import config

# --- Modelos Pydantic para Validação de Argumentos das Ferramentas ---

class AddOrGetLocationArgs(BaseModel):
    id_canonico: str = Field(description="ID canónico único do local (ex: 'estacao_alfa', 'planeta_gaia').")
    nome: str = Field(description="Nome legível do local.")
    tipo: str = Field(description="Tipo do local (STRING LIVRE, ex: 'Estação Espacial', 'Planeta', 'Sala').")
    perfil_json_data: Optional[Dict] = Field(None, description="Dados adicionais do local em formato de dicionário (ex: {'descricao': 'Um hub de comércio.'}).")
    parent_id_canonico: Optional[str] = Field(None, description="ID canónico do local pai, se houver (ex: uma sala dentro de uma estação).")

class AddOrGetPlayerArgs(BaseModel):
    id_canonico: str = Field(description="ID canónico único e criativo para o jogador (ex: 'pj_kael_o_explorador').")
    nome: str = Field(description="Nome do jogador.")
    local_inicial_id_canonico: str = Field(description="ID canónico do local onde o jogador inicia.")
    perfil_completo_data: Dict = Field(description="Dados completos do perfil do jogador em formato de dicionário (ex: {'raca': 'Humano', 'ocupacao': 'Explorador'}).")
    world_concept: str = Field("", description="O conceito do mundo para esta saga.")

class AddPlayerSkillArgs(BaseModel):
    jogador_id_canonico: str = Field(description="ID canónico do jogador.")
    categoria: str = Field(description="Categoria da habilidade (ex: 'Exploração', 'Combate').")
    nome: str = Field(description="Nome da habilidade (ex: 'Navegação Espacial', 'Tiro Preciso').")
    nivel_subnivel: Optional[str] = Field(None, description="Nível ou subnível da habilidade (ex: 'Novato', 'Avançado').")
    observacoes: Optional[str] = Field(None, description="Observações adicionais sobre a habilidade.")

class AddPlayerKnowledgeArgs(BaseModel):
    jogador_id_canonico: str = Field(description="ID canónico do jogador.")
    categoria: str = Field(description="Categoria do conhecimento (ex: 'Ciência', 'História').")
    nome: str = Field(description="Nome do conhecimento (ex: 'Anomalias Gravitacionais', 'Cultura Antiga').")
    nivel: int = Field(1, description="Nível do conhecimento (1-5).")
    descricao: Optional[str] = Field(None, description="Descrição detalhada do conhecimento.")

class AddOrGetPlayerPossessionArgs(BaseModel):
    jogador_id_canonico: str = Field(description="ID canónico do jogador.")
    item_nome: str = Field(description="Nome do item (ex: 'Kit de Sobrevivência').")
    posse_id_canonico: str = Field(description="ID canónico único da posse (ex: 'kit_sobrevivencia_gabriel').")
    perfil_json_data: Optional[Dict] = Field(None, description="Dados adicionais da posse em formato de dicionário (ex: {'estado': 'novo'}).")

class AddLogMemoryArgs(BaseModel):
    jogador_id_canonico: str = Field(description="ID canónico do jogador.")
    tipo: str = Field(description="Tipo de log (ex: 'log_evento', 'memoria_consolidada').")
    conteudo: str = Field(description="Conteúdo do log ou memória.")

class SqliteManager:
    """
    Gere todas as interações com a base de dados SQLite para uma sessão de jogo específica.
    Versão: 9.0.0 - Refatorado para máxima compatibilidade com LangChain, com assinaturas de função explícitas.
    """
    def __init__(self, session_name: str, supress_success_message=False):
        os.makedirs(config.PROD_DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(config.PROD_DATA_DIR, f"{session_name}.db")
        self.session_name = session_name
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados para a sessão '{session_name}' não foi encontrada.")
        if not supress_success_message:
            print(f"DataManager v9.0.0 conectado com sucesso à sessão: {self.session_name} ({self.db_path})")

    def _get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite '{self.db_path}': {e}")
            raise

    # --- Funções de Leitura Internas ---

    def get_entity_details_by_canonical_id(self, table_name: str, canonical_id: str) -> Optional[Dict]:
        # ... (código existente sem alterações)
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

    def get_all_entities_from_table(self, table_name: str) -> List[Dict]:
        # ... (código existente sem alterações)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                tabelas_validas = [
                    'locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                    'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                    'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                    'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'itens',
                    'sagas' # Adicionado para buscar o conceito do mundo
                ]
                if table_name not in tabelas_validas:
                    raise ValueError(f"Nome de tabela inválido para exportação: '{table_name}'.")
                
                query = f"SELECT * FROM {table_name}"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError) as e:
            print(f"ERRO ao obter todos os dados da tabela '{table_name}': {e}")
            return []
    
    def get_player_full_status(self, player_canonical_id: Optional[str] = None) -> Optional[Dict]:
        # ... (código existente sem alterações)
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
                if not player_info:
                    return None
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

    def get_ancestors(self, local_id_numeric: int) -> List[Dict]:
        # ... (código existente sem alterações)
        with self._get_connection() as conn:
            cursor = conn.cursor()
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
            cursor.execute(query, (local_id_numeric,))
            return [dict(row) for row in cursor.fetchall()]

    def get_children(self, local_id_numeric: int) -> List[Dict]:
        # ... (código existente sem alterações)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT l.id, l.id_canonico, l.nome, l.tipo FROM locais l WHERE l.parent_id = ?;"
            cursor.execute(query, (local_id_numeric,))
            return [dict(row) for row in cursor.fetchall()]

    def get_direct_accesses(self, local_id_numeric: int) -> List[Dict]:
        # ... (código existente sem alterações)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT l.id, l.id_canonico, l.nome, l.tipo, lad.tipo_acesso, lad.condicoes_acesso
                FROM locais_acessos_diretos lad
                JOIN locais l ON lad.local_destino_id = l.id
                WHERE lad.local_origem_id = ?;
            """
            cursor.execute(query, (local_id_numeric,))
            return [dict(row) for row in cursor.fetchall()]

    def get_siblings(self, local_id_numeric: int) -> List[Dict]:
        # ... (código existente sem alterações)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT parent_id FROM locais WHERE id = ?", (local_id_numeric,))
            res = cursor.fetchone()
            if not res or not res['parent_id']:
                return []
            parent_id = res['parent_id']
            query = "SELECT l.id, l.id_canonico, l.nome, l.tipo FROM locais l WHERE l.parent_id = ? AND l.id != ?;"
            cursor.execute(query, (parent_id, local_id_numeric))
            return [dict(row) for row in cursor.fetchall()]

    # --- FERRAMENTAS (WRITE) EXPOSTAS PARA O LLM ---

    @tool(args_schema=AddOrGetLocationArgs)
    def add_or_get_location(self, id_canonico: str, nome: str, tipo: str, perfil_json_data: Optional[Dict] = None, parent_id_canonico: Optional[str] = None) -> int:
        """Cria um novo local (planeta, estação, sala) ou obtém o ID de um local existente."""
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
            
            perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
            query = "INSERT INTO locais (id_canonico, nome, tipo, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
            cursor.execute(query, (id_canonico, nome, tipo, perfil_json_str, parent_id_numerico))
            conn.commit()
            return cursor.lastrowid

    @tool(args_schema=AddOrGetPlayerArgs)
    def add_or_get_player(self, id_canonico: str, nome: str, local_inicial_id_canonico: str, perfil_completo_data: Dict, world_concept: str) -> int:
        """Cria o personagem jogador principal, associando-o a um local inicial e guardando o conceito do mundo."""
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
            perfil_json_str = json.dumps(perfil_completo_data, ensure_ascii=False)
            
            cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                           (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
            
            # Guarda o conceito do mundo na tabela 'sagas'
            cursor.execute("INSERT INTO sagas (session_name, player_name, world_concept) VALUES (?, ?, ?)",
                           (self.session_name, nome, world_concept))
            conn.commit()
            return cursor.lastrowid

    @tool(args_schema=AddPlayerSkillArgs)
    def add_player_skill(self, jogador_id_canonico: str, categoria: str, nome: str, nivel_subnivel: Optional[str] = None, observacoes: Optional[str] = None) -> bool:
        """Adiciona uma nova habilidade ao jogador. Ignora se já existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res:
                print(f"ERRO: Jogador '{jogador_id_canonico}' não encontrado. Habilidade não pode ser adicionada.")
                return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel_subnivel, observacoes))
            conn.commit()
            return cursor.rowcount > 0

    @tool(args_schema=AddPlayerKnowledgeArgs)
    def add_player_knowledge(self, jogador_id_canonico: str, categoria: str, nome: str, nivel: int = 1, descricao: Optional[str] = None) -> bool:
        """Adiciona um novo conhecimento ao jogador. Ignora se já existir."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico)
            if not player_res:
                print(f"ERRO: Jogador '{jogador_id_canonico}' não encontrado. Conhecimento não pode ser adicionado.")
                return False
            player_db_id = player_res['id']
            cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                           (player_db_id, categoria, nome, nivel, descricao))
            conn.commit()
            return cursor.rowcount > 0

    @tool(args_schema=AddOrGetPlayerPossessionArgs)
    def add_or_get_player_possession(self, jogador_id_canonico: str, item_nome: str, posse_id_canonico: str, perfil_json_data: Optional[Dict] = None) -> int:
        """Adiciona um item ao inventário do jogador."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jogador_posses WHERE id_canonico = ?", (posse_id_canonico,))
            existing = cursor.fetchone()
            if existing:
                return existing['id']

            player_res = self.get_entity_details_by_canonical_id('jogador', jogador_id_canonico) # type: ignore
            if not player_res:
                print(f"ERRO: Jogador '{jogador_id_canonico}' não encontrado. Posse não pode ser adicionada.")
                return None
            player_db_id = player_res['id']
            
            perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
            cursor.execute("INSERT INTO jogador_posses (id_canonico, jogador_id, item_nome, perfil_json) VALUES (?, ?, ?, ?)",
                           (posse_id_canonico, player_db_id, item_nome, perfil_json_str))
            conn.commit()
            return cursor.lastrowid

    @tool(args_schema=AddLogMemoryArgs)
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
            conn.commit()
            return cursor.lastrowid
