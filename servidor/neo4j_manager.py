import os
import sys
import json # Necessário para perfil_json
from neo4j import GraphDatabase, basic_auth

# Adiciona o diretório da raiz do projeto ao sys.path para que o módulo config possa ser importado
# Assumindo que o neo4j_manager.py está em meu_rpg_llm/servidor/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))

# NOVO: Importar as configurações globais
import config as config 

class Neo4jManager:
    """
    API dedicada para interagir com o Pilar C (Base de Dados de Grafo - Neo4j).
    Fornece métodos para consultar relações, caminhos e o estado do universo no grafo.
    Versão: 1.5.0 - Recebe dados para construção, não lê SQLite diretamente. Usa config.py.
    """
    def __init__(self):
        """Inicializa o gestor e a conexão com o Neo4j."""
        try:
            # Usa configurações de config.py
            self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=basic_auth(config.NEO4J_USER, config.NEO4J_PASSWORD))
            self.driver.verify_connectivity()
            print("INFO: Neo4jManager conectado com sucesso ao Pilar C.")
        except Exception as e:
            raise ConnectionError(f"Falha ao conectar ao Neo4j. Verifique se o serviço está a correr. Erro: {e}")

    def close(self):
        """Fecha a conexão com o Neo4j."""
        if self.driver:
            self.driver.close()
            print("INFO: Conexão com o Neo4j fechada.")

    def get_full_path_to_local(self, local_id_canonico):
        """
        Obtém o caminho hierárquico completo de um local usando o grafo.
        Retorna uma lista de nomes de locais, do mais específico ao mais geral.
        Ex: ['Laboratório Central Alfa', 'Estação Base Alfa', 'Margem da Espiral de Órion', 'Braço de Órion']
        """
        query = """
            MATCH (start:Local {id_canonico: $id})
            MATCH path = (root:Local)-[:DENTRO_DE*]->(start)
            WHERE NOT EXISTS((:Local)-[:DENTRO_DE]->(root)) // Garante que 'root' é um nó raiz
            RETURN [node IN nodes(path) | node.nome] AS names
        """
        with self.driver.session() as session:
            result = session.run(query, id=local_id_canonico).single()
            return result['names'] if result and result['names'] else []


    def get_player_location_details(self, player_id_canonico=config.DEFAULT_PLAYER_ID_CANONICO): # Usa config.DEFAULT_PLAYER_ID_CANONICO
        """
        Obtém detalhes da localização atual do jogador, incluindo o próprio local,
        seus "filhos" (locais contidos hierarquicamente), e "acessos diretos" (vizinhos navegáveis).
        Adaptado para usar .nome_tipo para o tipo do local.
        """
        query = """
            MATCH (p:Jogador {id_canonico: $id_jogador})-[:ESTA_EM]->(local_atual:Local)
            OPTIONAL MATCH (local_atual)<-[:DENTRO_DE]-(filho:Local) // Locais contidos hierarquicamente
            OPTIONAL MATCH (local_atual)-[da:DA_ACESSO_A]->(acesso_direto:Local) // Relação de acesso explícita
            WHERE local_atual <> acesso_direto // Evita auto-referência
            
            RETURN
                local_atual { .id_canonico, .nome, .nome_tipo } AS local, // Agora buscando 'nome_tipo'
                COLLECT(DISTINCT filho { .id_canonico, .nome, .nome_tipo }) AS filhos, // Buscando 'nome_tipo'
                COLLECT(DISTINCT acesso_direto { .id_canonico, .nome, .nome_tipo, 'tipo_acesso': da.tipo_acesso, 'condicoes_acesso': da.condicoes_acesso }) AS acessos_diretos // Buscando 'nome_tipo'
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

    def update_player_location_in_graph(self, player_id, new_local_id):
        """
        Move o jogador para um novo local no grafo.
        Remove a relação :ESTA_EM existente e cria uma nova para o new_local_id.
        """
        query = """
        MATCH (p:Jogador {id_canonico: $p_id})
        OPTIONAL MATCH (p)-[r:ESTA_EM]->()
        DELETE r
        WITH p
        MATCH (new_loc:Local {id_canonico: $loc_id})
        CREATE (p)-[:ESTA_EM]->(new_loc)
        """
        with self.driver.session() as session:
            session.run(query, p_id=player_id, loc_id=new_local_id)
            print(f"INFO: Jogador '{player_id}' movido para '{new_local_id}' no grafo.")


    async def build_graph_from_data(self, all_sqlite_data): # NOVO: Recebe all_sqlite_data
        """
        Constrói/atualiza o grafo no Neo4j a partir de um dicionário contendo todos os dados do SQLite.
        Esta função é o coração do processo de construção do Pilar C.
        """
        print("\n--- A construir o Pilar C (Neo4j) a partir dos dados fornecidos (Pilar B) ---")

        # sqlite_conn e cursor removidos, pois não lemos mais diretamente do SQLite aqui.

        with self.driver.session() as session:
            print("Limpando grafo existente e criando restrições...")
            session.run("MATCH (n) DETACH DELETE n")
            # Restrição universal para id_canonico em nós 'Entidade'
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id_canonico IS UNIQUE")

            # 1. Obter mapeamento de tipos_entidades (tipo_id para nome_tipo) dos dados fornecidos
            type_id_to_name_map = {}
            tipos_entidades_data = all_sqlite_data.get('tipos_entidades', [])
            try:
                for row in tipos_entidades_data:
                    type_id_to_name_map[(row['nome_tabela'], row['id'])] = row['nome_tipo']
                print(f"DEBUG: Mapeamento de tipos_entidades carregado: {type_id_to_name_map}")
            except Exception as e:
                print(f"ERRO: Falha ao carregar mapeamento de tipos_entidades dos dados fornecidos: {e}.")
                return # Sai da função se a tabela essencial não existe

            # Mapeamento de tabelas SQLite para rótulos de nós Neo4j base
            entidades_tables_map = {
                "locais": "locais",
                "elementos_universais": "elementos_universais",
                "personagens": "personagens",
                "faccoes": "faccoes",
                "jogador": "jogador"
            }

            # 2. Criar nós para todas as entidades universais a partir dos dados fornecidos
            for tabela_sqlite, table_type_name_in_meta in entidades_tables_map.items():
                data_for_table = all_sqlite_data.get(tabela_sqlite, [])
                if not data_for_table:
                    print(f"AVISO: Nenhuns dados para a tabela '{tabela_sqlite}'. Pulando criação de nós.")
                    continue

                print(f"Criando nós da tabela '{tabela_sqlite}' ({len(data_for_table)} registros)...")
                
                # Obter informações das colunas (para saber se 'tipo_id' e 'perfil_json' existem)
                # Esta lógica é para adaptar a leitura de 'dict(row)' do DataManager
                # E saber quais propriedades esperar.
                
                for row_dict in data_for_table: # row_dict já é um dicionário
                    node_props = {
                        'id_canonico': row_dict['id_canonico'],
                        'nome': row_dict['nome']
                    }
                    
                    main_label = None 
                    
                    if 'tipo_id' in row_dict and row_dict['tipo_id'] is not None:
                        main_label = type_id_to_name_map.get((table_type_name_in_meta, row_dict['tipo_id']))
                        node_props['nome_tipo'] = main_label # Adiciona o nome do tipo como propriedade
                    elif tabela_sqlite == 'jogador': # Caso específico para a tabela jogador
                        main_label = 'Jogador'
                        node_props['nome_tipo'] = 'Jogador'
                    else: 
                        # Fallback se tipo_id não existir ou não for encontrado no mapa
                        # Podemos usar o nome da tabela capitalizado como um rótulo base.
                        main_label = tabela_sqlite.capitalize() 
                        node_props['nome_tipo'] = main_label 
                        
                    if main_label is None:
                        print(f"AVISO: Não foi possível determinar o rótulo principal para {row_dict['id_canonico']}. Usando 'Entidade'.")
                        main_label = 'Entidade'
                    
                    if ' ' in main_label:
                        main_label_cypher = f"`{main_label}`"
                    else:
                        main_label_cypher = main_label


                    if 'perfil_json' in row_dict and row_dict['perfil_json']:
                        try:
                            json_data = json.loads(row_dict['perfil_json'])
                            node_props.update(json_data)
                        except json.JSONDecodeError:
                            node_props['perfil_json_raw'] = row_dict['perfil_json']
                            
                    session.run(f"MERGE (n:Entidade {{id_canonico: $id_canonico}}) SET n += $props SET n:{main_label_cypher}",
                                id_canonico=node_props.pop('id_canonico'), props=node_props)

            # Criar Relações de Hierarquia (:DENTRO_DE) para Locais
            print("\n--- Iniciando criação de relações de hierarquia [:DENTRO_DE] para locais ---")
            locais_data = all_sqlite_data.get('locais', [])
            locais_id_map = {loc['id']: loc['id_canonico'] for loc in locais_data} # Mapeia ID numérico para ID canônico
            
            rel_locais_count = 0
            for local in locais_data:
                if local.get('parent_id') is not None:
                    filho_id_canonico = local['id_canonico']
                    pai_id_canonico = locais_id_map.get(local['parent_id'])
                    
                    if filho_id_canonico and pai_id_canonico:
                        session.run("MATCH (filho:Local {id_canonico: $filho_id}), (pai:Local {id_canonico: $pai_id}) "
                                    "MERGE (filho)-[:DENTRO_DE]->(pai)",
                                    filho_id=filho_id_canonico, pai_id=pai_id_canonico)
                        rel_locais_count += 1
            if rel_locais_count > 0:
                print(f"DEBUG: Encontradas {rel_locais_count} relações de hierarquia nos dados fornecidos.")
            else:
                print("DEBUG: Nenhuma relação de hierarquia encontrada nos dados de 'locais' (verifique parent_id).")


            # =========================================================================================
            # SEÇÃO: CRIAR RELAÇÕES DE ACESSO DIRETO (:DA_ACESSO_A)
            # =========================================================================================
            print("\n--- Iniciando criação de relações de acesso direto [:DA_ACESSO_A] ---")
            acessos_diretos_data = all_sqlite_data.get('locais_acessos_diretos', [])
            
            if acessos_diretos_data:
                print(f"DEBUG: Encontradas {len(acessos_diretos_data)} relações de acesso direto nos dados fornecidos.")
                for row in acessos_diretos_data:
                    origem_db_id = row['local_origem_id']
                    destino_db_id = row['local_destino_id']
                    tipo_acesso = row.get('tipo_acesso')
                    condicoes_acesso = row.get('condicoes_acesso')

                    origem_id_canonico = locais_id_map.get(origem_db_id)
                    destino_id_canonico = locais_id_map.get(destino_db_id)
            
                    if origem_id_canonico and destino_id_canonico:
                        print(f"  Criando acesso: {origem_id_canonico} -[:DA_ACESSO_A]-> {destino_id_canonico}")
                        
                        rel_props = {}
                        if tipo_acesso:
                            rel_props['tipo_acesso'] = tipo_acesso
                        if condicoes_acesso: 
                            rel_props['condicoes_acesso'] = condicoes_acesso

                        session.run("MATCH (origem:Local {id_canonico: $origem_id}), (destino:Local {id_canonico: $destino_id}) "
                                    "MERGE (origem)-[r:DA_ACESSO_A]->(destino) "
                                    "SET r += $rel_props", 
                                    origem_id=origem_id_canonico, destino_id=destino_id_canonico,
                                    rel_props=rel_props) 
                    else:
                        print(f"  - AVISO: Não foi possível mapear IDs numéricos ({origem_db_id}, {destino_db_id}) para IDs canônicos para criar relação :DA_ACESSO_A.")
            else:
                print("DEBUG: Nenhuma relação de acesso direto encontrada nos dados fornecidos para 'locais_acessos_diretos'.")


            # =========================================================================================
            # SEÇÃO: CRIAR RELAÇÕES UNIVERSAIS (:RELACAO_UNIVERSAL)
            # Lendo da tabela 'relacoes_entidades'
            # =========================================================================================
            print("\n--- Iniciando criação de relações universais dinâmicas ---")
            universal_relations_data = all_sqlite_data.get('relacoes_entidades', [])

            if universal_relations_data:
                print(f"DEBUG: Encontradas {len(universal_relations_data)} relações universais nos dados fornecidos.")
                for row in universal_relations_data:
                    origem_id = row['entidade_origem_id']
                    origem_tipo_tabela = row['entidade_origem_tipo']
                    tipo_relacao = row['tipo_relacao']
                    destino_id = row['entidade_destino_id']
                    destino_tipo_tabela = row['entidade_destino_tipo']
                    propriedades_json = row['propriedades_json']

                    # Converter nome da tabela SQLite para rótulo Neo4j (capitalizado)
                    origem_label_neo4j = entidades_tables_map.get(origem_tipo_tabela, origem_tipo_tabela.capitalize())
                    destino_label_neo4j = entidades_tables_map.get(destino_tipo_tabela, destino_tipo_tabela.capitalize())

                    props = {}
                    if propriedades_json:
                        try:
                            props = json.loads(propriedades_json)
                        except json.JSONDecodeError:
                            print(f"AVISO: Não foi possível parsear JSON de propriedades para a relação {tipo_relacao} (entre {origem_id} e {destino_id}).")
                            props['propriedades_json_raw'] = propriedades_json

                    session.run(f"""
                        MATCH (origem:{origem_label_neo4j} {{id_canonico: $origem_id}})
                        MATCH (destino:{destino_label_neo4j} {{id_canonico: $destino_id}})
                        MERGE (origem)-[r:`{tipo_relacao}`]->(destino)
                        SET r += $props
                    """, origem_id=origem_id, destino_id=destino_id, props=props)
                    print(f"  Criada relação '{tipo_relacao}' de {origem_id} para {destino_id}.")
            else:
                print("DEBUG: Nenhuma relação universal encontrada nos dados fornecidos para 'relacoes_entidades'.")


            # Criar Relação de Localização do Jogador (:ESTA_EM)
            print("\n--- Iniciando criação de relação de localização do jogador [:ESTA_EM] ---")
            jogador_data = all_sqlite_data.get('jogador', [])
            if jogador_data:
                # O jogador só deve ter 1 registro, pegamos o primeiro
                jogador_info = jogador_data[0] 
                jogador_id_canonico = jogador_info['id_canonico']

                # Obter o id_canonico do local atual do jogador usando o mapa de locais
                local_atual_id_numerico = jogador_info['local_atual_id']
                locais_data_map_by_id = {loc['id']: loc['id_canonico'] for loc in all_sqlite_data.get('locais', [])}
                local_atual_id_canonico = locais_data_map_by_id.get(local_atual_id_numerico)

                if jogador_id_canonico and local_atual_id_canonico:
                    print(f"DEBUG: Encontrada relação de localização do jogador no SQLite: Jogador={jogador_id_canonico}, Local={local_atual_id_canonico}")
                    session.run("MATCH (j:Jogador {id_canonico: $jogador_id}), (l:Local {id_canonico: $local_id}) "
                                "MERGE (j)-[:ESTA_EM]->(l)",
                                jogador_id=jogador_id_canonico, local_id=local_atual_id_canonico)
                else:
                    print("AVISO: Dados insuficientes para criar a relação :ESTA_EM (jogador ou local atual não encontrados).")
            else:
                print("DEBUG: Nenhuma relação de localização do jogador encontrada nos dados fornecidos para 'jogador'.")

        # sqlite_conn.close() removido, pois a conexão não é aberta aqui.
        print("\nSUCESSO: Base de dados de grafo (Neo4j) populada.")


# Removida a seção if __name__ == '__main__': test ou build,
# pois este script agora é um módulo que será chamado por sync_databases.py.
# Se precisar de um teste direto, use main_test no chromadb_manager ou crie um script de teste dedicado.
