import asyncio
import aiohttp
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
from agents.world_agent import WorldAgent
from servidor.engine.tool_processor import ToolProcessor

class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno para uma sessão específica.
    Versão: 3.1.0 - Passa o ToolProcessor da sessão para o LLMClient.
    """
    def __init__(self, context_builder: ContextBuilder, tool_processor: ToolProcessor):
        self.context_builder = context_builder
        self.tool_processor = tool_processor
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()
    
    async def execute_turn(self, player_action: str):
        """Simula um único turno do jogo de forma assíncrona."""
        async with aiohttp.ClientSession() as session:
            # O LLMClient agora recebe o tool_processor da sessão
            llm_client = LLMClient(session, self.tool_processor)

            print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
            context = await self.context_builder.get_current_context()
            
            print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
            prompt_narrativa = self.mj_agent.format_prompt(context, player_action)
            
            narrative, _ = await llm_client.call(
                config.GENERATIVE_MODEL, 
                prompt_narrativa, 
                self.mj_agent.get_tool_declarations()
            )
            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

            if not narrative or "interferência cósmica" in narrative:
                return narrative

            print("\n\033[1;36m--- Agente Arquiteto do Mundo está a analisar... ---\033[0m")
            
            world_agent_prompt = self.world_agent.format_prompt(
                narrative=narrative,
                context=context
            )
            world_agent_tools = self.tool_processor.get_tools()
            
            analysis_and_plan_text, _ = await llm_client.call(
                config.AGENT_GENERATIVE_MODEL,
                world_agent_prompt,
                world_agent_tools
            )

            if analysis_and_plan_text:
                print("\n\033[1;34m--- Raciocínio do Arquiteto do Mundo ---\033[0m")
                print(analysis_and_plan_text)
            
            print("\033[1;32m--- Atualização do mundo concluída. ---\033[0m")
            return narrative
