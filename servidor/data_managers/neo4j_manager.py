import os
import sys
import json # Necessary for perfil_json
from neo4j import GraphDatabase, basic_auth


# NEW: Import global configurations
from config import config

class Neo4jManager:
    """
    API dedicated to interacting with Pillar C (Graph Database - Neo4j).
    Provides methods to query relationships, paths, and the state of the universe in the graph.
    Version: 1.6.3 - Fixed ConstraintError by merging only on unique property and then setting labels.
                   The 'tipo' of entities is now a direct string used for node properties and labels.
    """
    def __init__(self):
        """Initializes the manager and the connection to Neo4j."""
        try:
            # Uses configurations from config.py
            self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=basic_auth(config.NEO4J_USER, config.NEO4J_PASSWORD))
            self.driver.verify_connectivity()
            print("INFO: Neo4jManager connected successfully to Pillar C.")
            
            # Create universal constraints on initialization to ensure uniqueness and optimization
            with self.driver.session() as session:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Local) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Jogador) REQUIRE n.id_canonico IS UNIQUE")
                # Add other UNIQUE constraints for other labels if necessary
            print("INFO: Neo4j uniqueness constraints verified/created.")

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j. Check if the service is running. Error: {e}")

    def close(self):
        """Closes the connection to Neo4j."""
        if self.driver:
            self.driver.close()
            print("INFO: Connection to Neo4j closed.")

    # --- Read Methods (Graph Query) ---

    def get_full_path_to_local(self, local_id_canonico):
        """
        Gets the full hierarchical path of a location using the graph.
        Returns a list of location names, from most specific to most general.
        Ex: ['Central Alpha Laboratory', 'Alpha Base Station', 'Orion Spiral Edge', 'Orion Arm']
        """
        query = """
            MATCH (start:Local {id_canonico: $id})
            MATCH path = (root:Local)-[:DENTRO_DE*]->(start)
            WHERE NOT EXISTS((:Local)-[:DENTRO_DE]->(root)) // Ensures 'root' is a root node
            RETURN [node IN nodes(path) | node.nome] AS names
        """
        with self.driver.session() as session:
            result = session.run(query, id=local_id_canonico).single()
            return result['names'] if result and result['names'] else []


    def get_player_location_details(self, player_id_canonico=config.DEFAULT_PLAYER_ID_CANONICO): # Uses config.DEFAULT_PLAYER_ID_CANONICO
        """
        Gets details of the player's current location, including the location itself,
        its "children" (hierarchically contained locations), and "direct accesses" (navigable neighbors).
        Uses .nome_tipo for the location type (which now directly stores the 'tipo' string).
        """
        query = """
            MATCH (p:Jogador {id_canonico: $id_jogador})-[:ESTA_EM]->(local_atual:Local)
            OPTIONAL MATCH (local_atual)<-[:DENTRO_DE]-(filho:Local) // Hierarchically contained locations
            OPTIONAL MATCH (local_atual)-[da:DA_ACESSO_A]->(acesso_direto:Local) // Explicit access relationship
            WHERE local_atual <> acesso_direto // Avoids self-reference
            
            RETURN
                local_atual { .id_canonico, .nome, .nome_tipo } AS local, 
                COLLECT(DISTINCT filho { .id_canonico, .nome, .nome_tipo }) AS filhos, 
                COLLECT(DISTINCT acessos_diretos { .id_canonico, .nome, .nome_tipo, 'tipo_acesso': da.tipo_acesso, 'condicoes_acesso': da.condicoes_acesso }) AS acessos_diretos 
        """
        with self.driver.session() as session:
            result = session.run(query, id_jogador=player_id_canonico).single()
            if result:
                return {
                    'local': result['local'],
                    'filhos': result['filhos'],
                    'acessos_diretos': result['acessos_diretos']
                }
            return None

    # --- Write Methods (Incremental Graph Update) ---

    def add_or_update_node(self, id_canonico, label_base, properties, main_label=None):
        """
        Adds or updates a generic node in Neo4j.
        id_canonico: Unique canonical ID of the entity.
        label_base: Base label of the entity type (e.g., 'Local', 'Personagem', 'ElementoUniversal').
        properties: Dictionary of properties for the node (includes 'nome', 'nome_tipo' etc.).
        main_label: Specific label (e.g., 'SpaceStation'), if different from label_base.
                    This will be derived from the 'tipo' string of the SQLite entity.
        """
        # Sanitize label_base for Cypher (remove spaces, etc.)
        cleaned_label_base = label_base.replace(" ", "").replace("-", "_") if ' ' in label_base or '-' in label_base else label_base
            
        # Collect all labels to be applied to the node, starting with the mandatory 'Entidade'
        all_labels_cypher = ":Entidade" 
        
        if cleaned_label_base:
            all_labels_cypher += f":`{cleaned_label_base}`"

        if main_label:
            # Sanitize main_label for Cypher labels (remove spaces, special characters)
            cleaned_main_label = main_label.replace(" ", "").replace("-", "_") 
            # Only add main_label if it's not empty and distinct from the base label
            if cleaned_main_label and cleaned_main_label != cleaned_label_base: 
                all_labels_cypher += f":`{cleaned_main_label}`"

        # The MERGE clause should only use the unique constraint part
        # Then, ensure all desired labels are present using SET
        query = f"""
            MERGE (n:Entidade {{id_canonico: $id_canonico}})
            SET n += $props
            SET n{all_labels_cypher} // Add all collected labels. This is idempotent.
            RETURN n.id_canonico
        """

        with self.driver.session() as session:
            try:
                result = session.run(query, id_canonico=id_canonico, props=properties).single()
                return result['n.id_canonico'] if result else None
            except Exception as e:
                print(f"ERROR in add_or_update_node for id_canonico '{id_canonico}': {e}")
                raise # Re-raise to let main.py handle it.

    def add_or_update_player_location_relation(self, player_id_canonico, local_id_canonico):
        """
        Creates or updates the :ESTA_EM relationship from the player to a location.
        Removes old :ESTA_EM relationships to ensure the player is in only one location.
        """
        query = """
            MATCH (p:Jogador {id_canonico: $player_id})
            OPTIONAL MATCH (p)-[old_rel:ESTA_EM]->()
            DELETE old_rel
            WITH p
            MATCH (l:Local {id_canonico: $local_id})
            MERGE (p)-[:ESTA_EM]->(l)
            RETURN p.id_canonico
        """
        with self.driver.session() as session:
            result = session.run(query, player_id=player_id_canonico, local_id=local_id_canonico).single()
            return result['p.id_canonico'] if result else None

    def add_or_update_parent_child_relation(self, child_id_canonico, parent_id_canonico):
        """
        Creates or updates a hierarchical :DENTRO_DE relationship between locations.
        """
        query = """
            MATCH (child:Local {id_canonico: $child_id})
            MATCH (parent:Local {id_canonico: $parent_id})
            MERGE (child)-[:DENTRO_DE]->(parent)
            RETURN child.id_canonico
        """
        with self.driver.session() as session:
            result = session.run(query, child_id=child_id_canonico, parent_id=parent_id_canonico).single()
            return result['child.id_canonico'] if result else None

    def add_or_update_direct_access_relation(self, origem_id_canonico, destino_id_canonico, tipo_acesso=None, condicoes_acesso=None):
        """
        Creates or updates a direct access :DA_ACESSO_A relationship between locations.
        """
        query = """
            MATCH (origem:Local {id_canonico: $origem_id})
            MATCH (destino:Local {id_canonico: $destino_id})
            MERGE (origem)-[r:DA_ACESSO_A]->(destino)
            SET r.tipo_acesso = $tipo_acesso, r.condicoes_acesso = $condicoes_acesso
            RETURN origem.id_canonico
        """
        with self.driver.session() as session:
            result = session.run(query, origem_id=origem_id_canonico, destino_id=destino_id_canonico,
                                 tipo_acesso=tipo_acesso, condicoes_acesso=condicoes_acesso).single()
            return result['origem.id_canonico'] if result else None
            
    def add_or_update_universal_relation(self, origem_id_canonico, origem_label, tipo_relacao, destino_id_canonico, destino_label, propriedades_data=None):
        """
        Creates or updates a dynamic universal relationship between any two entities.
        origem_label and destino_label should be the labels of the Neo4j nodes (e.g., 'Personagem', 'Local').
        """
        # Clean labels to ensure Cypher compatibility (remove spaces, etc.)
        cleaned_origem_label = origem_label.replace(" ", "").replace("-", "_")
        cleaned_destino_label = destino_label.replace(" ", "").replace("-", "_")
        cleaned_tipo_relacao = tipo_relacao.replace(" ", "_").upper() # Relationships usually in UPPER_SNAKE_CASE

        query = f"""
            MATCH (origem:`{cleaned_origem_label}` {{id_canonico: $origem_id}})
            MATCH (destino:`{cleaned_destino_label}` {{id_canonico: $destino_id}})
            MERGE (origem)-[r:`{cleaned_tipo_relacao}`]->(destino)
            SET r += $props
            RETURN origem.id_canonico
        """
        with self.driver.session() as session:
            props = propriedades_data if propriedades_data is not None else {}
            result = session.run(query, origem_id=origem_id_canonico, destino_id=destino_id_canonico, props=props).single()
            return result['origem.id_canonico'] if result else None

    async def build_graph_from_data(self, all_sqlite_data): # Receives all_sqlite_data
        """
        Builds/updates the graph in Neo4j from a dictionary containing all SQLite data.
        This function is the heart of the Pillar C construction process.
        NOW USES INCREMENTAL METHODS AND DOES NOT DELETE THE ENTIRE GRAPH ON BATCH RECONSTRUCTION.
        Updated to use the direct 'tipo' string from SQLite entities for node properties and labels.
        """
        print("\n--- Building Pillar C (Neo4j) from provided data (Pillar B) ---")

        with self.driver.session() as session:
            # REMOVED: session.run("MATCH (n) DETACH DELETE n")
            # Full graph deletion would now only be done if explicitly necessary (e.g., dev reset)
            print("INFO: The Neo4j graph will not be completely cleared, only updated.")
            
            # 1. No longer need to get type_info_map from tipos_entidades.
            # Entity types will be read directly from the 'tipo' column of each entity table.

            # Mapping of SQLite tables to Neo4j base node labels
            entidades_tables_map = {
                "locais": "Local",
                "elementos_universais": "ElementoUniversal",
                "personagens": "Personagem",
                "faccoes": "Faccao",
                "jogador": "Jogador" # Player is a specific type of Personagem, but will have its own label
            }

            # 2. Create or update nodes for all universal entities from the provided data
            for tabela_sqlite, label_base_neo4j in entidades_tables_map.items():
                data_for_table = all_sqlite_data.get(tabela_sqlite, [])
                if not data_for_table:
                    print(f"WARNING: No data for table '{tabela_sqlite}'. Skipping node creation.")
                    continue

                print(f"Creating/Updating nodes for table '{tabela_sqlite}' ({len(data_for_table)} records)...")
                
                for row_dict in data_for_table:
                    node_props = {
                        'id_canonico': row_dict['id_canonico'],
                        'nome': row_dict['nome']
                    }
                    
                    # 'tipo' is now directly available as a string in the row_dict
                    entity_type_string = row_dict.get('tipo') 
                    
                    # 'nome_tipo' property will store the direct type string (e.g., 'Space Station')
                    # 'main_label_neo4j' will be derived from this for Cypher label (e.g., 'SpaceStation')
                    node_props['nome_tipo'] = entity_type_string if entity_type_string else label_base_neo4j

                    main_label_neo4j = None
                    if entity_type_string:
                        # Clean the type string for use as a Cypher label (remove spaces, special chars)
                        main_label_neo44j = entity_type_string.replace(" ", "").replace("-", "_") 
                    
                    if 'perfil_json' in row_dict and row_dict['perfil_json']:
                        try:
                            json_data = json.loads(row_dict['perfil_json'])
                            node_props.update(json_data)
                        except json.JSONDecodeError:
                            node_props['perfil_json_raw'] = row_dict['perfil_json']
                    
                    # Call the incremental method
                    self.add_or_update_node(
                        id_canonico=node_props['id_canonico'],
                        label_base=label_base_neo4j,
                        properties=node_props,
                        main_label=main_label_neo4j # Pass the specific label (cleaned type string)
                    )
            
            # --- CREATE RELATIONSHIPS ---

            # Create Hierarchical Relationships (:DENTRO_DE) for Locations
            print("\n--- Starting creation of hierarchical relationships [:DENTRO_DE] for locations ---")
            locais_data = all_sqlite_data.get('locais', [])
            locais_id_map = {loc['id']: loc['id_canonico'] for loc in locais_data} # Maps numeric ID to canonical ID
            
            for local in locais_data:
                if local.get('parent_id') is not None:
                    filho_id_canonico = local['id_canonico']
                    pai_id_canonico = locais_id_map.get(local['parent_id'])
                    
                    if filho_id_canonico and pai_id_canonico:
                        self.add_or_update_parent_child_relation(filho_id_canonico, pai_id_canonico)
            
            # SECTION: CREATE DIRECT ACCESS RELATIONSHIPS (:DA_ACESSO_A)
            print("\n--- Starting creation of direct access relationships [:DA_ACESSO_A] ---")
            acessos_diretos_data = all_sqlite_data.get('locais_acessos_diretos', [])
            
            if acessos_diretos_data:
                for row in acessos_diretos_data:
                    origem_db_id = row['local_origem_id']
                    destino_db_id = row['local_destino_id']
                    tipo_acesso = row.get('tipo_acesso')
                    condicoes_acesso = row.get('condicoes_acesso')

                    origem_id_canonico = locais_id_map.get(origem_db_id)
                    destino_id_canonico = locais_id_map.get(destino_db_id)
            
                    if origem_id_canonico and destino_id_canonico:
                        self.add_or_update_direct_access_relation(origem_id_canonico, destino_id_canonico, tipo_acesso, condicoes_acesso)

            # SECTION: CREATE UNIVERSAL RELATIONSHIPS (:UNIVERSAL_RELATIONSHIP_TYPE)
            print("\n--- Starting creation of dynamic universal relationships ---")
            universal_relations_data = all_sqlite_data.get('relacoes_entidades', [])

            if universal_relations_data:
                for row in universal_relations_data:
                    origem_id = row['entidade_origem_id']
                    origem_tipo_tabela = row['entidade_origem_tipo']
                    tipo_relacao = row['tipo_relacao']
                    destino_id = row['entidade_destino_id']
                    destino_tipo_tabela = row['entidade_destino_tipo']
                    propriedades_json = row['propriedades_json']

                    # Convert SQLite table name to Neo4j label (capitalized, cleaned)
                    # Note: These are now the base labels for the table (e.g., 'Personagens' -> 'Personagem')
                    origem_label_neo4j = entidades_tables_map.get(origem_tipo_tabela, origem_tipo_tabela.capitalize())
                    destino_label_neo4j = entidades_tables_map.get(destino_tipo_tabela, destino_tipo_tabela.capitalize())

                    props = {}
                    if propriedades_json:
                        try:
                            props = json.loads(propriedades_json)
                        except json.JSONDecodeError:
                            print(f"WARNING: Could not parse JSON properties for relationship {tipo_relacao} (between {origem_id} and {destino_id}).")
                            props['propriedades_json_raw'] = propriedades_json

                    self.add_or_update_universal_relation(origem_id, origem_label_neo4j, tipo_relacao, destino_id, destino_label_neo4j, props)

            # Create Player Location Relationship (:ESTA_EM)
            print("\n--- Starting creation of player location relationship [:ESTA_EM] ---")
            jogador_data = all_sqlite_data.get('jogador', [])
            if jogador_data:
                jogador_info = jogador_data[0] 
                jogador_id_canonico = jogador_info['id_canonico']

                local_atual_id_numerico = jogador_info['local_atual_id']
                locais_data_map_by_id = {loc['id']: loc['id_canonico'] for loc in all_sqlite_data.get('locais', [])}
                local_atual_id_canonico = locais_data_map_by_id.get(local_atual_id_numerico)

                if jogador_id_canonico and local_atual_id_canonico:
                    self.add_or_update_player_location_relation(jogador_id_canonico, local_atual_id_canonico)
                else:
                    print("WARNING: Insufficient data to create :ESTA_EM relationship (player or current location not found).")
            else:
                print("DEBUG: No player location relationship found in the provided data for 'jogador'.")

        print("\nSUCESSO: Graph database (Neo4j) populated/updated.")
