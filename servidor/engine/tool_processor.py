# servidor/engine/tool_processor.py
import inspect
import json
import traceback
from typing import List, Dict, Tuple
from langchain_core.tools import BaseTool
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 7.0.0 - Refatorado para máxima compatibilidade, garantindo que o contexto 'self' seja sempre preservado.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.session_name = data_manager.session_name
        self.managers = {
            'data_manager': data_manager,
            'chromadb_manager': chromadb_manager,
            'neo4j_manager': neo4j_manager
        }
        
        self.tools: List[BaseTool] = []
        # Mapeia o nome da ferramenta para uma tupla (objeto da ferramenta, instância do gestor)
        self.tool_map: Dict[str, Tuple[BaseTool, object]] = {}
        self._discover_and_map_tools()

        print(f"INFO: {len(self.tools)} ferramentas preparadas para o motor de jogo.")

    def _discover_and_map_tools(self):
        """
        Descobre as ferramentas e mapeia cada nome de ferramenta ao seu objeto BaseTool
        e à instância do gestor a que pertence.
        """
        for manager_name, manager_instance in self.managers.items():
            for name, member in inspect.getmembers(manager_instance):
                if isinstance(member, BaseTool):
                    self.tools.append(member)
                    # Guarda a ferramenta E a instância do seu gestor
                    self.tool_map[member.name] = (member, manager_instance)

    def get_tools(self) -> List[BaseTool]:
        """Retorna a lista de ferramentas prontas para serem usadas pela IA."""
        return self.tools

    def execute_tool_calls(self, tool_calls: List[dict]):
        """
        Executa uma lista de chamadas de ferramentas, garantindo que o contexto 'self'
        da instância do gestor seja corretamente passado para o método.
        """
        if not tool_calls:
            print("--- Nenhuma ação estrutural foi necessária. ---")
            return

        print(f"--- Arquiteto do Mundo solicitou {len(tool_calls)} ações. Executando... ---")
        for call in tool_calls:
            tool_name = call.get('name')
            tool_args = call.get('args', {})

            # Obtém a tupla (ferramenta, instância do gestor)
            tool_info = self.tool_map.get(tool_name)

            if tool_info:
                tool_object, manager_instance = tool_info
                
                sanitized_args = {}
                for key, value in tool_args.items():
                    if isinstance(value, str) and ('_data' in key or '_json' in key):
                        try:
                            sanitized_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            sanitized_args[key] = value
                    else:
                        sanitized_args[key] = value
                
                # Injeta o nome da sessão se a ferramenta o exigir
                if tool_object.args_schema and 'session_name' in tool_object.args_schema.__fields__:
                    sanitized_args['session_name'] = self.session_name

                print(f"--- Executando Ferramenta: {tool_name} com args: {sanitized_args} ---")
                try:
                    # --- CORREÇÃO FINAL APLICADA AQUI ---
                    # Pega o método real a partir da instância do gestor usando o nome da ferramenta
                    method_to_call = getattr(manager_instance, tool_name)
                    # Chama o método diretamente na instância, o que passa 'self' implicitamente
                    result = method_to_call(**sanitized_args)
                    print(f"--- Resultado: {result} ---")
                except Exception as e:
                    print(f"ERRO ao executar a ferramenta '{tool_name}': {e}")
                    traceback.print_exc()
            else:
                print(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")
