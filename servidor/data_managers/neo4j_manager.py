# servidor/data_managers/neo4j_manager.py
from neo4j import GraphDatabase
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from typing import Dict, Any

from config import config

# --- Modelos de Argumentos para as Ferramentas (Pydantic) ---
class AddOrUpdateEntityArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo atual.")
    entity_type: str = Field(description="O tipo de entidade a ser criada, que servirá como label no grafo (ex: 'Local', 'Personagem', 'Item').")
    id_canonico: str = Field(description="O ID canônico único da entidade.")
    properties: Dict[str, Any] = Field({}, description="Um dicionário de propriedades para adicionar ou atualizar no nó da entidade.")

class AddRelationshipArgs(BaseModel):
    session_name: str = Field(description="O nome da sessão de jogo atual.")
    from_node_id: str = Field(description="O ID canônico do nó de origem da relação.")
    to_node_id: str = Field(description="O ID canônico do nó de destino da relação.")
    relationship_type: str = Field(description="O tipo da relação, que se tornará o nome da aresta no grafo (ex: 'ESTA_EM', 'POSSUI', 'INIMIGO_DE').")


class Neo4jManager:
    """
    Gerencia a interação com o banco de dados de grafos Neo4j.
    Versão: 4.0.0 - Refatorado para usar modelos Pydantic para os argumentos das ferramentas.
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
                entity_types = ["Local", "Personagem", "Item", "Faccao", "Jogador"]
                for entity_type in entity_types:
                    constraint_name = f"constraint_unique_{entity_type.lower()}_id_session"
                    if constraint_name not in existing_constraints:
                        query = f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{entity_type}) REQUIRE (n.id_canonico, n.session) IS UNIQUE"
                        session.run(query)
                print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")
            except Exception as e:
                print(f"AVISO: Não foi possível criar/verificar as restrições no Neo4j. Erro: {e}")

    @tool(args_schema=AddOrUpdateEntityArgs)
    def add_or_update_entity(self, **kwargs) -> str:
        """
        Cria ou atualiza um nó de entidade (como Local, Personagem, Item) no grafo para uma sessão específica.
        Use esta função para garantir que uma entidade exista no mundo antes de criar relações com ela.
        """
        args = AddOrUpdateEntityArgs(**kwargs)
        with self._driver.session() as session:
            # Garante que os identificadores chave estão nas propriedades
            props = args.properties.copy()
            props['id_canonico'] = args.id_canonico
            props['session'] = args.session_name
            
            query = f"""
            MERGE (n:{args.entity_type} {{id_canonico: $id_canonico, session: $session_name}})
            ON CREATE SET n += $props
            ON MATCH SET n += $props
            RETURN n.id_canonico AS id
            """
            result = session.run(query, id_canonico=args.id_canonico, session_name=args.session_name, props=props)
            node_id = result.single()['id']
            return f"Nó '{node_id}' do tipo '{args.entity_type}' criado/atualizado com sucesso."

    @tool(args_schema=AddRelationshipArgs)
    def add_relationship(self, **kwargs) -> str:
        """
        Cria uma relação (aresta) entre duas entidades existentes no grafo para uma sessão específica.
        Exemplo de relationship_type: 'ESTA_EM', 'POSSUI', 'INIMIGO_DE'.
        """
        args = AddRelationshipArgs(**kwargs)
        with self._driver.session() as session:
            # Garante que o tipo de relação é seguro para ser usado numa query Cypher
            safe_relationship_type = "".join(c for c in args.relationship_type.upper() if c.isalnum() or c == '_')

            query = f"""
            MATCH (a {{id_canonico: $from_id, session: $session_name}}), (b {{id_canonico: $to_id, session: $session_name}})
            MERGE (a)-[r:{safe_relationship_type}]->(b)
            RETURN type(r) AS rel_type
            """
            result = session.run(query, from_id=args.from_node_id, to_id=args.to_node_id, session_name=args.session_name)
            rel_type = result.single()['rel_type']
            return f"Relação '{rel_type}' criada de '{args.from_node_id}' para '{args.to_node_id}'."
