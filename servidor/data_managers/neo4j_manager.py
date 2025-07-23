import os
import sys
import json
from neo4j import GraphDatabase, basic_auth

# Adiciona o diretório raiz ao sys.path para importação da configuração
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
from config import config

class Neo4jManager:
    """
    Gerencia a interação com o banco de dados de grafos Neo4j.
    Versão: 4.0.0 - Unificado para operar com dados isolados por sessão usando uma propriedade 'session'.
                  Combina a construção de grafos com a gestão por sessão.
    """
    def __init__(self):
        """Inicializa o gestor e a conexão com o Neo4j."""
        self._driver = None
        try:
            self._driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=basic_auth(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
            print("INFO: Neo4jManager conectado com sucesso ao Pilar C (Neo4j).")
            self._create_constraints()
        except Exception as e:
            print(f"ERRO CRÍTICO: Falha ao conectar ou verificar o Neo4j. Verifique as credenciais e o status do servidor. Erro: {e}")
            raise

    def close(self):
        """Fecha a conexão com o Neo4j."""
        if self._driver is not None:
            self._driver.close()
            print("INFO: Conexão com Neo4j fechada.")

    def _create_constraints(self):
        """
        Garante que as restrições de unicidade compostas (id_canonico, session) existam.
        Isso é crucial para o isolamento dos dados de cada sessão.
        """
        with self._driver.session() as session:
            # Labels que representam entidades únicas por sessão
            entity_labels = ["Entidade", "Local", "Jogador", "Personagem", "Faccao", "ElementoUniversal", "Item"]
            for label in entity_labels:
                constraint_name = f"constraint_unique_{label.lower()}_id_session"
                query = f"""
                CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                FOR (n:{label})
                REQUIRE (n.id_canonico, n.session) IS UNIQUE
                """
                session.run(query)
        print("INFO: Restrições de unicidade por sessão do Neo4j verificadas/criadas.")

    def _execute_write(self, query, **params):
        """Executa uma transação de escrita no banco de dados."""
        with self._driver.session() as session:
            return session.write_transaction(lambda tx: tx.run(query, **params).single())

    def _execute_read(self, query, **params):
        """Executa uma transação de leitura no banco de dados."""
        with self._driver.session() as session:
            return session.read_transaction(lambda tx: tx.run(query, **params).data())

    # --- Métodos de Construção e Atualização do Grafo (por sessão) ---

    def add_or_update_node(self, session_name: str, id_canonico: str, labels: list, properties: dict):
        """Cria ou atualiza um nó, garantindo que a propriedade 'session' esteja definida."""
        properties['id_canonico'] = id_canonico
        properties['session'] = session_name
        
        # Constrói a parte dos labels da query
        labels_cypher = ":".join(labels)
        
        query = f"""
        MERGE (n:{labels_cypher} {{id_canonico: $id_canonico, session: $session_name}})
        SET n += $props
        RETURN n.id_canonico
        """
        self._execute_write(query, id_canonico=id_canonico, session_name=session_name, props=properties)

    def add_relationship(self, session_name: str, from_id: str, from_label: str, rel_type: str, to_id: str, to_label: str, props: dict = {}):
        """Cria ou atualiza uma relação entre dois nós DENTRO da mesma sessão."""
        query = f"""
        MATCH (a:{from_label} {{id_canonico: $from_id, session: $session_name}})
        MATCH (b:{to_label} {{id_canonico: $to_id, session: $session_name}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        """
        self._execute_write(query, from_id=from_id, to_id=to_id, session_name=session_name, props=props)

    def build_graph_from_data(self, all_sqlite_data: dict, session_name: str):
        """Constrói o grafo para uma sessão específica a partir dos dados do SQLite."""
        print(f"\n--- Construindo grafo (Neo4j) para a sessão '{session_name}' ---")
        
        entidades_map = {
            "locais": "Local",
            "elementos_universais": "ElementoUniversal",
            "personagens": "Personagem",
            "faccoes": "Faccao",
            "jogador": "Jogador"
        }

        # 1. Criar todos os nós
        for table, base_label in entidades_map.items():
            for row in all_sqlite_data.get(table, []):
                props = {k: v for k, v in row.items() if isinstance(v, (str, int, float, bool))}
                labels = ["Entidade", base_label]
                if row.get('tipo'):
                    labels.append(row['tipo'].replace(" ", "_"))
                self.add_or_update_node(session_name, row['id_canonico'], labels, props)

        # Mapeamento de ID numérico do SQLite para ID canônico
        locais_id_map = {loc['id']: loc['id_canonico'] for loc in all_sqlite_data.get('locais', [])}
        
        # 2. Criar Relações de Hierarquia (DENTRO_DE)
        for local in all_sqlite_data.get('locais', []):
            if local.get('parent_id') and local['parent_id'] in locais_id_map:
                parent_id_canonico = locais_id_map[local['parent_id']]
                self.add_relationship(session_name, local['id_canonico'], "Local", "DENTRO_DE", parent_id_canonico, "Local")

        # 3. Criar Relações de Acesso Direto (DA_ACESSO_A)
        for row in all_sqlite_data.get('locais_acessos_diretos', []):
            if row['local_origem_id'] in locais_id_map and row['local_destino_id'] in locais_id_map:
                origem_id = locais_id_map[row['local_origem_id']]
                destino_id = locais_id_map[row['local_destino_id']]
                props = {'tipo_acesso': row.get('tipo_acesso'), 'condicoes': row.get('condicoes_acesso')}
                self.add_relationship(session_name, origem_id, "Local", "DA_ACESSO_A", destino_id, "Local", props)

        # 4. Criar Relações Universais
        for row in all_sqlite_data.get('relacoes_entidades', []):
            props = json.loads(row['propriedades_json'] or '{}')
            rel_type = row['tipo_relacao'].upper().replace(" ", "_")
            self.add_relationship(
                session_name,
                row['entidade_origem_id'], entidades_map[row['entidade_origem_tipo']],
                rel_type,
                row['entidade_destino_id'], entidades_map[row['entidade_destino_tipo']],
                props
            )
        
        # 5. Criar Relação de Localização do Jogador (ESTA_EM)
        if all_sqlite_data.get('jogador'):
            player_info = all_sqlite_data['jogador'][0]
            if player_info.get('local_atual_id') in locais_id_map:
                local_id_canonico = locais_id_map[player_info['local_atual_id']]
                # Remove relação antiga antes de criar a nova
                self._execute_write(
                    "MATCH (p:Jogador {id_canonico: $pid, session: $s})-[r:ESTA_EM]->() DELETE r",
                    pid=player_info['id_canonico'], s=session_name
                )
                self.add_relationship(session_name, player_info['id_canonico'], "Jogador", "ESTA_EM", local_id_canonico, "Local")

        print(f"SUCESSO: Grafo para a sessão '{session_name}' populado/atualizado.")

    # --- Métodos de Consulta do Grafo (por sessão) ---

    def get_player_location_details(self, session_name: str, player_id_canonico: str):
        """Obtém detalhes da localização atual de um jogador específico para uma dada sessão."""
        query = """
            MATCH (p:Jogador {id_canonico: $player_id, session: $session_name})-[:ESTA_EM]->(local_atual:Local)
            OPTIONAL MATCH (local_atual)<-[:DENTRO_DE]-(filho:Local {session: $session_name})
            OPTIONAL MATCH (local_atual)-[da:DA_ACESSO_A]->(acesso_direto:Local {session: $session_name})
            RETURN
                local_atual { .* } AS local,
                COLLECT(DISTINCT filho { .* }) AS filhos,
                COLLECT(DISTINCT da { .*, destino: acesso_direto { .* } }) AS acessos_diretos
        """
        return self._execute_read(query, player_id=player_id_canonico, session_name=session_name)

    def get_full_path_to_local(self, session_name: str, local_id_canonico: str):
        """Retorna o caminho hierárquico completo até um local para uma dada sessão."""
        query = """
            MATCH (start:Local {id_canonico: $local_id, session: $session_name})
            MATCH path = (root:Local)-[:DENTRO_DE*0..]->(start)
            WHERE root.session = $session_name AND NOT EXISTS(()-[:DENTRO_DE]->(root))
            RETURN [node IN nodes(path) | node { .id_canonico, .nome, .tipo }] AS path_nodes
            ORDER BY length(path) DESC
            LIMIT 1
        """
        result = self._execute_read(query, local_id=local_id_canonico, session_name=session_name)
        return result[0]['path_nodes'] if result else []

