import aiohttp
from config import config
from servidor.engine.tool_processor import ToolProcessor

class LLMClient:
    """
    Cliente de API para interagir com o modelo Gemini.
    Versão: 1.1.0 - Adicionado modo 'single_shot' para forçar agentes a responderem de uma só vez.
    """
    def __init__(self, session: aiohttp.ClientSession, tool_processor: ToolProcessor):
        self.session = session
        self.tool_processor = tool_processor

    async def call(self, model_name, prompt, tools_declarations, chat_history_context=None, single_shot=False):
        """
        Envia um prompt para a API do LLM e lida com as chamadas de ferramentas.
        Se single_shot for True, processa todas as ferramentas de uma vez e não continua a conversa.
        """
        if chat_history_context is None:
            chat_history_context = [{"role": "user", "parts": [{"text": prompt}]}]

        payload = {"contents": chat_history_context, "tools": tools_declarations}
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={config.GEMINI_API_KEY}"

        try:
            async with self.session.post(api_url, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if not response.status == 200:
                    error_text = await response.text()
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {error_text}")
                    return f"Uma interferência cósmica impede a clareza. (Erro: {response.status})", {}
                
                result = await response.json()
                
                if not result.get("candidates") or not result["candidates"][0].get("content"):
                    return "O LLM parece estar em silêncio...", result

                parts = result["candidates"][0]["content"]["parts"]
                tool_calls = [part for part in parts if "functionCall" in part]

                # Se não houver chamadas de ferramentas, retorna o texto diretamente.
                if not tool_calls:
                    return (parts[0].get("text") or "").strip(), result

                # Processa TODAS as chamadas de ferramentas recebidas de uma vez.
                await self.tool_processor.process(tool_calls)
                
                # Se for um 'disparo único', o trabalho termina aqui. Não há mais conversa.
                if single_shot:
                    return "Agente executou as operações em lote.", result

                # Se não for disparo único (ex: MJ criando o mundo), continua a conversa.
                tool_responses = [{"functionResponse": {"name": tc["functionCall"]["name"], "response": {"status": "OK"}}} for tc in tool_calls]
                chat_history_context.append({"role": "model", "parts": tool_calls})
                chat_history_context.append({"role": "user", "parts": tool_responses})
                
                # Chama recursivamente para obter a resposta final em texto do LLM.
                return await self.call(model_name, prompt, tools_declarations, chat_history_context)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado.", {}
