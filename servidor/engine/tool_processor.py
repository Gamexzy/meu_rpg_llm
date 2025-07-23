import inspect
from langchain.tools import tool
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

class ToolProcessor:
    """
    Coleta e disponibiliza as ferramentas para uma sessão de jogo específica.
    Versão: 3.0.0 - Refatorado para ser específico da sessão, eliminando a necessidade de wrapping dinâmico.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        """
        Inicializa o processador de ferramentas com os managers da sessão atual.
        """
        self.data_manager = data_manager
        self.chromadb_manager = chromadb_manager
        self.neo4j_manager = neo4j_manager
        self.tools = self._discover_tools()

    def _discover_tools(self):
        """
        Descobre todos os métodos marcados como '@tool' nos managers da sessão.
        """
        discovered_tools = []
        # Adiciona a session_name aos métodos do Neo4j que precisam dela
        # Isso é um "binding" parcial, fixando o primeiro argumento.
        self.neo4j_manager.add_or_get_entity = tool(lambda **kwargs: Neo4jManager.add_or_get_entity(self.neo4j_manager, session_name=self.data_manager.session_name, **kwargs))
        self.neo4j_manager.add_relationship = tool(lambda **kwargs: Neo4jManager.add_relationship(self.neo4j_manager, session_name=self.data_manager.session_name, **kwargs))

        managers = [self.data_manager, self.chromadb_manager, self.neo4j_manager]
        
        for manager in managers:
            for name, method in inspect.getmembers(manager, inspect.ismethod):
                # A verificação agora é se o método é uma 'Tool' da Langchain
                if isinstance(method, tool):
                    discovered_tools.append(method)
        
        print(f"INFO: {len(discovered_tools)} ferramentas descobertas para a sessão '{self.data_manager.session_name}'.")
        return discovered_tools

    def get_tools(self):
        """Retorna a lista de todas as ferramentas disponíveis para o LLM nesta sessão."""
        return self.tools
