# servidor/engine/tool_processor.py
import inspect
import json
import traceback
from typing import List, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 5.4.0 - Corrigida a chamada da ferramenta para usar o método .invoke(), garantindo total compatibilidade com o LangChain.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.session_name = data_manager.session_name
        self.managers = {
            'data_manager': data_manager,
            'chromadb_manager': chromadb_manager,
            'neo4j_manager': neo4j_manager
        }
        
        self.tools: List[BaseTool] = []
        self.tool_map: Dict[str, BaseTool] = {} # Mapeia nome da ferramenta para o objeto da ferramenta
        self._discover_and_map_tools()

        print(f"INFO: {len(self.tools)} ferramentas preparadas para o motor de jogo.")

    def _discover_and_map_tools(self):
        """
        Descobre as ferramentas e mapeia cada nome de ferramenta ao seu objeto BaseTool.
        """
        for manager_instance in self.managers.values():
            for name, member in inspect.getmembers(manager_instance):
                if isinstance(member, BaseTool):
                    self.tools.append(member)
                    self.tool_map[member.name] = member

    def get_tools(self) -> List[BaseTool]:
        """Retorna a lista de ferramentas prontas para serem usadas pela IA."""
        return self.tools

    def execute_tool_calls(self, tool_calls: List[dict]):
        """
        Executa uma lista de chamadas de ferramentas solicitadas pela IA.
        """
        if not tool_calls:
            print("--- Nenhuma ação estrutural foi necessária. ---")
            return

        print(f"--- Arquiteto do Mundo solicitou {len(tool_calls)} ações. Executando... ---")
        for call in tool_calls:
            tool_name = call.get('name')
            tool_args = call.get('args', {})

            # Encontra o objeto da ferramenta que foi mapeado
            tool_to_execute = self.tool_map.get(tool_name)

            if tool_to_execute:
                sanitized_args = {}
                for key, value in tool_args.items():
                    if isinstance(value, str) and ('_data' in key or '_json' in key):
                        try:
                            sanitized_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            sanitized_args[key] = value
                    else:
                        sanitized_args[key] = value
                
                if tool_to_execute.args_schema and 'session_name' in tool_to_execute.args_schema.__fields__:
                    sanitized_args['session_name'] = self.session_name

                print(f"--- Executando Ferramenta: {tool_name} com args: {sanitized_args} ---")
                try:
                    # --- CORREÇÃO FINAL APLICADA AQUI ---
                    # Usamos .invoke() com o dicionário de argumentos. Esta é a forma correta
                    # e mais compatível de executar uma ferramenta LangChain.
                    result = tool_to_execute.invoke(sanitized_args)
                    print(f"--- Resultado: {result} ---")
                except Exception as e:
                    print(f"ERRO ao executar a ferramenta '{tool_name}': {e}")
                    traceback.print_exc()
            else:
                print(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")
