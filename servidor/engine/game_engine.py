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
    Versão: 4.0.0 - Unificado para operar com sessões. Armazena o nome da sessão
                  e o passa para todos os componentes relevantes (ContextBuilder, WorldAgent).
    """
    def __init__(self, session_name: str):
        """
        Inicializa o motor do jogo para uma sessão específica.
        Os componentes (ContextBuilder, ToolProcessor, Agentes) são criados aqui.

        Args:
            session_name (str): O identificador único para a sessão de jogo atual.
        """
        self.session_name = session_name
        self.context_builder = ContextBuilder(session_name)
        self.tool_processor = ToolProcessor()
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()
        print(f"INFO: GameEngine (v4.0.0) inicializado para a sessão '{self.session_name}'.")
    
    async def execute_turn(self, player_action: str) -> str:
        """
        Executa um único turno do jogo de forma assíncrona, garantindo o isolamento da sessão.
        """
        # A sessão aiohttp e o LLMClient são criados dinamicamente a cada turno.
        async with aiohttp.ClientSession() as session:
            llm_client = LLMClient(session, self.tool_processor)

            # 1. Obter Contexto (Específico da Sessão)
            print(f"\n\033[1;36m--- Obtendo contexto para o turno na sessão '{self.session_name}'... ---\033[0m")
            context = await self.context_builder.get_current_context()
            
            # 2. Gerar Narrativa do Mestre de Jogo
            print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
            prompt_narrativa = self.mj_agent.format_prompt(context, player_action)
            
            narrative, _ = await llm_client.call(
                config.GENERATIVE_MODEL, 
                prompt_narrativa, 
                self.mj_agent.get_tool_declarations()
            )
            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

            if not narrative or "interferência cósmica" in narrative:
                print("\033[1;31m--- Análise do mundo suspensa devido a um erro na geração da narrativa. ---\033[0m")
                return narrative

            # 3. Analisar e Atualizar o Estado do Mundo (Específico da Sessão)
            print("\n\033[1;36m--- Agente Arquiteto do Mundo está a analisar e a planear... ---\033[0m")
            
            # O session_name é passado para o prompt do WorldAgent, que o incluirá em todas as chamadas de ferramenta.
            world_agent_prompt = self.world_agent.format_prompt(
                session_name=self.session_name,
                narrative=narrative,
                context=context
            )
            world_agent_tools = self.tool_processor.get_tools()
            
            # O WorldAgent analisa a narrativa e o ToolProcessor executa as atualizações de estado.
            analysis_and_plan_text, _ = await llm_client.call(
                config.AGENT_GENERATIVE_MODEL,
                world_agent_prompt,
                world_agent_tools
            )

            if analysis_and_plan_text:
                print("\n\033[1;34m--- Raciocínio do Arquiteto do Mundo ---\033[0m")
                print(analysis_and_plan_text)
            
            print(f"\033[1;32m--- Atualização do mundo para a sessão '{self.session_name}' concluída. ---\033[0m")
            return narrative
