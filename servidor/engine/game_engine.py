# servidor/engine/game_engine.py
import json
import traceback
import threading
import re
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
from agents.world_agent import WorldAgent
from servidor.engine.tool_processor import ToolProcessor
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Dict

class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno para uma sessão específica.
    Versão: 4.3.0 - Adicionado método para gerar ferramentas e corrigida a resposta do MJ.
    """
    def __init__(self, context_builder: ContextBuilder, tool_processor: ToolProcessor):
        self.context_builder = context_builder
        self.tool_processor = tool_processor
        self.mj_agent = MJAgent()
        self.world_agent = WorldAgent()

        self.mj_llm_client = LLMClient(model_name=config.GENERATIVE_MODEL)
        self.world_llm_client = LLMClient(model_name=config.AGENT_GENERATIVE_MODEL)
        
        self.chat_history = []
        self.HISTORY_MAX_TURNS = 5

        print(f"--- INSTÂNCIA PARA '{context_builder.data_manager.session_name}' PRONTA ---")

    def generate_contextual_tools(self) -> List[Dict[str, str]]:
        """
        Usa o MJAgent para gerar uma lista de ações contextuais ("ferramentas")
        com base no estado atual do jogo.
        """
        try:
            print("\n\033[1;36m--- Gerando ferramentas contextuais... ---\033[0m")
            context = self.context_builder.get_current_context()
            context_str = json.dumps(context, indent=2, ensure_ascii=False)

            tool_system_prompt, tool_user_prompt = self.mj_agent.format_prompt_for_tools(context_str)

            response_text, _ = self.mj_llm_client.call(
                system_prompt=tool_system_prompt,
                user_prompt=tool_user_prompt,
                history=[],
                tools=[]
            )

            print(f"\n\033[1;33m--- Resposta JSON do MJ para ferramentas: ---\033[0m\n{response_text}")

            # Extrai o JSON de dentro de ```json ... ``` se houver
            json_match = re.search(r'```json\s*(\[.*\])\s*```', response_text, re.DOTALL)
            if json_match:
                clean_json_str = json_match.group(1)
            else:
                # Se não houver ```, busca por um array JSON solto
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if not json_match:
                    print("\033[1;31mAVISO: Nenhuma lista JSON válida encontrada na resposta do MJ.\033[0m")
                    return []
                clean_json_str = json_match.group(0)
            
            tools = json.loads(clean_json_str)
            return tools

        except Exception as e:
            print(f"ERRO CRÍTICO AO GERAR FERRAMENTAS: {e}")
            traceback.print_exc()
            return []

    def _run_world_agent_in_background(self, narrative: str, context_str: str, history_snapshot: list):
        """
        Esta função é executada numa thread separada para não bloquear a resposta ao utilizador.
        """
        try:
            # Não executa o agente de mundo se a narrativa for um erro ou aviso
            if "O Mestre de Jogo parece confuso" in narrative or "O universo tremeu" in narrative:
                return
                
            print("\n\033[1;36m--- [BG] Agente Arquiteto do Mundo está a analisar... ---\033[0m")
            world_system_prompt, world_user_prompt = self.world_agent.format_prompt(narrative, context_str)
            world_agent_tools = self.tool_processor.get_tools()
            
            analysis_and_plan_text, tool_calls = self.world_llm_client.call(
                system_prompt=world_system_prompt,
                user_prompt=world_user_prompt,
                history=history_snapshot,
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
            
            # --- CORREÇÃO DE SEGURANÇA ---
            # Verifica se a resposta é um JSON de ferramentas por engano.
            if narrative.strip().startswith('[') and narrative.strip().endswith(']'):
                print(f"\033[1;31mERRO: MJ respondeu com JSON em vez de narrativa. Ação: '{player_action}'. Resposta: {narrative}\033[0m")
                narrative = "O Mestre de Jogo parece confuso com sua ação e pede um momento para organizar seus pensamentos. Por favor, tente outra ação."

            
            print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO (Enviando ao cliente) ---\033[0m\n" + narrative)

            history_snapshot = self.chat_history[:]
            
            background_thread = threading.Thread(
                target=self._run_world_agent_in_background,
                args=(narrative, context_str, history_snapshot)
            )
            background_thread.start()

            self.chat_history.append(HumanMessage(content=player_action))
            self.chat_history.append(AIMessage(content=narrative))
            if len(self.chat_history) > self.HISTORY_MAX_TURNS * 2:
                self.chat_history = self.chat_history[-(self.HISTORY_MAX_TURNS * 2):]

            return narrative
        except Exception as e:
            print(f"ERRO CRÍTICO NO TURNO: {e}")
            traceback.print_exc()
            return "O universo tremeu com um erro inesperado. O Mestre de Jogo precisa de um momento para se recompor."
