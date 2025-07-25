# servidor/data_managers/neo4j_manager.py
from neo4j import GraphDatabase
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Dict, Optional
from config import config

# --- Modelos Pydantic para Validação de Argumentos das Ferramentas ---

class AddOrGetEntityArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo atual.")
    entity_type: str = Field(description="O tipo/label da entidade (ex: 'Local', 'Personagem').")
    id_canonico: str = Field(description="O ID canónico único da entidade.")
    properties: Dict = Field({}, description="Um dicionário de propriedades para o nó.")

class AddRelationshipArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo atual.")
    from_node_id: str = Field(description="ID canónico do nó de origem.")
    to_node_id: str = Field(description="ID canónico do nó de destino.")
    relationship_type: str = Field(description="O tipo da relação (ex: 'ESTA_EM', 'POSSUI').")
    properties: Optional[Dict] = Field({}, description="Um dicionário de propriedades para a relação.")

class Neo4jManager:
    """
    Gere a interação com a base de dados de grafos Neo4j.
    Versão: 5.0.0 - Refatorado para máxima compatibilidade com LangChain, com assinaturas de função explícitas.
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
                # Restrição genérica para todas as entidades
                constraint_name = "constraint_unique_entity_id_session"
                session.run(f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:Entidade) REQUIRE (n.id_canonico, n.session) IS UNIQUE")
                print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")
            except Exception as e:
                print(f"AVISO: Não foi possível criar/verificar as restrições no Neo4j. Erro: {e}")

    @tool(args_schema=AddOrGetEntityArgs)
    def add_or_get_entity(self, session_name: str, entity_type: str, id_canonico: str, properties: dict) -> Dict:
        """Cria ou obtém um nó de entidade (como Local, Personagem) no grafo para uma sessão específica."""
        with self._driver.session() as session:
            # Garante que as propriedades básicas estão presentes
            properties['id_canonico'] = id_canonico
            properties['session'] = session_name
            
            # A query agora usa a etiqueta :Entidade para a restrição e depois adiciona a etiqueta específica
            query = f"""
            MERGE (n:Entidade {{id_canonico: $id_canonico, session: $session_name}})
            ON CREATE SET n += $props, n:{entity_type}
            ON MATCH SET n += $props, n:{entity_type}
            RETURN n
            """
            result = session.run(query, id_canonico=id_canonico, session_name=session_name, props=properties)
            return result.single()[0]

    @tool(args_schema=AddRelationshipArgs)
    def add_relationship(self, session_name: str, from_node_id: str, to_node_id: str, relationship_type: str, properties: Optional[Dict] = None) -> bool:
        """Cria uma relação (aresta) entre duas entidades existentes no grafo para uma sessão específica."""
        with self._driver.session() as session:
            query = f"""
            MATCH (a:Entidade {{id_canonico: $from_id, session: $session_name}}), (b:Entidade {{id_canonico: $to_id, session: $session_name}})
            MERGE (a)-[r:{relationship_type}]->(b)
            ON CREATE SET r = $props
            ON MATCH SET r += $props
            RETURN type(r) as rel_type
            """
            result = session.run(query, from_id=from_node_id, to_id=to_node_id, session_name=session_name, props=properties or {})
            
            # Retorna True se a query foi bem-sucedida e encontrou/criou uma relação
            return result.single() is not None
