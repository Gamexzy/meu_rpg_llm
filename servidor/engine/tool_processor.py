import inspect
from functools import partial
from langchain_core.tools import BaseTool, StructuredTool
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 3.6.0 - Corrigida a execução da ferramenta para evitar o erro do argumento 'self'.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.data_manager = data_manager
        self.chromadb_manager = chromadb_manager
        self.neo4j_manager = neo4j_manager
        self.tools = self._discover_and_prepare_tools()
        self.tool_map = {t.name: t for t in self.tools}

    def _discover_and_prepare_tools(self):
        """Descobre todos os métodos marcados como '@tool' e prepara-os para a sessão."""
        discovered_tools = []
        managers = [self.data_manager, self.chromadb_manager, self.neo4j_manager]

        for manager in managers:
            for name, member in inspect.getmembers(manager):
                if isinstance(member, BaseTool):
                    if manager is self.neo4j_manager:
                        original_function = member.func
                        session_bound_function = partial(original_function, self.neo4j_manager, session_name=self.data_manager.session_name)
                        session_bound_function.__doc__ = original_function.__doc__
                        new_tool = StructuredTool.from_function(
                            func=session_bound_function,
                            name=member.name,
                            description=member.description,
                            args_schema=member.args_schema
                        )
                        discovered_tools.append(new_tool)
                    else:
                        discovered_tools.append(member)

        print(f"INFO: {len(discovered_tools)} ferramentas preparadas para o motor de jogo.")
        return discovered_tools

    def get_tools(self) -> list:
        """Retorna a lista de todas as ferramentas disponíveis para o LLM nesta sessão."""
        return self.tools

    def execute_tool(self, tool_name: str, tool_args: dict):
        """Encontra e executa uma ferramenta pelo nome com os argumentos fornecidos."""
        if tool_name in self.tool_map:
            print(f"\033[1;33m--- Executando Ferramenta: {tool_name} com args: {tool_args} ---\033[0m")
            try:
                # CORREÇÃO: Usamos o .invoke() que lida melhor com os argumentos do que o .run()
                result = self.tool_map[tool_name].invoke(tool_args)
                print(f"\033[1;32m--- Resultado: {result} ---\033[0m")
                return result
            except Exception as e:
                print(f"\033[1;31mERRO ao executar a ferramenta '{tool_name}': {e}\033[0m")
                return f"Erro ao executar a ferramenta: {e}"
        else:
            print(f"\033[1;31mERRO: Ferramenta '{tool_name}' não encontrada.\033[0m")
            return f"Ferramenta '{tool_name}' não encontrada."

