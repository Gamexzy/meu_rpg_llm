# servidor/data_managers/neo4j_manager.py
from neo4j import GraphDatabase
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Dict
from config import config
from pydantic import BaseModel, Field
# --- Modelos Pydantic para os Argumentos das Ferramentas ---

class AddOrGetEntityArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo para isolar os dados.")
    entity_type: str = Field(description="O tipo/label da entidade a ser criada (ex: 'Local', 'Personagem', 'Item').")
    id_canonico: str = Field(description="O ID canônico único para a entidade.")
    properties: Dict = Field(description="Um dicionário de propriedades para definir ou atualizar no nó.")

class AddRelationshipArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo onde a relação será criada.")
    from_node_id: str = Field(description="O ID canônico do nó de origem da relação.")
    to_node_id: str = Field(description="O ID canônico do nó de destino da relação.")
    relationship_type: str = Field(description="O tipo da relação a ser criada (ex: 'ESTA_EM', 'POSSUI').")

class Neo4jManager:
    """
    Gerencia a interação com o banco de dados de grafos Neo4j.
    Versão: 3.2.0 - Corrigido o tratamento de retorno da ferramenta add_relationship e melhorada a robustez.
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
                constraint_name = "constraint_unique_entity_session"
                session.run(f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:Entidade) REQUIRE (n.id_canonico, n.session) IS UNIQUE")
                print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")
            except Exception as e:
                print(f"AVISO: Não foi possível criar/verificar as restrições no Neo4j. Erro: {e}")

    @tool(args_schema=AddOrGetEntityArgs)
    def add_or_get_entity(self, **kwargs):
        """
        Cria ou obtém um nó de entidade (como Local, Personagem, Item) no grafo para uma sessão específica.
        Use esta função para garantir que uma entidade exista no mundo antes de criar relações com ela.
        """
        args = AddOrGetEntityArgs(**kwargs)
        with self._driver.session() as session:
            props = args.properties.copy()
            props['id_canonico'] = args.id_canonico
            props['session'] = args.session_name

            query = f"""
            MERGE (n:Entidade {{id_canonico: $id_canonico, session: $session_name}})
            ON CREATE SET n += $props, n:{args.entity_type}
            ON MATCH SET n += $props, n:{args.entity_type}
            RETURN n.id_canonico as id
            """
            result = session.run(query, id_canonico=args.id_canonico, session_name=args.session_name, props=props)
            return f"Entidade '{result.single()['id']}' criada/atualizada no grafo."

    @tool(args_schema=AddRelationshipArgs)
    def add_relationship(self, **kwargs) -> bool:
        """
        Cria uma relação (aresta) entre duas entidades existentes no grafo para uma sessão específica.
        Exemplo de relationship_type: 'ESTA_EM', 'POSSUI', 'INIMIGO_DE'.
        Retorna True se a operação foi bem-sucedida.
        """
        args = AddRelationshipArgs(**kwargs)
        with self._driver.session() as session:
            query = f"""
            MATCH (a:Entidade {{id_canonico: $from_id, session: $session_name}})
            MATCH (b:Entidade {{id_canonico: $to_id, session: $session_name}})
            MERGE (a)-[r:{args.relationship_type}]->(b)
            RETURN r IS NOT NULL as success
            """
            result = session.run(
                query,
                from_id=args.from_node_id,
                to_id=args.to_node_id,
                session_name=args.session_name
            )
            record = result.single()
            return record is not None and record['success']
