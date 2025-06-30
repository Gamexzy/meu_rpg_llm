import aiohttp
from config import config
from servidor.engine.tool_processor import ToolProcessor

class LLMClient:
    """
    Cliente de API para interagir com o modelo Gemini.
    Versão: 1.0.0
    """
    def __init__(self, session: aiohttp.ClientSession, tool_processor: ToolProcessor):
        self.session = session
        self.tool_processor = tool_processor

    async def call(self, model_name, prompt, tools_declarations, chat_history_context=None):
        """
        Envia um prompt para a API do LLM e lida com as chamadas de ferramentas.
        """
        if chat_history_context is None:
            chat_history_context = [{"role": "user", "parts": [{"text": prompt}]}]

        payload = {"contents": chat_history_context, "tools": tools_declarations}
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={config.GEMINI_API_KEY}"

        try:
            async with self.session.post(api_url, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if not response.status == 200:
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {await response.text()}")
                    return "Uma interferência cósmica impede a clareza.", {}
                
                result = await response.json()
                
                if not result.get("candidates") or not result["candidates"][0].get("content"):
                    return "O LLM parece estar em silêncio...", result

                parts = result["candidates"][0]["content"]["parts"]
                tool_calls = [part for part in parts if "functionCall" in part]

                if not tool_calls:
                    return (parts[0].get("text") or "").strip(), result

                tool_responses = await self.tool_processor.process(tool_calls)
                chat_history_context.append({"role": "model", "parts": tool_calls})
                chat_history_context.append({"role": "user", "parts": tool_responses})
                
                return await self.call(model_name, prompt, tools_declarations, chat_history_context)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado.", {}
