# servidor/engine/tool_processor.py
import inspect
import logging
import sqlite3
from typing import List, Dict, Tuple
from langchain_core.tools import BaseTool, Tool
from src.database.sqlite_manager import SqliteManager
from src.database.chromadb_manager import ChromaDBManager
from src.database.neo4j_manager import Neo4jManager
from src import config

logger = logging.getLogger(__name__)

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 9.0.0 - Adicionada ferramenta set_saga_summary para modificar o DB central.
    """
    def __init__(self, data_manager: SqliteManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.session_name = data_manager.session_name
        self.managers = {
            'data_manager': data_manager,
            'chromadb_manager': chromadb_manager,
            'neo4j_manager': neo4j_manager
        }
        
        self.tools: List[BaseTool] = []
        self.tool_map: Dict[str, Tuple[BaseTool, object]] = {}
        self._discover_and_map_tools()

        # Adiciona a ferramenta de resumo manualmente
        summary_tool = Tool(
            name="set_saga_summary",
            func=self.set_saga_summary,
            description="Define ou atualiza o resumo da saga, que aparece nos cartões de aventura do aplicativo."
        )
        self.tools.append(summary_tool)
        self.tool_map[summary_tool.name] = (summary_tool, self)

        logger.info(f"{len(self.tool_map)} ferramentas preparadas para o motor de jogo da sessão '{self.session_name}'.")

    def set_saga_summary(self, summary: str) -> str:
        """Atualiza o resumo da saga no banco de dados central."""
        conn = None
        try:
            conn = sqlite3.connect(config.DB_PATH_CENTRAL)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sagas SET summary = ? WHERE session_name = ?",
                (summary, self.session_name),
            )
            conn.commit()
            msg = f"Resumo da saga '{self.session_name}' atualizado para: '{summary}'"
            logger.info(msg)
            return msg
        except Exception as e:
            msg = f"Erro ao atualizar o resumo da saga '{self.session_name}': {e}"
            logger.error(msg, exc_info=True)
            return msg
        finally:
            if conn:
                conn.close()

    def _discover_and_map_tools(self):
        """Descobre as ferramentas e mapeia cada nome de ferramenta ao seu objeto BaseTool e à instância do gestor a que pertence."""
        for manager_name, manager_instance in self.managers.items():
            for name, member in inspect.getmembers(manager_instance):
                if isinstance(member, BaseTool):
                    self.tools.append(member)
                    self.tool_map[member.name] = (member, manager_instance)

    def get_tools(self) -> List[BaseTool]:
        """Retorna a lista de ferramentas prontas para serem usadas pela IA."""
        return self.tools

    def execute_tool_calls(self, tool_calls: List[dict]):
        """Executa uma lista de chamadas de ferramentas."""
        if not tool_calls:
            logger.info("--- Nenhuma ação estrutural foi necessária. ---")
            return

        logger.info(f"--- Arquiteto do Mundo solicitou {len(tool_calls)} ações. Executando... ---")
        for call in tool_calls:
            tool_name = call.get('name')
            tool_args = call.get('args', {})

            tool_info = self.tool_map.get(tool_name)

            if tool_info:
                tool_object, instance = tool_info
                
                logger.info(f"--- Executando Ferramenta: {tool_name} com args: {tool_args} ---")
                try:
                    # A chamada agora funciona para ambos os tipos de ferramentas
                    # Se a instância for o próprio ToolProcessor (self), ele se chama.
                    # Se for um manager, ele chama o método do manager.
                    if hasattr(tool_object, 'func'):
                        # Para BaseTools que são métodos de classes (maioria)
                        if inspect.ismethod(tool_object.func):
                             result = tool_object.func(**tool_args)
                        # Para a nossa ferramenta manual `set_saga_summary`
                        else:
                             result = tool_object.func(instance, **tool_args)
                    else:
                        result = tool_object(tool_args)

                    logger.info(f"--- Resultado: {result} ---")
                except Exception as e:
                    logger.error(f"ERRO ao executar a ferramenta '{tool_name}': {e}", exc_info=True)
            else:
                logger.warning(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")
