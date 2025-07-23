import json
import asyncio
import inspect

from langchain_core.tools import BaseTool
from langchain.tools import tool

from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Processa chamadas de função, executa-as em sessões isoladas e sincroniza os pilares de dados.
    Versão: 3.0.0 - Unificado para usar descoberta automática de ferramentas, injeção de sessão e
                  sincronização de pilares (SQLite -> ChromaDB/Neo4j).
    """
    def __init__(self):
        """Inicializa o processador e descobre/prepara as ferramentas dos managers."""
        # Estas instâncias são usadas apenas para descobrir os métodos.
        # As instâncias reais para execução serão criadas sob demanda para cada sessão.
        dm_template = DataManager(session_name="template", supress_success_message=True)
        cm_template = ChromaDBManager(session_name="template")
        nm_template = Neo4jManager()
        
        self.managers_template = {
            "DataManager": dm_template,
            "ChromaDBManager": cm_template,
            "Neo4jManager": nm_template
        }
        
        # Mapeia quais funções de criação disparam uma sincronização
        self.sync_map = {
            "add_or_get_location": "locais",
            "add_or_get_player": "jogador",
            "add_or_get_element_universal": "elementos_universais",
            "add_or_get_personagem": "personagens",
            "add_or_get_faccao": "faccoes",
            "add_or_get_player_possession": "jogador_posses",
            "add_or_get_item": "itens" # Adicionando a criação de item à sincronização
        }
        
        self.tools = self._discover_and_wrap_tools()
        print(f"INFO: ToolProcessor (v3.0.0) inicializado com {len(self.tools)} ferramentas descobertas e prontas para sessão.")

    def get_tools(self) -> list[BaseTool]:
        """Retorna a lista de todas as ferramentas disponíveis e prontas para o LLM."""
        return self.tools
        
    async def process(self, tool_calls_from_llm: list) -> list:
        """
        Processa uma lista de chamadas de ferramentas, garantindo que uma resposta seja gerada para cada chamada.
        A lógica de sincronização é acionada aqui após a execução bem-sucedida de ferramentas mapeadas.
        """
        tool_responses = []
        
        for tc in tool_calls_from_llm:
            call = tc.get("functionCall") or {}
            func_name = call.get("name")
            args = call.get("args", {})
            
            # Validação básica da chamada da ferramenta
            if not func_name or not isinstance(args, dict):
                print(f"AVISO: Chamada de ferramenta malformada recebida: {tc}")
                continue

            # Busca a ferramenta na lista de ferramentas preparadas
            target_tool = next((t for t in self.tools if t.name == func_name), None)

            if target_tool:
                try:
                    # Executa a ferramenta. O wrapper interno cuidará da criação da instância do manager da sessão.
                    result = await target_tool.ainvoke(args)
                    function_response = result if result is not None else f"Ação '{func_name}' executada com sucesso."
                    
                    # --- LÓGICA DE SINCRONIZAÇÃO DE PILARES ---
                    if func_name in self.sync_map:
                        session_name = args.get("session_name")
                        # Determina o ID canônico a partir de possíveis nomes de argumento
                        id_canonico_to_sync = args.get("id_canonico") or args.get("posse_id_canonico")
                        
                        if session_name and id_canonico_to_sync:
                            print(f"SYNC TRIGGER: Função '{func_name}' acionou a sincronização para '{id_canonico_to_sync}' na sessão '{session_name}'.")
                            await self._sync_pillars_for_entity(
                                session_name,
                                id_canonico_to_sync,
                                self.sync_map[func_name],
                                args
                            )

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    function_response = f"ERRO ao executar a ferramenta '{func_name}': {e}"
            else:
                print(f"ERRO: A IA tentou chamar uma função desconhecida: '{func_name}'")
                function_response = f"ERRO: Função '{func_name}' não encontrada."
            
            tool_responses.append({
                "functionResponse": {
                    "name": func_name, 
                    "response": {"result": str(function_response)}
                }
            })

        return tool_responses

    async def _sync_pillars_for_entity(self, session_name: str, id_canonico: str, table_name: str, original_args: dict):
        """Sincroniza ChromaDB e Neo4j para uma entidade recém-criada ou atualizada no SQLite."""
        # Cria instâncias de manager específicas para esta sessão para garantir o isolamento dos dados
        dm = DataManager(session_name, supress_success_message=True)
        cm = ChromaDBManager(session_name)
        nm = self.managers_template['Neo4jManager'] # Neo4jManager já é session-aware internamente

        entity_details = dm.get_entity_details_by_canonical_id(table_name, id_canonico)
        if not entity_details:
            print(f"AVISO de SYNC: Não foi possível encontrar detalhes da entidade '{id_canonico}' na tabela '{table_name}' para sincronização.")
            return

        # 1. Sincronizar com ChromaDB (Base de Conhecimento Vetorial)
        text_content, metadata = self._prepare_chroma_data(entity_details, table_name)
        if text_content:
            cm.add_or_update_lore(id_canonico, text_content, metadata)

        # 2. Sincronizar com Neo4j (Grafo de Relações)
        await self._update_neo4j_graph(nm, session_name, entity_details, table_name, original_args)

    def _prepare_chroma_data(self, entity_details: dict, table_name: str) -> tuple[str, dict]:
        """Prepara os dados de uma entidade para serem vetorizados no ChromaDB."""
        id_canonico = entity_details.get('id_canonico')
        nome = entity_details.get('nome', entity_details.get('item_nome', 'N/A'))
        tipo = entity_details.get('tipo', 'genérico')
        perfil_json_str = entity_details.get('perfil_json') or entity_details.get('perfil_completo_json', '{}')
        
        text_content = f"Entidade: {nome} (ID: {id_canonico}). Categoria: {table_name}. Tipo específico: {tipo}. Detalhes: {perfil_json_str}"
        metadata = {
            "id_canonico": id_canonico, 
            "tipo_entidade": table_name, 
            "nome": nome, 
            "subtipo": tipo
        }
        
        # Sanitiza metadados: valores complexos (list, dict) devem ser strings JSON
        return text_content, {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in metadata.items()}

    async def _update_neo4j_graph(self, nm: Neo4jManager, session_name: str, entity_details: dict, table_name: str, original_args: dict):
        """Atualiza o grafo Neo4j com o novo nó e suas relações iniciais."""
        neo4j_label_map = {
            "locais": "Local", "jogador": "Jogador", "elementos_universais": "ElementoUniversal",
            "personagens": "Personagem", "faccoes": "Faccao", "itens": "Item", "jogador_posses": "Posse"
        }
        base_label = neo4j_label_map.get(table_name)
        if not base_label: return

        # Cria/Atualiza o nó
        node_properties = {k: v for k, v in entity_details.items() if isinstance(v, (str, int, float, bool))}
        labels = ["Entidade", base_label]
        if entity_details.get('tipo'):
            labels.append(entity_details['tipo'].replace(" ", "_"))
        
        nm.add_or_update_node(session_name, entity_details['id_canonico'], labels, node_properties)
        
        # Cria relações iniciais com base na função que foi chamada
        if "parent_id_canonico" in original_args and original_args["parent_id_canonico"]:
            nm.add_relationship(session_name, entity_details['id_canonico'], base_label, "DENTRO_DE", original_args["parent_id_canonico"], "Local")
        
        if "local_inicial_id_canonico" in original_args:
            nm.add_relationship(session_name, entity_details['id_canonico'], base_label, "ESTA_EM", original_args["local_inicial_id_canonico"], "Local")

    def _discover_and_wrap_tools(self) -> list[BaseTool]:
        """Descobre, envolve e retorna todas as ferramentas para operar com sessões."""
        wrapped_tools = []
        for manager_name, manager_instance in self.managers_template.items():
            for method_name, method in inspect.getmembers(manager_instance, inspect.isfunction):
                if not method_name.startswith("_"): # Ignora métodos privados
                    try:
                        # Envolve a função para adicionar 'session_name' e recriar o manager
                        wrapped_tool = self._create_wrapped_tool(manager_name, method_name, method)
                        # Adiciona o decorador @tool da Langchain
                        langchain_tool = tool(wrapped_tool)
                        wrapped_tools.append(langchain_tool)
                    except TypeError:
                        # Ignora métodos que não são adequados para serem ferramentas (ex: sem assinatura)
                        continue
        return wrapped_tools

    def _create_wrapped_tool(self, manager_name: str, method_name: str, original_method):
        """Cria uma função wrapper para uma ferramenta que aceita session_name."""
        sig = inspect.signature(original_method)
        original_params = list(sig.parameters.values())[1:] # Pula 'self'
        
        # Define a nova função dinamicamente
        async def wrapped_tool(session_name: str, **kwargs):
            # Recria a instância do manager para a sessão correta
            if manager_name == "DataManager":
                current_manager = DataManager(session_name, supress_success_message=True)
            elif manager_name == "ChromaDBManager":
                current_manager = ChromaDBManager(session_name)
            elif manager_name == "Neo4jManager":
                current_manager = self.managers_template["Neo4jManager"]
                # Adiciona session_name aos kwargs para os métodos do Neo4j que precisam dele
                kwargs['session_name'] = session_name
            else:
                raise TypeError(f"Tipo de manager desconhecido: {manager_name}")

            original_method_bound = getattr(current_manager, method_name)
            
            # Chama a função original, que pode ser síncrona ou assíncrona
            if asyncio.iscoroutinefunction(original_method_bound):
                return await original_method_bound(**kwargs)
            else:
                return original_method_bound(**kwargs)
        
        # Cria a nova assinatura da função
        new_params = [inspect.Parameter('session_name', inspect.Parameter.KEYWORD_ONLY, annotation=str, default=None)]
        for p in original_params:
            new_params.append(p.replace(kind=inspect.Parameter.KEYWORD_ONLY, default=p.default if p.default is not inspect.Parameter.empty else None))
        
        wrapped_tool.__name__ = original_method.__name__
        wrapped_tool.__doc__ = original_method.__doc__ or "Ferramenta para interagir com o estado do mundo."
        wrapped_tool.__signature__ = sig.replace(parameters=new_params, return_annotation=sig.return_annotation)
        
        return wrapped_tool
