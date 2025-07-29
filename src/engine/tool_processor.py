# servidor/engine/tool_processor.py
import inspect
import json
import traceback
import logging
from typing import List, Dict, Tuple
from langchain_core.tools import BaseTool
from src.database.sqlite_manager import SqliteManager
from src.database.chromadb_manager import ChromaDBManager
from src.database.neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 8.1.0 - Corrigida a chamada da função da ferramenta para injetar 'self' manualmente.
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

        logger.info(f"{len(self.tool_map)} ferramentas preparadas para o motor de jogo da sessão '{self.session_name}'.")

    def _discover_and_map_tools(self):
        """
        Descobre as ferramentas e mapeia cada nome de ferramenta ao seu objeto BaseTool
        e à instância do gestor a que pertence.
        """
        for manager_name, manager_instance in self.managers.items():
            for name, member in inspect.getmembers(manager_instance):
                if isinstance(member, BaseTool):
                    self.tools.append(member)
                    self.tool_map[member.name] = (member, manager_instance)

    def get_tools(self) -> List[BaseTool]:
        """Retorna a lista de ferramentas prontas para serem usadas pela IA."""
        return self.tools

    def execute_tool_calls(self, tool_calls: List[dict]):
        """
        Executa uma lista de chamadas de ferramentas, garantindo o contexto correto e a validação de tipos.
        """
        if not tool_calls:
            logger.info("--- Nenhuma ação estrutural foi necessária. ---")
            return

        logger.info(f"--- Arquiteto do Mundo solicitou {len(tool_calls)} ações. Executando... ---")
        for call in tool_calls:
            tool_name = call.get('name')
            tool_args = call.get('args', {})

            tool_info = self.tool_map.get(tool_name)

            if tool_info:
                tool_object, manager_instance = tool_info
                
                sanitized_args = {}
                for key, value in tool_args.items():
                    if isinstance(value, str) and ('_data' in key or '_json' in key or 'properties' in key):
                        try:
                            sanitized_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            sanitized_args[key] = value
                    else:
                        sanitized_args[key] = value
                
                if tool_object.args_schema and 'session_name' in tool_object.args_schema.__fields__:
                    sanitized_args['session_name'] = self.session_name

                logger.info(f"--- Executando Ferramenta: {tool_name} com args: {sanitized_args} ---")
                try:
                    # --- CORREÇÃO DEFINITIVA ---
                    # O `tool_object.func` contém a função original (ex: SqliteManager.add_or_get_location).
                    # Chamamos essa função, passando a `manager_instance` como o primeiro argumento (`self`),
                    # e depois desempacotamos o resto dos argumentos.
                    result = tool_object.func(manager_instance, **sanitized_args)
                    
                    logger.info(f"--- Resultado: {result} ---")
                except Exception as e:
                    logger.error(f"ERRO ao executar a ferramenta '{tool_name}': {e}", exc_info=True)
            else:
                logger.warning(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")
