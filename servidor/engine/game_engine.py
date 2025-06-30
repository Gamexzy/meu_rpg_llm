import asyncio
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
from agents.sqlite_agent import SQLiteAgent
from agents.chromadb_agent import ChromaDBAgent
from agents.neo4j_agent import Neo4jAgent

class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno.
    Versão: 1.0.0
    """
    def __init__(self, context_builder: ContextBuilder, llm_client: LLMClient):
        self.context_builder = context_builder
        self.llm_client = llm_client
        self.mj_agent = MJAgent()
        self.sqlite_agent = SQLiteAgent()
        self.chromadb_agent = ChromaDBAgent()
        self.neo4j_agent = Neo4jAgent()
    
    async def execute_turn(self, player_action: str):
        """Simula um único turno do jogo de forma assíncrona."""
        print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
        context = await self.context_builder.get_current_context()
        
        print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
        prompt_narrativa = self.mj_agent.format_prompt(context, player_action)
        narrative, _ = await self.llm_client.call(
            config.GENERATIVE_MODEL, prompt_narrativa, self.mj_agent.get_tool_declarations()
        )
        
        print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

        if not narrative or "interferência cósmica" in narrative:
            print("\033[1;31m--- Análise do mundo suspensa devido a um erro na geração da narrativa. ---\033[0m")
            return narrative

        print("\n\033[1;36m--- Agentes de IA estão a analisar a narrativa para atualizar o mundo... ---\033[0m")
        
        analysis_tasks = [
            self.llm_client.call(config.AGENT_GENERATIVE_MODEL, self.sqlite_agent.format_prompt(narrative, context), self.sqlite_agent.get_tool_declarations()),
            self.llm_client.call(config.AGENT_GENERATIVE_MODEL, self.chromadb_agent.format_prompt(narrative, context), self.chromadb_agent.get_tool_declarations()),
            self.llm_client.call(config.AGENT_GENERATIVE_MODEL, self.neo4j_agent.format_prompt(narrative, context), self.neo4j_agent.get_tool_declarations()),
        ]
        await asyncio.gather(*analysis_tasks)
        
        print("\033[1;32m--- Atualização do mundo concluída. ---\033[0m")
        return narrative
