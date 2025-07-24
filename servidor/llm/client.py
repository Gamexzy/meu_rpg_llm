# servidor/llm/client.py
import traceback
from typing import List, Tuple

from config import config
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI


class LLMClient:
    """
    Cliente para interagir com a API do Google Gemini de forma síncrona, usando as abstrações do LangChain.
    Versão: 4.0.0 - Refatorado para usar llm.bind_tools() para uma vinculação de ferramentas robusta.
    """

    def __init__(self, model_name: str, tool_processor):
        self.tool_processor = tool_processor # Mantido para referência futura, se necessário
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=config.GEMINI_API_KEY,
            convert_system_message_to_human=True,
        )
        print(f"INFO: LLMClient inicializado com o modelo: {model_name}")

    def call(
        self, system_prompt: str, user_prompt: str, tools: List[BaseTool] = None
    ) -> Tuple[str, List[dict]]:
        """
        Envia um prompt para o modelo Gemini e retorna a resposta e as chamadas de função.
        """
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        llm_with_tools = self.llm

        if tools:
            # CORREÇÃO: Usa o método .bind_tools() que lida com toda a conversão internamente.
            llm_with_tools = self.llm.bind_tools(tools)

        try:
            # Usa .invoke() para chamada síncrona
            response = llm_with_tools.invoke(messages)
            
            text_response = response.content
            function_calls = response.tool_calls

            if function_calls:
                # A execução agora é responsabilidade do GameEngine, mas a chamada está aqui por completude
                self.tool_processor.execute_tool_calls(function_calls)

            return text_response, function_calls

        except Exception as e:
            print(f"ERRO: Falha na chamada da API do LLM: {e}")
            # Descomente a linha abaixo para ver o traceback completo em caso de erros difíceis
            # traceback.print_exc() 
            return f"Houve uma interferência cósmica e a resposta se perdeu. Erro: {e}", []
