import sqlite3
import os
import json
import datetime
import sys

# Add the project root directory to sys.path so that the config module can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
sys.path.append(os.path.join(PROJECT_ROOT, 'data')) # Added to import entity_types_data

# Import global configurations
import config as config 
# Import the entity type data for helper functions
import entity_types_data as entity_types_data # type: ignore

class DataManager:
    """
    World API (v5.15) - The only layer that DIRECTLY interacts with the SQLite database.
    Abstracts SQL queries and provides methods for the game engine
    to get and modify the state of the universe.
    (Change: add_new_entity_type now supports display_name and parent_tipo_id,
             _get_type_id returns full type info,
             get_entity_details_by_canonical_id uses display_name.
             Version: 5.15)
    """

    def __init__(self, db_path=config.DB_PATH_SQLITE): 
        """
        Initializes the DataManager and establishes the connection to the database.
        """
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"The database was not found at '{self.db_path}'. "
                                    "Please run the 'scripts/build_world.py' script first to create the empty schema.")
        print(f"DataManager (v5.15) connected successfully to: {self.db_path}")

    def _get_connection(self):
        """Returns a new database connection with Row Factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _get_type_info(self, table_name, name_type=None, type_id=None):
        """
        Gets full information about an entity type from the tipos_entidades table
        by name_type or by type_id.
        Returns a dictionary with 'id', 'nome_tabela', 'nome_tipo', 'display_name', 'parent_tipo_id'.
        Returns None if the type is not found, and prints an ERROR.
        """
        if not name_type and not type_id:
            print("ERROR: Either 'name_type' or 'type_id' must be provided to _get_type_info.")
            return None
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id, nome_tabela, nome_tipo, display_name, parent_tipo_id FROM tipos_entidades WHERE nome_tabela = ?"
                params = [table_name]
                
                if name_type:
                    # Normalize name_type to snake_case for lookup
                    name_type_formatted = entity_types_data.to_snake_case(name_type)
                    query += " AND nome_tipo = ?"
                    params.append(name_type_formatted)
                elif type_id:
                    query += " AND id = ?"
                    params.append(type_id)

                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                if result:
                    return dict(result)
                else:
                    if name_type:
                        print(f"ERROR: Type '{name_type}' for table '{table_name}' not found in 'tipos_entidades'.")
                    elif type_id:
                        print(f"ERROR: Type ID '{type_id}' for table '{table_name}' not found in 'tipos_entidades'.")
                    return None
        except sqlite3.Error as e:
            print(f"Error fetching type info for '{name_type or type_id}' in table '{table_name}': {e}")
            return None

    def _get_table_columns(self, table_name):
        """Returns a list of column names for a given table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            return [col[1] for col in cursor.fetchall()]

    # --- Generic Read Functions ---

    def get_entity_details_by_canonical_id(self, table_name, canonical_id):
        """
        Fetches the complete details of an entity by its canonical ID in any universal table.
        Performs JOIN with tipos_entidades if the table has a tipo_id column.
        Returns the complete row dictionary, including the internal ID ('id').
        Now includes 'tipo_display_name' from tipos_entidades.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Validate table name for security
                valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 'jogador_posses', 'tipos_entidades', 'locais_acessos_diretos', 'relacoes_entidades', 'jogador_habilidades', 'jogador_conhecimentos', 'jogador_status_fisico_emocional', 'jogador_logs_memoria', 'local_elementos']
                if table_name not in valid_tables:
                    raise ValueError(f"Invalid table name: '{table_name}'. Use one of the following: {', '.join(valid_tables)}")
                
                columns = self._get_table_columns(table_name)
                
                if 'tipo_id' in columns:
                    query = f"""
                        SELECT t1.*, t2.nome_tipo AS tipo_nome_interno, t2.display_name AS tipo_display_name
                        FROM {table_name} t1
                        LEFT JOIN tipos_entidades t2 ON t1.tipo_id = t2.id
                        WHERE t1.id_canonico = ?
                    """
                elif 'id_canonico' in columns: # For tables without tipo_id, but with id_canonico (e.g., jogador, jogador_posses)
                    query = f"SELECT * FROM {table_name} WHERE id_canonico = ?"
                else: # For relationship tables that do not have id_canonico as primary key
                    # This case is more complex, as relacoes_entidades and locais_acessos_diretos
                    # do not have their own id_canonico as PK, but can be searched by their related entities
                    # For simplicity, we will allow get_entity_details_by_canonical_id to return None
                    # and handle this in specific calls (e.g., get_all_entities_from_table for synchronization)
                    return None # Not supported to search by id_canonico for tables without it as primary/unique key

                cursor.execute(query, (canonical_id,))
                resultado = cursor.fetchone()
                
                if resultado:
                    result_dict = dict(resultado)
                    # Rename 'tipo_display_name' to 'tipo' in the result if it exists for simpler access
                    if 'tipo_display_name' in result_dict:
                        result_dict['tipo'] = result_dict.pop('tipo_display_name')
                    # Also include the internal type name if available
                    if 'tipo_nome_interno' in result_dict:
                        result_dict['tipo_nome_interno'] = result_dict.pop('tipo_nome_interno')
                    return result_dict
                return None
        except (sqlite3.Error, ValueError) as e:
            print(f"Error fetching entity '{canonical_id}' in '{table_name}': {e}")
            return None
    
    def get_all_entities_from_table(self, table_name):
        """
        Returns all records from a specified table.
        Ideal for mass export to other pillars.
        When fetching from tables with 'tipo_id', it now includes 'nome_tipo' and 'display_name' from 'tipos_entidades'.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Validate table name
                valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador', 
                                   'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                                   'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                                   'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'tipos_entidades']
                if table_name not in valid_tables:
                    raise ValueError(f"Invalid table name for export: '{table_name}'.")
                
                # Special handling for tables that might have tipo_id to include display_name
                if table_name in ['locais', 'elementos_universais', 'personagens', 'faccoes']:
                    query = f"""
                        SELECT t1.*, t2.nome_tipo, t2.display_name
                        FROM {table_name} t1
                        LEFT JOIN tipos_entidades t2 ON t1.tipo_id = t2.id
                    """
                else:
                    query = f"SELECT * FROM {table_name}"
                
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except (sqlite3.Error, ValueError) as e:
            print(f"ERROR getting all data from table '{table_name}': {e}")
            return []
            
    # --- Local Reading Functions (Hierarchy and Accesses) ---

    def get_ancestors(self, local_id_numerico):
        """Returns the ancestor chain of a location by its numeric ID."""
        query = """
            WITH RECURSIVE get_ancestors(id, id_canonico, nome, tipo_id, parent_id, nivel) AS (
                SELECT id, id_canonico, nome, tipo_id, parent_id, 0 FROM locais WHERE id = ?
                UNION ALL
                SELECT l.id, l.id_canonico, l.nome, l.tipo_id, l.parent_id, ga.nivel + 1
                FROM locais l JOIN get_ancestors ga ON l.id = ga.parent_id
            )
            SELECT ga.id, ga.id_canonico, ga.nome, te.display_name AS tipo, ga.nivel
            FROM get_ancestors ga
            LEFT JOIN tipos_entidades te ON ga.tipo_id = te.id
            ORDER BY nivel DESC;
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching ancestors for local ID {local_id_numerico}: {e}")
            return []

    def get_children(self, local_id_numerico):
        """Returns the direct children of a location (what is contained within it)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.parent_id = ?;
                """
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching children for local ID {local_id_numerico}: {e}")
            return []

    def get_direct_accesses(self, local_id_numerico):
        """Returns locations directly accessible from a location."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo, lad.tipo_acesso, lad.condicoes_acesso
                    FROM locais_acessos_diretos lad
                    JOIN locais l ON lad.local_destino_id = l.id
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE lad.local_origem_id = ?;
                """
                cursor.execute(query, (local_id_numerico,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching direct accesses for local ID {local_id_numerico}: {e}")
            return []

    def get_siblings(self, local_id_numerico):
        """
        Returns "neighboring" locations (that share the same parent).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT parent_id FROM locais WHERE id = ?", (local_id_numerico,))
                res = cursor.fetchone()
                if not res or res['parent_id'] is None: # Added 'is None' for roots
                    return []
                
                parent_id = res['parent_id']
                
                query = """
                    SELECT l.id, l.id_canonico, l.nome, te.display_name AS tipo
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.parent_id = ? AND l.id != ?;
                """
                cursor.execute(query, (parent_id, local_id_numerico))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching neighbors for local ID {local_id_numerico}: {e}")
            return []

    # --- Player Reading Functions ---

    def get_player_full_status(self, player_canonical_id=config.DEFAULT_PLAYER_ID_CANONICO): # Uses config.DEFAULT_PLAYER_ID_CANONICO
        """Fetches and aggregates all player status information."""
        player_status = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                player_info = self.get_entity_details_by_canonical_id('jogador', player_canonical_id)
                if not player_info: return None
                player_db_id = player_info['id'] # The internal ID of the player

                # Also fetch the canonical ID of the location for easier use
                # Query adapted to get display_name of the location
                query_local = """
                    SELECT l.id as local_id, l.id_canonico as local_id_canonico, l.nome as local_nome, te.display_name as local_tipo
                    FROM locais l
                    LEFT JOIN tipos_entidades te ON l.tipo_id = te.id
                    WHERE l.id = ?
                """
                cursor.execute(query_local, (player_info['local_atual_id'],))
                local_info = cursor.fetchone()

                # Ensures that 'local_info' is a dictionary before unpacking
                player_status['base'] = {**player_info, **(dict(local_info) if local_info else {})}
                
                cursor.execute("SELECT * FROM jogador_habilidades WHERE jogador_id = ?", (player_db_id,))
                player_status['habilidades'] = [dict(row) for row in cursor.fetchall()]
                
                cursor.execute("SELECT * FROM jogador_conhecimentos WHERE jogador_id = ?", (player_db_id,))
                player_status['conhecimentos'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_posses WHERE jogador_id = ?", (player_db_id,))
                player_status['posses'] = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
                vitals = cursor.fetchone()
                player_status['vitals'] = dict(vitals) if vitals else {} # Ensures it's a dictionary even if there's no data

                # Logs now use timestamp_evento
                cursor.execute("SELECT * FROM jogador_logs_memoria WHERE jogador_id = ? ORDER BY id DESC LIMIT 5", (player_db_id,))
                player_status['logs_recentes'] = [dict(row) for row in cursor.fetchall()]

            return player_status
        except sqlite3.Error as e:
            print(f"Error fetching full player status: {e}")
            return None

    # --- Write Functions for Dynamic Canonization ---

    def add_location(self, id_canonico, nome, tipo_nome, perfil_json_data=None, parent_id_canonico=None):
        """Adds a new location to the universe (Canonization).
        'tipo_nome' should be the textual name of the type (e.g., 'Estação Espacial')."""
        
        type_info = self._get_type_info('locais', name_type=tipo_nome)
        if type_info is None:
            # If the specific type doesn't exist, try to add it dynamically
            # For simplicity, we assume generic types already exist or are added by build_world.
            # Here, if a very specific sub-type is passed, we might need a more complex
            # logic to add it first if it's new (handled by add_new_entity_type from LLM).
            # For now, if _get_type_info fails, it means the type (or its normalized form) isn't in DB.
            return None 
        
        tipo_id_numerico = type_info['id']

        parent_id_numerico = None
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if parent_id_canonico:
                    cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (parent_id_canonico,))
                    parent_res = cursor.fetchone()
                    if not parent_res:
                        print(f"WARNING: Canonical Parent ID '{parent_id_canonico}' not found for location '{id_canonico}'. Inserting as root.")
                    else:
                        parent_id_numerico = parent_res['id']
                
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                
                query = "INSERT INTO locais (id_canonico, nome, tipo_id, perfil_json, parent_id) VALUES (?, ?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str, parent_id_numerico))
                new_local_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Location '{nome}' ({id_canonico}) added with ID {new_local_id}.")
                
                return new_local_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding location '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_location(self, id_canonico, nome, tipo_nome, perfil_json_data=None, parent_id_canonico=None):
        """
        Checks if a location with the canonical_id already exists. If it exists, returns its details.
        Otherwise, creates the new location and returns its details.
        """
        existing_loc = self.get_entity_details_by_canonical_id('locais', id_canonico)
        if existing_loc:
            print(f"INFO: Location '{nome}' ({id_canonico}) already exists. Using existing one.")
            return existing_loc['id'] # Returns the internal ID
        else:
            print(f"INFO: Location '{nome}' ({id_canonico}) not found. Creating new location.")
            return self.add_location(id_canonico, nome, tipo_nome, perfil_json_data, parent_id_canonico)

    def add_player(self, id_canonico, nome, local_inicial_id_canonico, perfil_completo_data):
        """
        Adds a new player to the database and sets their initial location.
        'creditos_conta' and other attributes should now come INSIDE 'perfil_completo_data'.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if the initial location exists
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (local_inicial_id_canonico,))
                local_res = cursor.fetchone()
                if not local_res:
                    print(f"ERROR: Initial location '{local_inicial_id_canonico}' not found. Player cannot be created.")
                    return None
                
                local_inicial_id_numerico = local_res['id']
                perfil_json_str = json.dumps(perfil_completo_data, ensure_ascii=False)

                cursor.execute("INSERT INTO jogador (id_canonico, nome, local_atual_id, perfil_completo_json) VALUES (?, ?, ?, ?)",
                               (id_canonico, nome, local_inicial_id_numerico, perfil_json_str))
                player_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Player '{nome}' ({id_canonico}) created with ID {player_id} at location '{local_inicial_id_canonico}'.")
                
                return player_id
        except sqlite3.IntegrityError as e:
            print(f"ERROR: Player with canonical ID '{id_canonico}' already exists: {e}")
            conn.rollback()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding player '{nome}': {e}")
            return None

    def add_or_get_player(self, id_canonico, nome, local_inicial_id_canonico, perfil_completo_data):
        """
        Checks if a player with the canonical_id already exists. If it exists, returns their details.
        Otherwise, creates the new player and returns their details.
        """
        existing_player = self.get_entity_details_by_canonical_id('jogador', id_canonico)
        if existing_player:
            print(f"INFO: Player '{nome}' ({id_canonico}) already exists. Using existing one.")
            return existing_player['id']
        else:
            print(f"INFO: Player '{nome}' ({id_canonico}) not found. Creating new player.")
            return self.add_player(id_canonico, nome, local_inicial_id_canonico, perfil_completo_data)


    def add_player_vitals(self, jogador_id_canonico, fome="Normal", sede="Normal", cansaco="Descansado", humor="Neutro", motivacao="Neutro", timestamp_atual=None):
        """
        Adds or updates the player's physical and emotional status.
        'timestamp_atual' is now the only date/time field (YYYY-MM-DD HH:MM:SS format).
        """
        if timestamp_atual is None:
            timestamp_atual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res:
                    print(f"ERROR: Player with canonical ID '{jogador_id_canonico}' not found to add vitals.")
                    return False
                player_db_id = player_res['id']

                # Checks if a record already exists for the player
                cursor.execute("SELECT id FROM jogador_status_fisico_emocional WHERE jogador_id = ?", (player_db_id,))
                existing_vitals = cursor.fetchone()

                if existing_vitals:
                    query = """
                        UPDATE jogador_status_fisico_emocional
                        SET fome = ?, sede = ?, cansaco = ?, humor = ?, motivacao = ?, timestamp_atual = ?
                        WHERE jogador_id = ?;
                    """
                    cursor.execute(query, (fome, sede, cansaco, humor, motivacao, timestamp_atual, player_db_id))
                    print(f"INFO: Player vitals '{jogador_id_canonico}' updated.")
                else:
                    query = """
                        INSERT INTO jogador_status_fisico_emocional
                        (jogador_id, fome, sede, cansaco, humor, motivacao, timestamp_atual)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """
                    cursor.execute(query, (player_db_id, fome, sede, cansaco, humor, motivacao, timestamp_atual))
                    print(f"INFO: Initial vitals for player '{jogador_id_canonico}' added.")
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding/updating player vitals '{jogador_id_canonico}': {e}")
            return False

    def add_player_skill(self, jogador_id_canonico, categoria, nome, nivel_subnivel=None, observacoes=None):
        """Adds a new skill to the player. It is already idempotent."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                # Use INSERT OR IGNORE for skill idempotence (avoid duplicates, do not update)
                cursor.execute("INSERT OR IGNORE INTO jogador_habilidades (jogador_id, categoria, nome, nivel_subnivel, observacoes) VALUES (?, ?, ?, ?, ?)",
                               (player_db_id, categoria, nome, nivel_subnivel, observacoes))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Skill '{nome}' added for '{jogador_id_canonico}'.")
                    return True
                else:
                    print(f"INFO: Skill '{nome}' for '{jogador_id_canonico}' already exists (ignored).")
                    return False # Returns False if ignored (nothing new was added)

        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding skill for '{jogador_id_canonico}': {e}")
            return False

    def add_player_knowledge(self, jogador_id_canonico, categoria, nome, nivel=1, descricao=None):
        """Adds a new knowledge to the player. It is already idempotent."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM jogador WHERE id_canonico = ?", (jogador_id_canonico,))
                player_res = cursor.fetchone()
                if not player_res: return False
                player_db_id = player_res['id']
                
                # Use INSERT OR IGNORE for knowledge idempotence
                cursor.execute("INSERT OR IGNORE INTO jogador_conhecimentos (jogador_id, categoria, nome, nivel, descricao) VALUES (?, ?, ?, ?, ?)",
                               (player_db_id, categoria, nome, nivel, descricao))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Knowledge '{nome}' added for '{jogador_id_canonico}'.")
                    return True
                else:
                    print(f"INFO: Knowledge '{nome}' for '{jogador_id_canonico}' already exists (ignored).")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding knowledge for '{jogador_id_canonico}': {e}")
            return False

    def add_player_possession(self, jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data=None):
        """Adds a new possession to the player."""
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
                print(f"INFO: Possession '{item_nome}' ({posse_id_canonico}) added for '{jogador_id_canonico}'.")

                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding possession for '{jogador_id_canonico}': {e}")
            return False

    def add_or_get_player_possession(self, jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data=None):
        """
        Checks if a player's possession with the canonical_id already exists. If it exists, returns its details.
        Otherwise, creates the new possession and returns its details (internal ID).
        """
        existing_possession = self.get_entity_details_by_canonical_id('jogador_posses', posse_id_canonico)
        if existing_possession:
            print(f"INFO: Possession '{item_nome}' ({posse_id_canonico}) for '{jogador_id_canonico}' already exists. Using existing one.")
            return existing_possession['id']
        else:
            print(f"INFO: Possession '{item_nome}' ({posse_id_canonico}) for '{jogador_id_canonico}' not found. Creating new possession.")
            return self.add_player_possession(jogador_id_canonico, item_nome, posse_id_canonico, perfil_json_data)


    def add_log_memory(self, jogador_id_canonico, tipo, conteudo, timestamp_evento=None):
        """
        Adds a log or consolidated memory for the player.
        'timestamp_evento' is now the only date/time field (YYYY-MM-DD HH:MM:SS format).
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
                print(f"INFO: Log/Memory ({tipo}) added for '{jogador_id_canonico}'.")
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding log/memory for '{jogador_id_canonico}': {e}")
            return False

    def update_player_location(self, player_canonical_id, new_local_canonical_id):
        """Updates the player's current location in the DB."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM locais WHERE id_canonico = ?", (new_local_canonical_id,))
                local_res = cursor.fetchone()
                if not local_res:
                    print(f"ERROR: Destination location '{new_local_canonical_id}' not found to move the player.")
                    return False
                new_local_id = local_res['id']

                cursor.execute("UPDATE jogador SET local_atual_id = ? WHERE id_canonico = ?", (new_local_id, player_canonical_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"INFO: Player '{player_canonical_id}' moved to '{new_local_canonical_id}'.")
                    return True
                else:
                    print(f"WARNING: Player '{player_canonical_id}' not found for location update.")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR updating player location '{player_canonical_id}': {e}")
            return False

    def add_direct_access_relation(self, origem_id_canonico, destino_id_canonico, tipo_acesso=None, condicoes_acesso=None):
        """
        Adds a direct access relationship between two locations.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                origem_entity = self.get_entity_details_by_canonical_id('locais', origem_id_canonico)
                destino_entity = self.get_entity_details_by_canonical_id('locais', destino_id_canonico)

                if not origem_entity or not destino_entity:
                    print(f"ERROR: Origin ('{origem_id_canonico}') or Destination ('{destino_id_canonico}') not found for access relationship.")
                    return False

                # Use INSERT OR IGNORE to handle existing access relationships.
                query = """
                    INSERT OR IGNORE INTO locais_acessos_diretos (local_origem_id, local_destino_id, tipo_acesso, condicoes_acesso)
                    VALUES (?, ?, ?, ?);
                """
                cursor.execute(query, (origem_entity['id'], destino_entity['id'], tipo_acesso, condicoes_acesso))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"INFO: Direct access relationship between '{origem_id_canonico}' and '{destino_id_canonico}' added.")
                    return True
                else:
                    print(f"WARNING: Direct access relationship between '{origem_id_canonico}' and '{destino_id_canonico}' already exists (ignored).")
                    return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding direct access relationship: {e}")
            return False

    def add_universal_relation(self, origem_id_canonico, origem_tipo_tabela, tipo_relacao, destino_id_canonico, destino_tipo_tabela, propriedades_data=None):
        """
        Adds a universal relationship to the 'relacoes_entidades' table.
        origem_tipo_tabela and destino_tipo_tabela must be the table names (e.g., 'personagens', 'locais').
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
                    print(f"INFO: Universal relationship '{tipo_relacao}' created between '{origem_id_canonico}' ({origem_tipo_tabela}) and '{destino_id_canonico}' ({destino_tipo_tabela}).")
                    return cursor.lastrowid
                else:
                    print(f"WARNING: Universal relationship '{tipo_relacao}' between '{origem_id_canonico}' and '{destino_id_canonico}' already exists (ignored).")
                    return None
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding universal relationship: {e}")
            return None

    def add_column_to_table(self, table_name, column_name, column_type, default_value=None):
        """
        Adds a new column to an existing table.
        Allows the DB schema to be dynamically expanded.
        table_name: Table name.
        column_name: New column name.
        column_type: Data type (TEXT, INTEGER, REAL, BLOB).
        default_value: Optional default value for the new column.
        """
        valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes', 'jogador',
                        'jogador_habilidades', 'jogador_conhecimentos', 'jogador_posses',
                        'jogador_status_fisico_emocional', 'jogador_logs_memoria',
                        'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades', 'tipos_entidades']
        valid_types = ['TEXT', 'INTEGER', 'REAL', 'BLOB']

        if table_name not in valid_tables:
            print(f"ERROR: Table '{table_name}' is not valid for adding column.")
            return False
        if column_type.upper() not in valid_types:
            print(f"ERROR: Invalid column type '{column_type}'. Use one of the following: {', '.join(valid_types)}.")
            return False
        
        # Validate column name to prevent basic SQL Injection
        if not column_name.replace('_', '').isalnum(): 
            print(f"ERROR: Invalid column name '{column_name}'. Use only alphanumeric characters and underscores.")
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if the column already exists
                cursor.execute(f"PRAGMA table_info({table_name});")
                existing_columns = [info['name'] for info in cursor.fetchall()]
                if column_name in existing_columns:
                    print(f"WARNING: Column '{column_name}' already exists in table '{table_name}'.")
                    return True # Considers it a success, as the column is already there

                if default_value is not None:
                    if isinstance(default_value, str):
                        default_sql = f"'{default_value}'"
                    elif isinstance(default_value, (int, float)):
                        default_sql = str(default_value)
                    else:
                        print(f"WARNING: Default value of unsupported type directly for SQL: {type(default_value)}. Inserting NULL.")
                        default_sql = "NULL"
                    query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type.upper()} DEFAULT {default_sql};"
                else:
                    query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type.upper()};"
                
                cursor.execute(query)
                conn.commit()
                print(f"INFO: Column '{column_name}' ({column_type}) added to table '{table_name}'.")
                return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding column '{column_name}' to table '{table_name}': {e}")
            return False

    def add_element_universal(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Adds a new universal element (technology, magic, resource, etc.)."""
        type_info = self._get_type_info('elementos_universais', name_type=tipo_nome)
        if type_info is None:
            return None
        tipo_id_numerico = type_info['id']
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO elementos_universais (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Universal Element '{nome}' ({id_canonico}) added with ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding universal element '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_element_universal(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Checks if a universal element already exists. If it exists, returns its details. Otherwise, creates and returns."""
        existing_entity = self.get_entity_details_by_canonical_id('elementos_universais', id_canonico)
        if existing_entity:
            print(f"INFO: Universal Element '{nome}' ({id_canonico}) already exists. Using existing one.")
            return existing_entity['id']
        else:
            print(f"INFO: Universal Element '{nome}' ({id_canonico}) not found. Creating new element.")
            return self.add_element_universal(id_canonico, nome, tipo_nome, perfil_json_data)

    def add_personagem(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Adds a new character (NPC, monster, etc.)."""
        type_info = self._get_type_info('personagens', name_type=tipo_nome)
        if type_info is None:
            return None
        tipo_id_numerico = type_info['id']
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO personagens (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Character '{nome}' ({id_canonico}) added with ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding character '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_personagem(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Checks if a character already exists. If it exists, returns its details. Otherwise, creates and returns."""
        existing_entity = self.get_entity_details_by_canonical_id('personagens', id_canonico)
        if existing_entity:
            print(f"INFO: Character '{nome}' ({id_canonico}) already exists. Using existing one.")
            return existing_entity['id']
        else:
            print(f"INFO: Character '{nome}' ({id_canonico}) not found. Creating new character.")
            return self.add_personagem(id_canonico, nome, tipo_nome, perfil_json_data)

    def add_faccao(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Adds a new faction (kingdom, corporation, etc.)."""
        type_info = self._get_type_info('faccoes', name_type=tipo_nome)
        if type_info is None:
            return None
        tipo_id_numerico = type_info['id']
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                perfil_json_str = json.dumps(perfil_json_data, ensure_ascii=False) if perfil_json_data else None
                query = "INSERT INTO faccoes (id_canonico, nome, tipo_id, perfil_json) VALUES (?, ?, ?, ?)"
                cursor.execute(query, (id_canonico, nome, tipo_id_numerico, perfil_json_str))
                new_id = cursor.lastrowid
                conn.commit()
                print(f"INFO: Faction '{nome}' ({id_canonico}) added with ID {new_id}.")

                return new_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR adding faction '{nome}' ({id_canonico}): {e}")
            return None

    def add_or_get_faccao(self, id_canonico, nome, tipo_nome, perfil_json_data=None):
        """Checks if a faction already exists. If it exists, returns its details. Otherwise, creates and returns."""
        existing_entity = self.get_entity_details_by_canonical_id('faccoes', id_canonico)
        if existing_entity:
            print(f"INFO: Faction '{nome}' ({id_canonico}) already exists. Using existing one.")
            return existing_entity['id']
        else:
            print(f"INFO: Faction '{nome}' ({id_canonico}) not found. Creating new faction.")
            return self.add_faccao(id_canonico, nome, tipo_nome, perfil_json_data)

    # --- NEW: Function to Add New Entity Type Dynamically ---
    def add_new_entity_type(self, nome_tabela, nome_tipo, display_name=None, parent_tipo_display=None):
        """
        Adds a new type to the 'tipos_entidades' table with validation.
        Allows AI to create new types in a controlled manner, including hierarchy.
        nome_tabela: The table name this type belongs to (e.g., 'locais', 'personagens').
        nome_tipo: The internal, snake_case name of the type (e.g., 'estacao_espacial').
        display_name: The user-friendly name of the type (e.g., 'Estação Espacial'). If None, it will be capitalized nome_tipo.
        parent_tipo_display: The display_name of the parent type, if this is a sub-type.
        Returns True if the type was added or already existed, False in case of validation failure/error.
        """
        # Validation Rules:
        # 1. Basic input validation
        if not nome_tabela or not nome_tipo:
            print("VALIDATION ERROR: 'nome_tabela' and 'nome_tipo' cannot be empty.")
            return False
        
        valid_tables = ['locais', 'elementos_universais', 'personagens', 'faccoes']
        if nome_tabela not in valid_tables:
            print(f"VALIDATION ERROR: 'nome_tabela' '{nome_tabela}' is invalid. Use one of the following: {', '.join(valid_tables)}.")
            return False

        # 2. Normalization and Formatting
        # nome_tipo should be snake_case
        nome_tipo_formatado = entity_types_data.to_snake_case(nome_tipo)
        if not nome_tipo_formatado: # Ensure conversion didn't result in empty string
            print(f"VALIDATION ERROR: Normalized 'nome_tipo' for '{nome_tipo}' is empty.")
            return False

        # display_name: Use provided or capitalize nome_tipo_formatado
        display_name_formatted = display_name.strip() if display_name else nome_tipo_formatado[0].upper() + nome_tipo_formatado[1:].replace('_', ' ')

        parent_tipo_id_numerico = None
        if parent_tipo_display:
            parent_type_info = self._get_type_info(nome_tabela, name_type=parent_tipo_display)
            if parent_type_info:
                parent_tipo_id_numerico = parent_type_info['id']
            else:
                print(f"WARNING: Parent type '{parent_tipo_display}' not found for table '{nome_tabela}'. New type will be added without a parent.")

        # 3. Check if it already exists (idempotence)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check for existence using nome_tabela and nome_tipo (snake_case)
                cursor.execute("SELECT id FROM tipos_entidades WHERE nome_tabela = ? AND nome_tipo = ?", (nome_tabela, nome_tipo_formatado))
                existing_id = cursor.fetchone()
                if existing_id:
                    print(f"WARNING: Type '{display_name_formatted}' (internal: '{nome_tipo_formatado}') for table '{nome_tabela}' already exists (ID: {existing_id['id']}).")
                    return True # Already exists, consider it a success

                # 4. Insert the new type
                cursor.execute("INSERT INTO tipos_entidades (nome_tabela, nome_tipo, display_name, parent_tipo_id) VALUES (?, ?, ?, ?)",
                               (nome_tabela, nome_tipo_formatado, display_name_formatted, parent_tipo_id_numerico))
                conn.commit()
                print(f"INFO: New type '{display_name_formatted}' (internal: '{nome_tipo_formatado}') added for table '{nome_tabela}'.")
                return True
        except sqlite3.IntegrityError as e:
            print(f"ERROR adding type '{display_name_formatted}' for '{nome_tabela}' (violated UNIQUE constraint): {e}")
            conn.rollback()
            return False
        except sqlite3.Error as e:
            print(f"UNEXPECTED ERROR adding type '{display_name_formatted}' for '{nome_tabela}': {e}")
            conn.rollback()
            return False

