# servidor/engine/tool_processor.py
import inspect
import json
import traceback
import logging # Adicionar import de logging
from typing import List, Dict, Tuple
from langchain_core.tools import BaseTool
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager
from servidor.data_managers.neo4j_manager import Neo4jManager

# Obter um logger para este módulo
logger = logging.getLogger(__name__)

class ToolProcessor:
    """
    Coleta, prepara e executa as ferramentas para uma sessão de jogo específica.
    Versão: 7.1.0 - Corrigido o método de chamada da ferramenta para usar .invoke() em vez de desempacotamento de kwargs.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager, neo4j_manager: Neo4jManager):
        self.session_name = data_manager.session_name
        self.managers = {
            'data_manager': data_manager,
            'chromadb_manager': chromadb_manager,
            'neo4j_manager': neo4j_manager
        }
        
        self.tools: List[BaseTool] = []
        self.tool_map: Dict[str, Tuple[BaseTool, object]] = {}
        self._discover_and_map_tools()

        logger.info(f"{len(self.tools)} ferramentas preparadas para o motor de jogo da sessão '{self.session_name}'.")

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
        Executa uma lista de chamadas de ferramentas usando o método .invoke().
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
                
                # O Langchain espera que os argumentos de dados JSON sejam strings, não dicionários.
                # Vamos garantir que eles sejam convertidos para string JSON antes de invocar.
                args_for_invocation = {}
                for key, value in tool_args.items():
                    if isinstance(value, dict):
                        args_for_invocation[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        args_for_invocation[key] = value
                
                if tool_object.args_schema and 'session_name' in tool_object.args_schema.__fields__:
                    args_for_invocation['session_name'] = self.session_name

                logger.info(f"--- Executando Ferramenta: {tool_name} com args: {args_for_invocation} ---")
                try:
                    # --- CORREÇÃO PRINCIPAL APLICADA AQUI ---
                    # Usamos o método .invoke() da ferramenta, passando um único dicionário de argumentos.
                    result = tool_object.invoke(args_for_invocation)
                    logger.info(f"--- Resultado: {result} ---")
                except Exception as e:
                    logger.error(f"ERRO ao executar a ferramenta '{tool_name}': {e}", exc_info=True)
            else:
                logger.warning(f"AVISO: Ferramenta '{tool_name}' solicitada pela IA, mas não encontrada.")

