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
    Versão: 1.6.1 - build_graph_from_data agora usa display_name como nome_tipo para nós
                   e mapeamento de tipos de entidades.
    """
    def __init__(self):
        """Inicializa o gestor e a conexão com o Neo4j."""
        try:
            # Usa configurações de config.py
            self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=basic_auth(config.NEO4J_USER, config.NEO4J_PASSWORD))
            self.driver.verify_connectivity()
            print("INFO: Neo4jManager conectado com sucesso ao Pilar C.")
            
            # Criar restrições universais na inicialização para garantir unicidade e otimização
            with self.driver.session() as session:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Local) REQUIRE n.id_canonico IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Jogador) REQUIRE n.id_canonico IS UNIQUE")
                # Adicione outras restrições UNIQUE para outros labels se necessário
            print("INFO: Restrições de unicidade do Neo4j verificadas/criadas.")

        except Exception as e:
            raise ConnectionError(f"Falha ao conectar ao Neo4j. Verifique se o serviço está a correr. Erro: {e}")

    def close(self):
        """Fecha a conexão com o Neo4j."""
        if self.driver:
            self.driver.close()
            print("INFO: Conexão com o Neo4j fechada.")

    # --- Métodos de Leitura (Consulta do Grafo) ---

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
        Adaptado para usar .nome_tipo (que agora será o display_name) para o tipo do local.
        """
        query = """
            MATCH (p:Jogador {id_canonico: $id_jogador})-[:ESTA_EM]->(local_atual:Local)
            OPTIONAL MATCH (local_atual)<-[:DENTRO_DE]-(filho:Local) // Locais contidos hierarquicamente
            OPTIONAL MATCH (local_atual)-[da:DA_ACESSO_A]->(acesso_direto:Local) // Relação de acesso explícita
            WHERE local_atual <> acesso_direto // Evita auto-referência
            
            RETURN
                local_atual { .id_canonico, .nome, .nome_tipo } AS local, // Agora buscando 'nome_tipo' (que é o display_name)
                COLLECT(DISTINCT filho { .id_canonico, .nome, .nome_tipo }) AS filhos, // Buscando 'nome_tipo' (display_name)
                COLLECT(DISTINCT acessos_diretos { .id_canonico, .nome, .nome_tipo, 'tipo_acesso': da.tipo_acesso, 'condicoes_acesso': da.condicoes_acesso }) AS acessos_diretos // Buscando 'nome_tipo' (display_name)
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

    # --- Métodos de Escrita (Atualização Incremental do Grafo) ---

    def add_or_update_node(self, id_canonico, label_base, properties, main_label=None):
        """
        Adiciona ou atualiza um nó genérico no Neo4j.
        id_canonico: ID canônico único da entidade.
        label_base: Rótulo base do tipo de entidade (ex: 'Local', 'Personagem', 'ElementoUniversal').
        properties: Dicionário de propriedades para o nó (inclui 'nome', 'nome_tipo' etc.).
        main_label: Rótulo específico (ex: 'EstacaoEspacial'), se diferente de label_base.
                    Este será derivado do nome_tipo do SQLite (snake_case)
        """
        if ' ' in label_base:
            label_base_cypher = f"`{label_base}`"
        else:
            label_base_cypher = label_base
            
        specific_label_cypher = ""
        if main_label:
            # Removendo espaços e caracteres especiais para rótulos Cypher, se for o caso
            # Assumimos que main_label já vem como nome_tipo do SQLite (snake_case) ou display_name
            # mas rótulos não podem ter espaços, então tratamos aqui.
            cleaned_main_label = main_label.replace(" ", "").replace("-", "_") 
            if cleaned_main_label: # Garante que não é uma string vazia
                specific_label_cypher = f":`{cleaned_main_label}`" if ' ' in cleaned_main_label else f":{cleaned_main_label}"

        query = f"""
            MERGE (n:Entidade:{label_base_cypher}{specific_label_cypher} {{id_canonico: $id_canonico}})
            SET n += $props
            RETURN n.id_canonico
        """
        with self.driver.session() as session:
            result = session.run(query, id_canonico=id_canonico, props=properties).single()
            return result['n.id_canonico'] if result else None

    def add_or_update_player_location_relation(self, player_id_canonico, local_id_canonico):
        """
        Cria ou atualiza a relação :ESTA_EM do jogador para um local.
        Remove relações :ESTA_EM antigas para garantir que o jogador esteja em apenas um local.
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
        Cria ou atualiza uma relação hierárquica :DENTRO_DE entre locais.
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
        Cria ou atualiza uma relação de acesso direto :DA_ACESSO_A entre locais.
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
        Cria ou atualiza uma relação universal dinâmica entre quaisquer duas entidades.
        origem_label e destino_label devem ser os rótulos do Neo4j (ex: 'Personagem', 'Local').
        """
        # Limpar rótulos para garantir compatibilidade com Cypher (remove espaços, etc.)
        cleaned_origem_label = origem_label.replace(" ", "").replace("-", "_")
        cleaned_destino_label = destino_label.replace(" ", "").replace("-", "_")
        cleaned_tipo_relacao = tipo_relacao.replace(" ", "_").upper() # Relações geralmente em UPPER_SNAKE_CASE

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

    async def build_graph_from_data(self, all_sqlite_data): # Recebe all_sqlite_data
        """
        Constrói/atualiza o grafo no Neo4j a partir de um dicionário contendo todos os dados do SQLite.
        Esta função é o coração do processo de construção do Pilar C.
        AGORA USA OS MÉTODOS INCREMENTAIS E NÃO APAGA O GRAFO INTEIRO NA RECONSTRUÇÃO EM LOTE.
        Atualizado para usar 'display_name' como 'nome_tipo' para os nós e para
        usar o 'nome_tipo' (snake_case) como o main_label quando apropriado.
        """
        print("\n--- A construir o Pilar C (Neo4j) a partir dos dados fornecidos (Pilar B) ---")

        with self.driver.session() as session:
            # REMOVIDO: session.run("MATCH (n) DETACH DELETE n")
            # A exclusão total do grafo agora só seria feita se explicitamente necessário (ex: reset de dev)
            print("INFO: O grafo Neo4j não será limpo completamente, apenas atualizado.")
            

            # 1. Obter mapeamento de tipos_entidades (tipo_id para nome_tipo e display_name) dos dados fornecidos
            type_info_map = {}
            tipos_entidades_data = all_sqlite_data.get('tipos_entidades', [])
            try:
                for row in tipos_entidades_data:
                    type_info_map[(row['nome_tabela'], row['id'])] = {
                        'nome_tipo': row['nome_tipo'], # Ex: 'estacao_espacial' (snake_case)
                        'display_name': row['display_name'] # Ex: 'Estação Espacial'
                    }
                print(f"DEBUG: Mapeamento de tipos_entidades carregado: {type_info_map}")
            except Exception as e:
                print(f"ERRO: Falha ao carregar mapeamento de tipos_entidades dos dados fornecidos: {e}.")
                return # Sai da função se a tabela essencial não existe

            # Mapeamento de tabelas SQLite para rótulos de nós Neo4j base
            entidades_tables_map = {
                "locais": "Local",
                "elementos_universais": "ElementoUniversal",
                "personagens": "Personagem",
                "faccoes": "Faccao",
                "jogador": "Jogador" # Jogador é um tipo específico de Personagem, mas terá seu próprio label
            }

            # 2. Criar ou atualizar nós para todas as entidades universais a partir dos dados fornecidos
            for tabela_sqlite, label_base_neo4j in entidades_tables_map.items():
                data_for_table = all_sqlite_data.get(tabela_sqlite, [])
                if not data_for_table:
                    print(f"AVISO: Nenhuns dados para a tabela '{tabela_sqlite}'. Pulando criação de nós.")
                    continue

                print(f"Criando/Atualizando nós da tabela '{tabela_sqlite}' ({len(data_for_table)} registros)...")
                
                for row_dict in data_for_table:
                    node_props = {
                        'id_canonico': row_dict['id_canonico'],
                        'nome': row_dict['nome']
                    }
                    
                    # main_label_neo4j será o rótulo Cypher específico (snake_case)
                    # nome_tipo_prop_neo4j será a propriedade 'nome_tipo' (display_name)
                    main_label_neo4j = None 
                    nome_tipo_prop_neo4j = None

                    if 'tipo_id' in row_dict and row_dict['tipo_id'] is not None:
                        type_details = type_info_map.get((tabela_sqlite, row_dict['tipo_id']))
                        if type_details:
                            nome_tipo_prop_neo4j = type_details['display_name'] # A propriedade nome_tipo agora é o display_name
                            main_label_neo4j = type_details['nome_tipo'] # O label específico (snake_case)
                            node_props['nome_tipo_interno'] = type_details['nome_tipo'] # Mantém o nome_tipo interno como propriedade
                        else:
                            # Fallback se o tipo_id não for encontrado no mapeamento
                            print(f"AVISO: Tipo ID {row_dict['tipo_id']} para {tabela_sqlite} não encontrado no mapeamento. Usando tipo genérico.")
                            nome_tipo_prop_neo4j = label_base_neo4j
                            main_label_neo4j = label_base_neo4j

                    # Adiciona a propriedade 'nome_tipo' ao nó, usando o display_name
                    node_props['nome_tipo'] = nome_tipo_prop_neo4j if nome_tipo_prop_neo4j else label_base_neo4j
                    
                    if 'perfil_json' in row_dict and row_dict['perfil_json']:
                        try:
                            json_data = json.loads(row_dict['perfil_json'])
                            node_props.update(json_data)
                        except json.JSONDecodeError:
                            node_props['perfil_json_raw'] = row_dict['perfil_json']
                    
                    # Chamar o novo método incremental
                    self.add_or_update_node(
                        id_canonico=node_props['id_canonico'],
                        label_base=label_base_neo4j,
                        properties=node_props,
                        main_label=main_label_neo4j # Passa o rótulo específico (snake_case)
                    )
            
            # --- CRIAR RELAÇÕES ---

            # Criar Relações de Hierarquia (:DENTRO_DE) para Locais
            print("\n--- Iniciando criação de relações de hierarquia [:DENTRO_DE] para locais ---")
            locais_data = all_sqlite_data.get('locais', [])
            locais_id_map = {loc['id']: loc['id_canonico'] for loc in locais_data} # Mapeia ID numérico para ID canônico
            
            for local in locais_data:
                if local.get('parent_id') is not None:
                    filho_id_canonico = local['id_canonico']
                    pai_id_canonico = locais_id_map.get(local['parent_id'])
                    
                    if filho_id_canonico and pai_id_canonico:
                        self.add_or_update_parent_child_relation(filho_id_canonico, pai_id_canonico)
            
            # SEÇÃO: CRIAR RELAÇÕES DE ACESSO DIRETO (:DA_ACESSO_A)
            print("\n--- Iniciando criação de relações de acesso direto [:DA_ACESSO_A] ---")
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

            # SEÇÃO: CRIAR RELAÇÕES UNIVERSAIS (:RELACAO_UNIVERSAL)
            print("\n--- Iniciando criação de relações universais dinâmicas ---")
            universal_relations_data = all_sqlite_data.get('relacoes_entidades', [])

            if universal_relations_data:
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

                    self.add_or_update_universal_relation(origem_id, origem_label_neo4j, tipo_relacao, destino_id, destino_label_neo4j, props)

            # Criar Relação de Localização do Jogador (:ESTA_EM)
            print("\n--- Iniciando criação de relação de localização do jogador [:ESTA_EM] ---")
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
                    print("AVISO: Dados insuficientes para criar a relação :ESTA_EM (jogador ou local atual não encontrados).")
            else:
                print("DEBUG: Nenhuma relação de localização do jogador encontrada nos dados fornecidos para 'jogador'.")

        print("\nSUCESSO: Base de dados de grafo (Neo4j) populada/atualizada.")
