import json
import asyncio
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Processa chamadas de função da IA, executa-as e sincroniza os pilares de dados.
    Versão: 1.2.0 - Adicionada resiliência para lidar com chamadas de funções desconhecidas, evitando erros de contagem de respostas.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.data_manager = data_manager
        self.chromadb_manager = chromadb_manager
        self.neo4j_manager = neo4j_manager
        self._register_available_functions()

    def _register_available_functions(self):
        """Mapeia os nomes das funções para os métodos dos gestores."""
        self.available_functions = {
            # Funções do DataManager (SQLite)
            "add_or_get_location": self.data_manager.add_or_get_location,
            "add_or_get_player": self.data_manager.add_or_get_player,
            "add_player_vitals": self.data_manager.add_player_vitals,
            "add_player_skill": self.data_manager.add_player_skill,
            "add_player_knowledge": self.data_manager.add_player_knowledge,
            "add_or_get_player_possession": self.data_manager.add_or_get_player_possession,
            "update_player_location": self.data_manager.update_player_location,
            "add_direct_access_relation": self.data_manager.add_direct_access_relation,
            "add_universal_relation": self.data_manager.add_universal_relation,
            "add_or_get_element_universal": self.data_manager.add_or_get_element_universal,
            "add_or_get_personagem": self.data_manager.add_or_get_personagem,
            "add_or_get_faccao": self.data_manager.add_or_get_faccao,
            "add_log_memory": self.data_manager.add_log_memory, # Adicionado para garantir que esteja disponível
            
            # Funções do ChromaDBManager
            "add_or_update_lore": self.chromadb_manager.add_or_update_lore,
            
            # Funções do Neo4jManager
            "add_or_update_parent_child_relation": self.neo4j_manager.add_or_update_parent_child_relation,
        }
        # Mapeamento para sincronização dos pilares
        self.table_name_map = {
            "add_or_get_location": "locais",
            "add_or_get_player": "jogador",
            "add_or_get_element_universal": "elementos_universais",
            "add_or_get_personagem": "personagens",
            "add_or_get_faccao": "faccoes",
            "add_or_get_player_possession": "jogador_posses"
        }

    async def process(self, tool_calls_from_llm):
        """
        Processa uma lista de chamadas de ferramentas, garantindo que uma resposta seja gerada para cada chamada.
        """
        tool_responses_parts = []
        for tc in tool_calls_from_llm:
            function_call = tc["functionCall"]
            function_name = function_call["name"]
            function_response = None

            if function_name in self.available_functions:
                func_to_call = self.available_functions[function_name]
                # Processa os argumentos, convertendo strings JSON em objetos Python quando necessário
                processed_args = {k: json.loads(v) if isinstance(v, str) and (k.endswith('_data') or k == 'metadata') else v 
                                  for k, v in function_call.get("args", {}).items()}

                try:
                    # Executa a função (seja ela síncrona ou assíncrona)
                    result = await func_to_call(**processed_args) if asyncio.iscoroutinefunction(func_to_call) else func_to_call(**processed_args)
                    function_response = result if result is not None else "Executado com sucesso."
                    
                    # Se a função foi bem-sucedida e é uma que cria uma entidade principal, sincroniza os outros pilares.
                    if function_name in self.table_name_map and result not in [None, False]:
                        id_canonico_to_sync = processed_args.get("id_canonico") or processed_args.get("player_canonical_id") or processed_args.get("posse_id_canonico")
                        if id_canonico_to_sync:
                            await self._sync_pillars_for_entity(id_canonico_to_sync, self.table_name_map[function_name], processed_args, function_name)
                
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    function_response = f"ERRO ao executar a ferramenta '{function_name}': {e}"
            else:
                # **LÓGICA DE CORREÇÃO:** Se a função não for encontrada, gera uma resposta de erro em vez de ignorar.
                print(f"ERRO: A IA tentou chamar uma função desconhecida: '{function_name}'")
                function_response = f"ERRO: Função '{function_name}' não encontrada ou não registrada no ToolProcessor."
            
            # Garante que uma resposta seja adicionada para CADA chamada de ferramenta, mantendo a contagem correta.
            tool_responses_parts.append({
                "functionResponse": {
                    "name": function_name, 
                    "response": {"result": str(function_response)}
                }
            })

        return tool_responses_parts

    async def _sync_pillars_for_entity(self, id_canonico, table_name, processed_args, function_name):
        """Sincroniza ChromaDB e Neo4j para uma entidade recém-criada ou atualizada no SQLite."""
        entity_details = self.data_manager.get_entity_details_by_canonical_id(table_name, id_canonico)
        if not entity_details: 
            print(f"AVISO: Não foi possível encontrar detalhes da entidade '{id_canonico}' na tabela '{table_name}' para sincronização.")
            return

        # Sincroniza com o ChromaDB
        text_content, metadata = self._prepare_chroma_data(entity_details, table_name)
        if text_content: 
            await self.chromadb_manager.add_or_update_lore(id_canonico, text_content, metadata)

        # Sincroniza com o Neo4j
        await self._update_neo4j_graph(entity_details, table_name, processed_args, function_name)

    def _prepare_chroma_data(self, entity_details, table_name):
        """Prepara os dados de uma entidade para serem vetorizados no ChromaDB."""
        nome = entity_details.get('nome', '')
        tipo = entity_details.get('tipo', 'Desconhecido')
        perfil_json_str = entity_details.get('perfil_json') or entity_details.get('perfil_completo_json') or '{}'
        perfil = json.loads(perfil_json_str)
        
        text_map = {
            "locais": f"Local: {nome}. Tipo: {tipo}. Descrição: {perfil.get('descricao', 'N/A')}.",
            "jogador": f"O Jogador principal: {nome}. Raça: {perfil.get('raca', 'N/A')}. Ocupação: {perfil.get('ocupacao', 'N/A')}.",
            "personagens": f"Personagem: {nome}. Tipo: {tipo}. Detalhes: {perfil_json_str}",
            "elementos_universais": f"Elemento: {nome}. Tipo: {tipo}. Detalhes: {perfil_json_str}",
            "faccoes": f"Facção: {nome}. Tipo: {tipo}. Detalhes: {perfil_json_str}",
            "jogador_posses": f"Posse do jogador: {entity_details.get('item_nome', 'N/A')}. Detalhes: {perfil_json_str}",
        }
        text_content = text_map.get(table_name, f"Entidade: {nome}. Tipo: {tipo}. Detalhes: {perfil_json_str}")
        metadata = {"id_canonico": entity_details['id_canonico'], "tipo": table_name.replace("_", "-"), "nome": nome, "subtipo": tipo}
        return text_content, metadata

    async def _update_neo4j_graph(self, entity_details, table_name, processed_args, function_name):
        """Atualiza o grafo Neo4j com o novo nó e suas relações iniciais."""
        neo4j_label_map = {
            "locais": "Local", "jogador": "Jogador", "elementos_universais": "ElementoUniversal",
            "personagens": "Personagem", "faccoes": "Faccao",
        }
        base_label = neo4j_label_map.get(table_name)
        if not base_label: return

        # Adiciona ou atualiza o nó
        node_properties = {k: v for k, v in entity_details.items() if isinstance(v, (str, int, float, bool))}
        self.neo4j_manager.add_or_update_node(
            id_canonico=entity_details['id_canonico'], label_base=base_label,
            properties=node_properties, main_label=entity_details.get('tipo', '').replace(" ", "")
        )

        # Adiciona relações iniciais com base na função que foi chamada
        if function_name == "add_or_get_location" and "parent_id_canonico" in processed_args and processed_args["parent_id_canonico"]:
            self.neo4j_manager.add_or_update_parent_child_relation(entity_details['id_canonico'], processed_args["parent_id_canonico"])
        elif function_name == "add_or_get_player" and "local_inicial_id_canonico" in processed_args:
            self.neo4j_manager.add_or_update_player_location_relation(entity_details['id_canonico'], processed_args["local_inicial_id_canonico"])
            