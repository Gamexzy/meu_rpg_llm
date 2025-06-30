import json
import asyncio
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Processa chamadas de função da IA, executa-as e sincroniza os pilares de dados.
    Versão: 1.1.0 - Corrigido o nome da variável de chromadb_manager.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.data_manager = data_manager
        self.chromadb_manager = chromadb_manager
        self.neo4j_manager = neo4j_manager
        self._register_available_functions()

    def _register_available_functions(self):
        """Mapeia os nomes das funções para os métodos dos gestores."""
        self.available_functions = {
            # DataManager functions
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
            
            # ChromaDBManager functions
            "add_or_update_lore": self.chromadb_manager.add_or_update_lore, # CORREÇÃO: Usado self.chromadb_manager
            
            # Neo4jManager functions
            "add_or_update_parent_child_relation": self.neo4j_manager.add_or_update_parent_child_relation,
        }
        self.table_name_map = {
            "add_or_get_location": "locais",
            "add_or_get_player": "jogador",
            "add_or_get_element_universal": "elementos_universais",
            "add_or_get_personagem": "personagens",
            "add_or_get_faccao": "faccoes",
            "add_or_get_player_possession": "jogador_posses"
        }

    async def process(self, tool_calls_from_llm):
        """Processa uma lista de chamadas de ferramentas."""
        tool_responses_parts = []
        for tc in tool_calls_from_llm:
            function_call = tc["functionCall"]
            function_name = function_call["name"]
            
            if function_name in self.available_functions:
                func_to_call = self.available_functions[function_name]
                processed_args = {k: json.loads(v) if isinstance(v, str) and (k.endswith('_data') or k == 'metadata') else v 
                                  for k, v in function_call.get("args", {}).items()}

                try:
                    function_response = await func_to_call(**processed_args) if asyncio.iscoroutinefunction(func_to_call) else func_to_call(**processed_args)
                    
                    if function_name in self.table_name_map and function_response not in [None, False]:
                        id_canonico_to_sync = processed_args.get("id_canonico") or processed_args.get("player_canonical_id")
                        if id_canonico_to_sync:
                            await self._sync_pillars_for_entity(id_canonico_to_sync, self.table_name_map[function_name], processed_args, function_name)
                
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    function_response = f"ERRO: {e}"
                
                tool_responses_parts.append({"functionResponse": {"name": function_name, "response": {"result": str(function_response)}}})
        return tool_responses_parts

    async def _sync_pillars_for_entity(self, id_canonico, table_name, processed_args, function_name):
        """Sincroniza ChromaDB e Neo4j para uma entidade."""
        entity_details = self.data_manager.get_entity_details_by_canonical_id(table_name, id_canonico)
        if not entity_details: return

        text_content, metadata = self._prepare_chroma_data(entity_details, table_name)
        if text_content: 
            await self.chromadb_manager.add_or_update_lore(id_canonico, text_content, metadata) # CORREÇÃO: Usado self.chromadb_manager

        await self._update_neo4j_graph(entity_details, table_name, processed_args, function_name)

    def _prepare_chroma_data(self, entity_details, table_name):
        """Prepara os dados para o ChromaDB."""
        nome = entity_details.get('nome', '')
        tipo = entity_details.get('tipo', 'Desconhecido')
        perfil_json_str = entity_details.get('perfil_json') or entity_details.get('perfil_completo_json') or '{}'
        perfil = json.loads(perfil_json_str)
        text_map = {
            "locais": f"Local: {nome}. Tipo: {tipo}. Descrição: {perfil.get('descricao', 'N/A')}.",
            "jogador": f"O Jogador principal: {nome}. Raça: {perfil.get('raca', 'N/A')}. Ocupação: {perfil.get('ocupacao', 'N/A')}.",
        }
        text_content = text_map.get(table_name, f"Entidade: {nome}. Tipo: {tipo}. Detalhes: {perfil_json_str}")
        metadata = {"id_canonico": entity_details['id_canonico'], "tipo": table_name, "nome": nome, "subtipo": tipo}
        return text_content, metadata

    async def _update_neo4j_graph(self, entity_details, table_name, processed_args, function_name):
        """Atualiza o grafo Neo4j."""
        neo4j_label_map = {
            "locais": "Local", "jogador": "Jogador", "elementos_universais": "ElementoUniversal",
            "personagens": "Personagem", "faccoes": "Faccao",
        }
        base_label = neo4j_label_map.get(table_name)
        if not base_label: return

        node_properties = {k: v for k, v in entity_details.items() if isinstance(v, (str, int, float, bool))}
        self.neo4j_manager.add_or_update_node(
            id_canonico=entity_details['id_canonico'], label_base=base_label,
            properties=node_properties, main_label=entity_details.get('tipo', '').replace(" ", "")
        )

        if function_name == "add_or_get_location" and "parent_id_canonico" in processed_args:
            self.neo4j_manager.add_or_update_parent_child_relation(entity_details['id_canonico'], processed_args["parent_id_canonico"])
        elif function_name == "add_or_get_player" and "local_inicial_id_canonico" in processed_args:
            self.neo4j_manager.add_or_update_player_location_relation(entity_details['id_canonico'], processed_args["local_inicial_id_canonico"])
