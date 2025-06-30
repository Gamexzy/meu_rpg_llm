import os
import sys
import json
from neo4j import GraphDatabase, basic_auth

from config import config

class Neo4jManager:
    """
    API dedicada para interagir com o Pilar C (Graph Database - Neo4j).
    Versão: 1.8.0 - Removido o ID padrão de get_player_location_details para maior flexibilidade.
    """
    def __init__(self):
        """Inicializa o gestor e a conexão com o Neo4j."""
        try:
            self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=basic_auth(config.NEO4J_USER, config.NEO4J_PASSWORD))
            self.driver.verify_connectivity()
            print("INFO: Neo4jManager conectado com sucesso ao Pilar C.")
            
            with self.driver.session() as session:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Local) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Jogador) REQUIRE n.id_canonico IS UNIQUE")
            print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")

        except Exception as e:
            raise ConnectionError(f"Falha ao conectar ao Neo4j. Verifique se o serviço está em execução. Erro: {e}")

    def close(self):
        """Fecha a conexão com o Neo4j."""
        if self.driver:
            self.driver.close()
            print("INFO: Conexão com o Neo4j fechada.")

    def get_player_location_details(self, player_id_canonico):
        """
        Obtém detalhes da localização atual de um jogador específico.
        """
        query = """
            MATCH (p:Jogador {id_canonico: $id_jogador})-[:ESTA_EM]->(local_atual:Local)
            OPTIONAL MATCH (local_atual)<-[:DENTRO_DE]-(filho:Local)
            OPTIONAL MATCH (local_atual)-[da:DA_ACESSO_A]->(acesso_direto:Local)
            WHERE local_atual <> acesso_direto
            
            RETURN
                local_atual { .id_canonico, .nome, .nome_tipo } AS local, 
                COLLECT(DISTINCT filho { .id_canonico, .nome, .nome_tipo }) AS filhos, 
                COLLECT(DISTINCT acessos_diretos { .id_canonico, .nome, .nome_tipo, tipo_acesso: da.tipo_acesso, condicoes_acesso: da.condicoes_acesso }) AS acessos_diretos
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

    # ... (O resto das funções do Neo4jManager permanecem as mesmas) ...

    def get_full_path_to_local(self, local_id_canonico):
        query = """
            MATCH (start:Local {id_canonico: $id})
            MATCH path = (root:Local)-[:DENTRO_DE*]->(start)
            WHERE NOT EXISTS((:Local)-[:DENTRO_DE]->(root))
            RETURN [node IN nodes(path) | node.nome] AS names
        """
        with self.driver.session() as session:
            result = session.run(query, id=local_id_canonico).single()
            return result['names'] if result and result['names'] else []

    def add_or_update_node(self, id_canonico, label_base, properties, main_label=None):
        cleaned_label_base = label_base.replace(" ", "").replace("-", "_")
        all_labels_cypher = f":Entidade:`{cleaned_label_base}`"
        if main_label:
            cleaned_main_label = main_label.replace(" ", "").replace("-", "_")
            if cleaned_main_label and cleaned_main_label != cleaned_label_base:
                all_labels_cypher += f":`{cleaned_main_label}`"
        query = f"""
            MERGE (n:Entidade {{id_canonico: $id_canonico}})
            SET n += $props
            SET n{all_labels_cypher}
            RETURN n.id_canonico
        """
        with self.driver.session() as session:
            return session.run(query, id_canonico=id_canonico, props=properties).single()

    def add_or_update_player_location_relation(self, player_id_canonico, local_id_canonico):
        query = """
            MATCH (p:Jogador {id_canonico: $player_id})
            OPTIONAL MATCH (p)-[old_rel:ESTA_EM]->()
            DELETE old_rel
            WITH p
            MATCH (l:Local {id_canonico: $local_id})
            MERGE (p)-[:ESTA_EM]->(l)
        """
        with self.driver.session() as session:
            session.run(query, player_id=player_id_canonico, local_id=local_id_canonico)

    def add_or_update_parent_child_relation(self, child_id_canonico, parent_id_canonico):
        query = """
            MATCH (child:Local {id_canonico: $child_id})
            MATCH (parent:Local {id_canonico: $parent_id})
            MERGE (child)-[:DENTRO_DE]->(parent)
        """
        with self.driver.session() as session:
            session.run(query, child_id=child_id_canonico, parent_id=parent_id_canonico)

    def add_or_update_direct_access_relation(self, origem_id_canonico, destino_id_canonico, tipo_acesso=None, condicoes_acesso=None):
        query = """
            MATCH (origem:Local {id_canonico: $origem_id})
            MATCH (destino:Local {id_canonico: $destino_id})
            MERGE (origem)-[r:DA_ACESSO_A]->(destino)
            SET r.tipo_acesso = $tipo_acesso, r.condicoes_acesso = $condicoes_acesso
        """
        with self.driver.session() as session:
            session.run(query, origem_id=origem_id_canonico, destino_id=destino_id_canonico,
                        tipo_acesso=tipo_acesso, condicoes_acesso=condicoes_acesso)

    def add_or_update_universal_relation(self, origem_id_canonico, origem_label, tipo_relacao, destino_id_canonico, destino_label, propriedades_data=None):
        cleaned_origem_label = origem_label.replace(" ", "").replace("-", "_")
        cleaned_destino_label = destino_label.replace(" ", "").replace("-", "_")
        cleaned_tipo_relacao = tipo_relacao.replace(" ", "_").upper()
        query = f"""
            MATCH (origem:`{cleaned_origem_label}` {{id_canonico: $origem_id}})
            MATCH (destino:`{cleaned_destino_label}` {{id_canonico: $destino_id}})
            MERGE (origem)-[r:`{cleaned_tipo_relacao}`]->(destino)
            SET r += $props
        """
        with self.driver.session() as session:
            props = propriedades_data if propriedades_data is not None else {}
            session.run(query, origem_id=origem_id_canonico, destino_id=destino_id_canonico, props=props)

    async def build_graph_from_data(self, all_sqlite_data):
        print("\n--- Construindo Pilar C (Neo4j) a partir dos dados fornecidos (Pilar B) ---")
        entidades_tables_map = {"locais": "Local", "elementos_universais": "ElementoUniversal", "personagens": "Personagem", "faccoes": "Faccao", "jogador": "Jogador"}
        for tabela_sqlite, label_base_neo4j in entidades_tables_map.items():
            for row_dict in all_sqlite_data.get(tabela_sqlite, []):
                node_props = {k: v for k, v in row_dict.items() if isinstance(v, (str, int, float, bool))}
                self.add_or_update_node(row_dict['id_canonico'], label_base_neo4j, node_props, row_dict.get('tipo'))
        
        locais_id_map = {loc['id']: loc['id_canonico'] for loc in all_sqlite_data.get('locais', [])}
        for local in all_sqlite_data.get('locais', []):
            if local.get('parent_id'):
                self.add_or_update_parent_child_relation(local['id_canonico'], locais_id_map.get(local['parent_id']))
        
        for row in all_sqlite_data.get('locais_acessos_diretos', []):
            self.add_or_update_direct_access_relation(locais_id_map.get(row['local_origem_id']), locais_id_map.get(row['local_destino_id']), row.get('tipo_acesso'), row.get('condicoes_acesso'))

        for row in all_sqlite_data.get('relacoes_entidades', []):
            self.add_or_update_universal_relation(row['entidade_origem_id'], entidades_tables_map.get(row['entidade_origem_tipo']), row['tipo_relacao'], row['entidade_destino_id'], entidades_tables_map.get(row['entidade_destino_tipo']), json.loads(row['propriedades_json'] or '{}'))

        if all_sqlite_data.get('jogador'):
            jogador_info = all_sqlite_data['jogador'][0]
            self.add_or_update_player_location_relation(jogador_info['id_canonico'], locais_id_map.get(jogador_info['local_atual_id']))
        print("\nSUCESSO: Base de dados de grafo (Neo4j) populada/atualizada.")
