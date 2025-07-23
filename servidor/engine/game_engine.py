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
    Motor principal do jogo. Orquestra cada turno.
    Versão: 2.3.0 - Corrigida a inicialização do aiohttp.ClientSession para compatibilidade com Flask.
    """
    def __init__(self, context_builder: ContextBuilder, tool_processor: ToolProcessor):
        """
        Inicializa o motor do jogo com os componentes necessários.
        O LLMClient agora é criado dinamicamente a cada turno.
        """
        self.context_builder = context_builder
        self.tool_processor = tool_processor
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()
    
    async def execute_turn(self, player_action: str):
        """
        Simula um único turno do jogo de forma assíncrona.
        Cria a sessão de rede e o LLMClient dentro do loop de eventos.
        """
        # A sessão aiohttp e o LLMClient são criados aqui, dentro do contexto async.
        async with aiohttp.ClientSession() as session:
            llm_client = LLMClient(session, self.tool_processor)

            print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
            context = await self.context_builder.get_current_context()
            
            print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
            prompt_narrativa = self.mj_agent.format_prompt(context, player_action)
            
            # 1ª Chamada de IA: Gerar a narrativa do Mestre de Jogo.
            narrative, _ = await llm_client.call(
                config.GENERATIVE_MODEL, 
                prompt_narrativa, 
                self.mj_agent.get_tool_declarations()
            )
            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

            if not narrative or "interferência cósmica" in narrative:
                print("\033[1;31m--- Análise do mundo suspensa devido a um erro na geração da narrativa. ---\033[0m")
                return narrative

            print("\n\033[1;36m--- Agente Arquiteto do Mundo está a analisar e a planear... ---\033[0m")
            
            world_agent_prompt = self.world_agent.format_prompt(narrative, context)
            world_agent_tools = self.world_agent.get_tool_declarations()
            
            # 2ª Chamada de IA: O WorldAgent analisa a narrativa e executa as atualizações de estado.
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
