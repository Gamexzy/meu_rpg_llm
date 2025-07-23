import aiohttp
import json
from langchain_core.tools import BaseTool
from typing import List, Tuple
from config import config
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from servidor.engine.tool_processor import ToolProcessor

class LLMClient:
    """
    Cliente para interagir com a API do Google Gemini.
    Versão: 2.0.0 - Refatorado para usar um ToolProcessor externo para execução de ferramentas.
    """
    def __init__(self, session: aiohttp.ClientSession, tool_processor: ToolProcessor):
        self.session = session
        self.tool_processor = tool_processor # Recebe o processador da sessão

    async def call(self, model_name: str, prompt: str, tools: List[BaseTool] = None) -> Tuple[str, List[dict]]:
        """
        Envia um prompt para o modelo Gemini e retorna a resposta e as chamadas de função.
        """
        api_key = config.GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
                {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            ]
        }

        # Adiciona as ferramentas à requisição se elas existirem
        if tools:
            payload["tools"] = [{"function_declarations": [t.get_schema() for t in tools]}]

        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extrai o conteúdo e as chamadas de função da resposta
                    content = data.get("candidates", [{}])[0].get("content", {})
                    text_response = content.get("parts", [{}])[0].get("text", "")
                    function_calls = [part['functionCall'] for part in content.get("parts", []) if 'functionCall' in part]

                    # Se houver chamadas de função, executa-as
                    if function_calls:
                        print(f"INFO: LLM solicitou a execução de {len(function_calls)} ferramenta(s)...")
                        # O ToolProcessor já é da sessão correta, então não precisamos passar o session_name
                        for call in function_calls:
                            tool_name = call['name']
                            tool_args = call.get('args', {})
                            
                            # Encontra a ferramenta correta no processador e a executa
                            found_tool = next((t for t in self.tool_processor.get_tools() if t.name == tool_name), None)
                            if found_tool:
                                found_tool.run(tool_args)
                            else:
                                print(f"ERRO: Ferramenta '{tool_name}' solicitada pelo LLM mas não encontrada no ToolProcessor.")

                    return text_response, function_calls
                else:
                    error_text = await response.text()
                    print(f"Erro na API Gemini ({response.status}): {error_text}")
                    return "Houve uma interferência cósmica e a resposta se perdeu.", []
        except Exception as e:
            print(f"Exceção ao chamar a API Gemini: {e}")
            return "Houve uma interferência cósmica e a conexão falhou.", []
