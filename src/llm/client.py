# servidor/llm/client.py
import traceback
from typing import List, Tuple
from src import config
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI



class LLMClient:
    """
    Cliente para interagir com a API do Google Gemini, usando as abstrações do LangChain.
    Versão: 5.0.0 - Simplificado, removido o tool_processor que não era utilizado.
    """

    def __init__(self, model_name: str):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=config.GEMINI_API_KEY,
            convert_system_message_to_human=True,
        )
        print(f"INFO: LLMClient inicializado com o modelo: {model_name}")

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        history: List[BaseMessage] = None,
        tools: List[BaseTool] = None,
    ) -> Tuple[str, List[dict]]:
        """
        Envia um prompt para o modelo Gemini e retorna a resposta e as chamadas de função.
        """
        messages = [SystemMessage(content=system_prompt)]
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=user_prompt))

        llm_with_tools = self.llm
        if tools:
            llm_with_tools = self.llm.bind_tools(tools)

        try:
            response = llm_with_tools.invoke(messages)
            
            text_response = response.content if hasattr(response, 'content') else str(response)
            tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []

            return text_response, tool_calls

        except Exception as e:
            print(f"ERRO: Falha na chamada da API do LLM: {e}")
            traceback.print_exc()
            return f"Houve uma interferência cósmica e a resposta se perdeu. Erro: {e}", []
