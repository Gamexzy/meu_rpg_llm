# servidor/engine/tool_processor.py
import inspect
import json
from functools import partial
from typing import List
from langchain_core.tools import BaseTool
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 4.1.0 - Adiciona pré-processamento de argumentos para converter strings JSON em dicionários.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.managers = {'data_manager': data_manager, 'chromadb_manager': chromadb_manager, 'neo4j_manager': neo4j_manager}
        self.tools = self._discover_tools()
        print(f"INFO: {len(self.tools)} ferramentas preparadas para o motor de jogo.")

    def _discover_tools(self) -> List[BaseTool]:
        """Descobre e retorna todas as ferramentas dos managers."""
        tools = []
        for manager in self.managers.values():
            for name, method in inspect.getmembers(manager, predicate=inspect.ismethod):
                if hasattr(method, "is_tool") and method.is_tool:
                    tools.append(method.tool_instance)
        return tools

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
            
            # Encontra a ferramenta correspondente na lista
            tool_to_execute = next((t for t in self.tools if t.name == tool_name), None)

            if tool_to_execute:
                # --- LÓGICA DE CORREÇÃO E LIMPEZA DOS ARGUMENTOS ---
                sanitized_args = {}
                for key, value in tool_args.items():
                    # 1. Ignora o argumento 'self' se a IA o enviar por engano
                    if key == 'self':
                        continue
                    # 2. Converte strings que parecem JSON em dicionários
                    if isinstance(value, str) and ('_data' in key or '_json' in key):
                        try:
                            sanitized_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            print(f"AVISO: Não foi possível converter o argumento '{key}' para JSON. Usando como string.")
                            sanitized_args[key] = value
                    else:
                        sanitized_args[key] = value
                # --- FIM DA LÓGICA DE CORREÇÃO ---
                
                print(f"--- Executando Ferramenta: {tool_name} com args: {sanitized_args} ---")
                try:
                    # Executa a ferramenta com os argumentos limpos
                    result = tool_to_execute.invoke(sanitized_args)
                    print(f"--- Resultado: {result} ---")
                except Exception as e:
                    print(f"ERRO ao executar a ferramenta '{tool_name}': {e}")
            else:
                print(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")
