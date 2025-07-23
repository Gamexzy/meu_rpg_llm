from neo4j import GraphDatabase
from langchain.tools import tool
from config import config

class Neo4jManager:
    """
    Gerencia a interação com o banco de dados de grafos Neo4j.
    Versão: 3.1.0 - Adicionadas anotações @tool para exposição ao LLM.
    """
    def __init__(self):
        self._driver = None
        try:
            self._driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
            print("INFO: Neo4jManager conectado com sucesso ao Pilar C.")
            self._create_constraints()
        except Exception as e:
            print(f"ERRO CRÍTICO: Falha ao conectar ou verificar o Neo4j. Erro: {e}")
            raise

    def close(self):
        if self._driver is not None:
            self._driver.close()

    def _create_constraints(self):
        """Garante que as restrições de unicidade compostas existam."""
        with self._driver.session() as session:
            try:
                existing_constraints = {c['name'] for c in session.run("SHOW CONSTRAINTS").data()}
                entity_types = ["Local", "Personagem", "Item", "Faccao"] 
                for entity_type in entity_types:
                    constraint_name = f"constraint_unique_{entity_type.lower()}_id_session"
                    if constraint_name not in existing_constraints:
                        query = f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{entity_type}) REQUIRE (n.id_canonico, n.session) IS UNIQUE"
                        session.run(query)
                print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")
            except Exception as e:
                print(f"AVISO: Não foi possível criar/verificar as restrições no Neo4j. Erro: {e}")

    @tool
    def add_or_get_entity(self, session_name: str, entity_type: str, id_canonico: str, properties: dict):
        """
        Cria ou obtém um nó de entidade (como Local, Personagem, Item) no grafo para uma sessão específica.
        Use esta função para garantir que uma entidade exista no mundo antes de criar relações com ela.
        """
        with self._driver.session() as session:
            properties['id_canonico'] = id_canonico
            properties['session'] = session_name
            query = f"""
            MERGE (n:{entity_type} {{id_canonico: $id_canonico, session: $session_name}})
            ON CREATE SET n += $props
            ON MATCH SET n += $props
            RETURN n
            """
            result = session.run(query, id_canonico=id_canonico, session_name=session_name, props=properties)
            return result.single()[0]

    @tool
    def add_relationship(self, session_name: str, from_node_id: str, to_node_id: str, relationship_type: str):
        """
        Cria uma relação (aresta) entre duas entidades existentes no grafo para uma sessão específica.
        Exemplo de relationship_type: 'ESTA_EM', 'POSSUI', 'INIMIGO_DE'.
        """
        with self._driver.session() as session:
            query = f"""
            MATCH (a {{id_canonico: $from_id, session: $session_name}}), (b {{id_canonico: $to_id, session: $session_name}})
            MERGE (a)-[r:{relationship_type}]->(b)
            RETURN type(r)
            """
            result = session.run(query, from_id=from_node_id, to_id=to_node_id, session_name=session_name)
            return result.single() is not None
