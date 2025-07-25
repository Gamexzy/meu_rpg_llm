# servidor/engine/game_engine.py
import json
import traceback
import threading  # Importa a biblioteca de threading
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
from agents.world_agent import WorldAgent
from servidor.engine.tool_processor import ToolProcessor
from langchain_core.messages import HumanMessage, AIMessage

class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno para uma sessão específica.
    Versão: 4.0.0 - A atualização do World Agent agora é executada em segundo plano (assíncrona).
    """
    def __init__(self, context_builder: ContextBuilder, tool_processor: ToolProcessor):
        self.context_builder = context_builder
        self.tool_processor = tool_processor
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()

        self.mj_llm_client = LLMClient(model_name=config.GENERATIVE_MODEL, tool_processor=self.tool_processor)
        self.world_llm_client = LLMClient(model_name=config.AGENT_GENERATIVE_MODEL, tool_processor=self.tool_processor)
        
        self.chat_history = []
        self.HISTORY_MAX_TURNS = 5

        print(f"--- INSTÂNCIA PARA '{context_builder.data_manager.session_name}' PRONTA ---")

    def _run_world_agent_in_background(self, narrative: str, context_str: str):
        """
        Esta função é executada numa thread separada para não bloquear a resposta ao utilizador.
        """
        try:
            print("\n\033[1;36m--- [BG] Agente Arquiteto do Mundo está a analisar... ---\033[0m")
            world_system_prompt, world_user_prompt = self.world_agent.format_prompt(narrative, context_str)
            world_agent_tools = self.tool_processor.get_tools()
            
            analysis_and_plan_text, tool_calls = self.world_llm_client.call(
                system_prompt=world_system_prompt,
                user_prompt=world_user_prompt,
                history=self.chat_history,
                tools=world_agent_tools
            )

            if analysis_and_plan_text:
                print("\n\033[1;34m--- [BG] Raciocínio do Arquiteto do Mundo ---\033[0m\n" + analysis_and_plan_text)
            
            self.tool_processor.execute_tool_calls(tool_calls)

            print("\033[1;32m--- [BG] Atualização do mundo concluída. ---\033[0m")
        except Exception as e:
            print(f"ERRO CRÍTICO NA THREAD DE BACKGROUND: {e}")
            traceback.print_exc()

    def execute_turn(self, player_action: str) -> str:
        """
        Simula um turno do jogo. A narração é retornada imediatamente,
        e a atualização do estado do mundo é feita em segundo plano.
        """
        try:
            print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
            context = self.context_builder.get_current_context()
            context_str = json.dumps(context, indent=4, ensure_ascii=False)

            print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
            mj_system_prompt, mj_user_prompt = self.mj_agent.format_prompt(context_str, player_action)
            
            narrative, _ = self.mj_llm_client.call(
                system_prompt=mj_system_prompt,
                user_prompt=mj_user_prompt,
                history=self.chat_history,
                tools=[] 
            )
            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO (Enviando ao cliente) ---\033[0m\n" + narrative)

            # Atualiza o histórico para que a thread de background possa usá-lo
            self.chat_history.append(HumanMessage(content=player_action))
            self.chat_history.append(AIMessage(content=narrative))
            if len(self.chat_history) > self.HISTORY_MAX_TURNS * 2:
                self.chat_history = self.chat_history[-(self.HISTORY_MAX_TURNS * 2):]

            if not narrative or "interferência cósmica" in narrative:
                return narrative

            # --- INICIA A ATUALIZAÇÃO DO MUNDO EM SEGUNDO PLANO ---
            world_agent_thread = threading.Thread(
                target=self._run_world_agent_in_background,
                args=(narrative, context_str)
            )
            world_agent_thread.start()
            
            # Retorna a narrativa imediatamente para o cliente
            return narrative
            
        except Exception as e:
            print(f"ERRO CRÍTICO NO TURNO: {e}")
            traceback.print_exc()
            return "O universo tremeu com um erro inesperado. O Mestre de Jogo precisa de um momento para se recompor."
