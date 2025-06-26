import os
import sys
import sqlite3
import json # Necessário para perfil_json
from neo4j import GraphDatabase, basic_auth

# --- Configuração de Caminhos e DBs ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH_SQLITE = os.path.join(PROD_DATA_DIR, 'estado.db')

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password" # Mude se a sua password for diferente

class Neo4jManager:
    """
    API dedicada para interagir com o Pilar C (Base de Dados de Grafo - Neo4j).
    Fornece métodos para consultar relações, caminhos e o estado do universo no grafo.
    Versão: 1.4.0 - Adaptado para esquema universal v9.0 (tipos_entidades, timestamps).
    """
    def __init__(self):
        """Inicializa o gestor e a conexão com o Neo4j."""
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))
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
        # A query busca o caminho da raiz até o nó inicial, depois inverte.
        # Necessário um JOIN para obter o nome do tipo do nó.
        query = """
            MATCH (start:Local {id_canonico: $id})
            MATCH path = (root:Local)-[:DENTRO_DE*]->(start)
            WHERE NOT EXISTS((:Local)-[:DENTRO_DE]->(root)) // Garante que 'root' é um nó raiz
            RETURN [node IN nodes(path) | node.nome] AS names
        """
        # A query anterior Order By size(names) DESC limit 1 não era tão robusta
        # para garantir o caminho da raiz ao nó. Essa busca da raiz ao nó.

        with self.driver.session() as session:
            result = session.run(query, id=local_id_canonico).single()
            return result['names'] if result and result['names'] else []


    def get_player_location_details(self, player_id_canonico='pj_gabriel_oliveira'):
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


def build_graph_from_sqlite(sqlite_path, neo4j_driver):
    """
    Lê os dados do SQLite e constrói/atualiza o grafo no Neo4j.
    Esta função é o coração do processo de construção do Pilar C, adaptada para o esquema universal v9.0.
    """
    print("\n--- A construir o Pilar C (Neo4j) a partir do Pilar B (SQLite) ---")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row # Para acessar colunas por nome
    cursor = sqlite_conn.cursor()

    with neo4j_driver.session() as session:
        print("Limpando grafo existente e criando restrições...")
        session.run("MATCH (n) DETACH DELETE n")
        # Restrição universal para id_canonico em nós 'Entidade'
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id_canonico IS UNIQUE")

        # 1. Obter mapeamento de tipos_entidades (tipo_id para nome_tipo)
        # Necessário para definir labels dinâmicos e propriedades de tipo nos nós Neo4j
        type_id_to_name_map = {}
        try:
            cursor.execute("SELECT id, nome_tabela, nome_tipo FROM tipos_entidades")
            for row in cursor.fetchall():
                # Armazena o nome_tipo por (nome_tabela, id_do_tipo)
                type_id_to_name_map[(row['nome_tabela'], row['id'])] = row['nome_tipo']
            print(f"DEBUG: Mapeamento de tipos_entidades carregado: {type_id_to_name_map}")
        except sqlite3.OperationalError as e:
            print(f"ERRO: Tabela 'tipos_entidades' não encontrada ou erro: {e}. Execute build_world.py v9.0 primeiro!")
            sqlite_conn.close()
            return # Sai da função se a tabela essencial não existe

        # Mapeamento de tabelas SQLite para rótulos de nós Neo4j base
        # O rótulo principal (ex: Local, Personagem) virá do nome_tipo
        # 'Entidade' é um rótulo base comum para todos os nós canônicos
        entidades_tables = {
            "locais": "locais", # nome da tabela no tipos_entidades
            "elementos_universais": "elementos_universais",
            "personagens": "personagens",
            "faccoes": "faccoes",
            "jogador": "jogador" # Embora 'jogador' não tenha tipo_id, será tratado como Personagem/Jogador
        }

        # 2. Criar nós para todas as entidades universais
        for tabela_sqlite, table_type_name_in_meta in entidades_tables.items():
            print(f"Criando nós da tabela '{tabela_sqlite}'...")
            
            # Obter informações das colunas para saber se 'tipo_id' e 'perfil_json' existem
            cursor.execute(f"PRAGMA table_info({tabela_sqlite});")
            colunas_info = [info['name'] for info in cursor.fetchall()]
            
            select_cols = ['id_canonico', 'nome']
            if 'tipo_id' in colunas_info: # Se a tabela usa tipo_id (v9.0)
                select_cols.append('tipo_id')
            #else: # Se for a tabela 'jogador' que não tem tipo_id mas tem um tipo implícito
            #    # Para o jogador, podemos definir um tipo padrão se não houver tipo_id
            #    if tabela_sqlite == 'jogador':
            #        # Poderíamos buscar o tipo_id para 'Jogador' da tabela 'personagens'
            #        pass 
            
            if 'perfil_json' in colunas_info:
                select_cols.append('perfil_json')

            cursor.execute(f"SELECT {', '.join(select_cols)} FROM {tabela_sqlite}")
            for row in cursor.fetchall():
                node_props = {
                    'id_canonico': row['id_canonico'],
                    'nome': row['nome']
                }
                
                main_label = None # O rótulo principal do Neo4j
                
                # Determinar o rótulo principal do Neo4j a partir de tipo_id ou nome da tabela
                if 'tipo_id' in select_cols and row['tipo_id'] is not None:
                    main_label = type_id_to_name_map.get((table_type_name_in_meta, row['tipo_id']))
                    node_props['nome_tipo'] = main_label # Adiciona o nome do tipo como propriedade
                elif tabela_sqlite == 'jogador': # Caso específico para a tabela jogador
                    main_label = 'Jogador' # Rótulo padrão para o jogador
                    node_props['nome_tipo'] = 'Jogador' # Adiciona o nome do tipo como propriedade
                elif tabela_sqlite == 'locais' and row['id_canonico'] == 'braco_orion': # Exemplo de default para root
                    main_label = 'BracoEspiral' # Ou 'Galaxia', etc.
                    node_props['nome_tipo'] = 'BracoEspiral' # Adiciona o nome do tipo como propriedade
                else: # Fallback para rótulo baseado no nome da tabela se tipo_id não for aplicável/encontrado
                    main_label = entidades_map.get(tabela_sqlite, tabela_sqlite.capitalize())
                    node_props['nome_tipo'] = main_label # Adiciona o nome do tipo como propriedade
                    
                if main_label is None:
                    print(f"AVISO: Não foi possível determinar o rótulo principal para {row['id_canonico']}. Usando 'Entidade'.")
                    main_label = 'Entidade'
                
                # Se main_label tiver espaços ou caracteres especiais, precisamos escapá-lo no Cypher
                # Para simplicidade, vamos assumir nomes de tipo sem espaços para labels.
                # Se os nomes dos tipos_entidades puderem ter espaços, precisará de backticks: `My Type`
                if ' ' in main_label:
                    main_label_cypher = f"`{main_label}`"
                else:
                    main_label_cypher = main_label


                if 'perfil_json' in select_cols and row['perfil_json']:
                    try:
                        json_data = json.loads(row['perfil_json'])
                        node_props.update(json_data)
                    except json.JSONDecodeError:
                        node_props['perfil_json_raw'] = row['perfil_json']
                        
                # Adiciona o rótulo genérico 'Entidade' e o rótulo específico (main_label)
                session.run(f"MERGE (n:Entidade {{id_canonico: $id_canonico}}) SET n += $props SET n:{main_label_cypher}",
                            id_canonico=node_props.pop('id_canonico'), props=node_props)

        # Criar Relações de Hierarquia (:DENTRO_DE) para Locais
        print("\n--- Iniciando criação de relações de hierarquia [:DENTRO_DE] para locais ---")
        try:
            cursor.execute("SELECT c.id_canonico AS filho_id_canonico, p.id_canonico AS pai_id_canonico FROM locais c JOIN locais p ON c.parent_id = p.id")
            rel_locais_data = cursor.fetchall()
            if rel_locais_data:
                print(f"DEBUG: Encontradas {len(rel_locais_data)} relações de hierarquia no SQLite.")
                for row in rel_locais_data:
                    session.run("MATCH (filho:Local {id_canonico: $filho_id}), (pai:Local {id_canonico: $pai_id}) "
                                "MERGE (filho)-[:DENTRO_DE]->(pai)",
                                filho_id=row['filho_id_canonico'], pai_id=row['pai_id_canonico'])
            else:
                print("DEBUG: Nenhuma relação de hierarquia encontrada na tabela 'locais' do SQLite (verifique parent_id).")
        except sqlite3.OperationalError as e:
            print(f"ERRO SQLITE (Relações Hierarquia): {e}")
            print("Verifique se a tabela 'locais' e a coluna 'parent_id' existem e estão corretas.")

        # =========================================================================================
        # SEÇÃO: CRIAR RELAÇÕES DE ACESSO DIRETO (:DA_ACESSO_A) - AGORA COM TIPOS E CONDIÇÕES
        # Corrigido para lidar com valores nulos para propriedades de relacionamento.
        # =========================================================================================
        print("\n--- Iniciando criação de relações de acesso direto [:DA_ACESSO_A] ---")
        try:
            # Inclui as colunas tipo_acesso e condicoes_acesso
            cursor.execute("SELECT local_origem_id, local_destino_id, tipo_acesso, condicoes_acesso FROM locais_acessos_diretos")
            acessos_diretos_data = cursor.fetchall()
        
            if acessos_diretos_data:
                print(f"DEBUG: Encontradas {len(acessos_diretos_data)} relações de acesso direto no SQLite.")
                # Mapeie os IDs internos do SQLite de volta para os id_canonico
                cursor.execute("SELECT id, id_canonico FROM locais")
                sqlite_to_canonico_map = {row['id']: row['id_canonico'] for row in cursor.fetchall()}
        
                for row in acessos_diretos_data:
                    origem_db_id = row['local_origem_id']
                    destino_db_id = row['local_destino_id']
                    tipo_acesso = row['tipo_acesso']
                    condicoes_acesso = row['condicoes_acesso']

                    origem_id_canonico = sqlite_to_canonico_map.get(origem_db_id)
                    destino_id_canonico = sqlite_to_canonico_map.get(destino_db_id)
        
                    if origem_id_canonico and destino_id_canonico:
                        print(f"  Criando acesso: {origem_id_canonico} -[:DA_ACESSO_A]-> {destino_id_canonico}")
                        
                        # Construir dicionário de propriedades dinamicamente, ignorando None
                        rel_props = {}
                        if tipo_acesso:
                            rel_props['tipo_acesso'] = tipo_acesso
                        if condicoes_acesso: # APENAS SE condicoes_acesso NÃO FOR NULO
                            rel_props['condicoes_acesso'] = condicoes_acesso

                        # Usar SET r += $props para adicionar apenas propriedades não nulas
                        session.run("MATCH (origem:Local {id_canonico: $origem_id}), (destino:Local {id_canonico: $destino_id}) "
                                    "MERGE (origem)-[r:DA_ACESSO_A]->(destino) "
                                    "SET r += $rel_props", # Adiciona apenas as propriedades presentes em rel_props
                                    origem_id=origem_id_canonico, destino_id=destino_id_canonico,
                                    rel_props=rel_props) # Passa o dicionário de propriedades
                    else:
                        print(f"  - AVISO: Não foi possível mapear IDs SQLite ({origem_db_id}, {destino_db_id}) para IDs canônicos para criar relação :DA_ACESSO_A.")
            else:
                print("DEBUG: Nenhuma relação de acesso direto encontrada na tabela 'locais_acessos_diretos' do SQLite.")
        except sqlite3.OperationalError as e:
            print(f"ERRO SQLITE (Relações Acessos Diretos): {e}")
            print("Verifique se a tabela 'locais_acessos_diretos' existe e está correta.")
        except Exception as e:
            print(f"ERRO inesperado ao criar relações :DA_ACESSO_A no Neo4j: {e}")


        # =========================================================================================
        # SEÇÃO: CRIAR RELAÇÕES UNIVERSAIS (:RELACAO_UNIVERSAL)
        # Lendo da tabela 'relacoes_entidades'
        # =========================================================================================
        print("\n--- Iniciando criação de relações universais dinâmicas ---")
        try:
            cursor.execute("SELECT entidade_origem_id, entidade_origem_tipo, tipo_relacao, entidade_destino_id, entidade_destino_tipo, propriedades_json FROM relacoes_entidades")
            universal_relations_data = cursor.fetchall()

            if universal_relations_data:
                print(f"DEBUG: Encontradas {len(universal_relations_data)} relações universais no SQLite.")
                for row in universal_relations_data:
                    origem_id = row['entidade_origem_id']
                    origem_tipo_tabela = row['entidade_origem_tipo']
                    tipo_relacao = row['tipo_relacao']
                    destino_id = row['entidade_destino_id']
                    destino_tipo_tabela = row['entidade_destino_tipo']
                    propriedades_json = row['propriedades_json']

                    # Converter nome da tabela SQLite para rótulo Neo4j (capitalizado)
                    origem_label_neo4j = entidades_map.get(origem_tipo_tabela, origem_tipo_tabela.capitalize())
                    destino_label_neo4j = entidades_map.get(destino_tipo_tabela, destino_tipo_tabela.capitalize())

                    props = {}
                    if propriedades_json:
                        try:
                            props = json.loads(propriedades_json)
                        except json.JSONDecodeError:
                            print(f"AVISO: Não foi possível parsear JSON de propriedades para a relação {tipo_relacao} (entre {origem_id} e {destino_id}).")
                            props['propriedades_json_raw'] = propriedades_json

                    # MERGE para garantir que os nós existam e CREATE para criar a relação
                    # Usar rótulos dinâmicos (Personagem, Local, etc.)
                    session.run(f"""
                        MATCH (origem:{origem_label_neo4j} {{id_canonico: $origem_id}})
                        MATCH (destino:{destino_label_neo4j} {{id_canonico: $destino_id}})
                        MERGE (origem)-[r:`{tipo_relacao}`]->(destino)
                        SET r += $props
                    """, origem_id=origem_id, destino_id=destino_id, props=props)
                    print(f"  Criada relação '{tipo_relacao}' de {origem_id} para {destino_id}.")
            else:
                print("DEBUG: Nenhuma relação universal encontrada na tabela 'relacoes_entidades' do SQLite.")
        except sqlite3.OperationalError as e:
            print(f"ERRO SQLITE (Relações Universais): {e}")
            print("Verifique se a tabela 'relacoes_entidades' existe e está correta.")
        except Exception as e:
            print(f"ERRO inesperado ao criar relações universais no Neo4j: {e}")


        # Criar Relação de Localização do Jogador (:ESTA_EM)
        print("\n--- Iniciando criação de relação de localização do jogador [:ESTA_EM] ---")
        try:
            cursor.execute("SELECT j.id_canonico AS jogador_id, l.id_canonico AS local_id FROM jogador j JOIN locais l ON j.local_atual_id = l.id")
            rel_jogador_data = cursor.fetchall()
            if rel_jogador_data:
                print(f"DEBUG: Encontradas {len(rel_jogador_data)} relações de localização do jogador no SQLite.")
                for row in rel_jogador_data:
                    jogador_id = row['jogador_id']
                    local_id = row['local_id']
                    print(f"  Processando relação: Jogador={jogador_id}, Local={local_id}")
                    session.run("MATCH (j:Jogador {id_canonico: $jogador_id}), (l:Local {id_canonico: $local_id}) "
                                "MERGE (j)-[:ESTA_EM]->(l)",
                                jogador_id=jogador_id, local_id=local_id)
            else:
                print("DEBUG: Nenhuma relação de localização do jogador encontrada na tabela 'jogador' do SQLite (verifique local_atual_id).")
        except sqlite3.OperationalError as e:
            print(f"ERRO SQLITE (Relação Jogador Local): {e}")
            print("Verifique se as tabelas 'jogador' e 'locais' e as colunas 'local_atual_id' e 'id' existem e estão corretas.")

    sqlite_conn.close()
    print("\nSUCESSO: Base de dados de grafo (Neo4j) populada.")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'build':
        print("\nIniciando o processo de construção do grafo Neo4j...")
        driver = None
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            build_graph_from_sqlite(DB_PATH_SQLITE, driver)
        except ConnectionError as e:
            print(f"ERRO DE CONEXÃO: {e}")
            print("Certifique-se de que o Neo4j está a correr e acessível.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERRO INESPERADO durante a construção do grafo: {e}")
        finally:
            if driver:
                driver.close()
                print("Conexão do driver Neo4j fechada.")
            print("Processo de construção do grafo finalizado.")
    elif len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("\n--- A testar as consultas do Neo4jManager ---")
        manager = None
        try:
            manager = Neo4jManager()

            # Teste 1: get_full_path_to_local
            print("\n--- Testando: get_full_path_to_local ---")
            # Para testar, você precisa ter dados no SQLite e ter rodado 'python neo4j_manager.py build'
            # antes. Por exemplo, se você criou a 'estacao_base_alfa' e 'lab_central_alfa' via main.py
            caminho = manager.get_full_path_to_local("lab_central_alfa")
            if caminho:
                print(f"Caminho completo para 'lab_central_alfa': {' -> '.join(caminho)}")
            else:
                print("Caminho não encontrado para 'lab_central_alfa'. Verifique o ID e se as relações DENTRO_DE foram criadas.")

            # Teste 2: get_player_location_details (localização inicial)
            print("\n--- Testando: get_player_location_details() (Localização Inicial) ---")
            detalhes_loc_inicial = manager.get_player_location_details(player_id_canonico='pj_gabriel_oliveira')
            if detalhes_loc_inicial:
                print("Detalhes da localização inicial do jogador:")
                print(f"  Local Atual: {detalhes_loc_inicial.get('local', {}).get('nome', 'N/A')} (ID: {detalhes_loc_inicial.get('local', {}).get('id_canonico', 'N/A')})")
                print(f"  Locais Filhos: {', '.join([f'{f.get('nome', 'N/A')} (ID: {f.get('id_canonico', 'N/A')})' for f in detalhes_loc_inicial.get('filhos', [])])}")
                print(f"  Acessos Diretos: {', '.join([f'{a.get('nome', 'N/A')} (ID: {a.get('id_canonico', 'N/A')}) (Tipo: {a.get('tipo_acesso', 'N/A')}, Condição: {a.get('condicoes_acesso', 'N/A')})' for a in detalhes_loc_inicial.get('acessos_diretos', [])])}")
            else:
                print("Não foi possível obter detalhes da localização do jogador. Verifique o ID do jogador ou se a relação ESTA_EM foi criada.")

            # Teste 3: update_player_location_in_graph
            print("\n--- Testando: update_player_location_in_graph('pj_gabriel_oliveira', 'estacao_base_alfa') ---")
            manager.update_player_location_in_graph('pj_gabriel_oliveira', 'estacao_base_alfa')

            # Teste 4: get_player_location_details (localização após atualização)
            print("\n--- Testando: get_player_location_details() (Localização Após Atualização) ---")
            detalhes_loc_final = manager.get_player_location_details(player_id_canonico='pj_gabriel_oliveira')
            if detalhes_loc_final:
                print("Detalhes da localização do jogador após atualização:")
                print(f"  Novo Local Atual: {detalhes_loc_final.get('local', {}).get('nome', 'N/A')} (ID: {detalhes_loc_final.get('local', {}).get('id_canonico', 'N/A')})")
                print(f"  Locais Filhos: {', '.join([f'{f.get('nome', 'N/A')} (ID: {f.get('id_canonico', 'N/A')})' for f in detalhes_loc_final.get('filhos', [])])}")
                print(f"  Acessos Diretos: {', '.join([f'{a.get('nome', 'N/A')} (ID: {a.get('id_canonico', 'N/A')}) (Tipo: {a.get('tipo_acesso', 'N/A')}, Condição: {a.get('condicoes_acesso', 'N/A')})' for a in detalhes_loc_final.get('acessos_diretos', [])])}")
            else:
                print("Não foi possível obter detalhes da localização do jogador após a atualização.")

        except ConnectionError as e:
            print(f"ERRO DE CONEXÃO: {e}")
            print("Certifique-se de que o Neo4j está a correr e acessível.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERRO INESPERADO durante o teste: {e}")
        finally:
            if manager:
                manager.close()
            print("--- Testes do Neo4jManager finalizados ---")
    else:
        print("Uso: python servidor/neo4j_manager.py [build|test]")
