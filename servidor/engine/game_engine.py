# servidor/engine/game_engine.py
import json
import traceback
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
from agents.world_agent import WorldAgent
from servidor.engine.tool_processor import ToolProcessor

class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno para uma sessão específica.
    Versão: 3.4.0 - Convertido para operações síncronas para compatibilidade com Flask.
    """
    def __init__(self, context_builder: ContextBuilder, tool_processor: ToolProcessor):
        self.context_builder = context_builder
        self.tool_processor = tool_processor
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()

        self.mj_llm_client = LLMClient(model_name=config.GENERATIVE_MODEL, tool_processor=self.tool_processor)
        self.world_llm_client = LLMClient(model_name=config.AGENT_GENERATIVE_MODEL, tool_processor=self.tool_processor)
        
        print(f"--- INSTÂNCIA PARA '{context_builder.data_manager.session_name}' PRONTA ---")

    def execute_turn(self, player_action: str):
        """Simula um único turno do jogo de forma síncrona."""
        try:
            print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
            context = self.context_builder.get_current_context()
            context_str = json.dumps(context, indent=4, ensure_ascii=False)

            print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
            mj_system_prompt, mj_user_prompt = self.mj_agent.format_prompt(context_str, player_action)
            
            # Chamada síncrona
            narrative, _ = self.mj_llm_client.call(
                system_prompt=mj_system_prompt,
                user_prompt=mj_user_prompt,
                tools=[] 
            )
            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

            if not narrative or "interferência cósmica" in narrative:
                return narrative

            print("\n\033[1;36m--- Agente Arquiteto do Mundo está a analisar... ---\033[0m")
            world_system_prompt, world_user_prompt = self.world_agent.format_prompt(narrative, context_str)
            world_agent_tools = self.tool_processor.get_tools()
            
            # Chamada síncrona
            analysis_and_plan_text, tool_calls = self.world_llm_client.call(
                system_prompt=world_system_prompt,
                user_prompt=world_user_prompt,
                tools=world_agent_tools
            )

            if analysis_and_plan_text:
                print("\n\033[1;34m--- Raciocínio do Arquiteto do Mundo ---\033[0m\n" + analysis_and_plan_text)
            
            if not tool_calls:
                print("--- Nenhuma ação estrutural foi necessária. ---")

            print("\033[1;32m--- Atualização do mundo concluída. ---\033[0m")
            return narrative
        except Exception as e:
            print(f"ERRO CRÍTICO NO TURNO: {e}")
            traceback.print_exc()
            return "O universo tremeu com um erro inesperado. O Mestre de Jogo precisa de um momento para se recompor."
