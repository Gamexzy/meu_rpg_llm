import aiohttp
from config import config
from servidor.engine.tool_processor import ToolProcessor

class LLMClient:
    """
    Cliente de API para interagir com o modelo Gemini.
    Versão: 1.1.0 - Corrigido o ciclo de chamada de ferramenta para não reenviar as declarações na chamada recursiva.
    """
    def __init__(self, session: aiohttp.ClientSession, tool_processor: ToolProcessor):
        self.session = session
        self.tool_processor = tool_processor

    async def call(self, model_name, prompt, tools_declarations=None, chat_history_context=None):
        """
        Envia um prompt para a API do LLM e lida com as chamadas de ferramentas.
        A declaração de ferramentas só é enviada na primeira chamada do ciclo.
        """
        if chat_history_context is None:
            # Se não houver histórico, começa um novo com o prompt inicial.
            chat_history_context = [{"role": "user", "parts": [{"text": prompt}]}]

        # Monta o payload base com o conteúdo (histórico)
        payload = {"contents": chat_history_context}
        
        # Adiciona as ferramentas ao payload APENAS se elas forem fornecidas (na primeira chamada)
        if tools_declarations:
            payload["tools"] = tools_declarations

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={config.GEMINI_API_KEY}"

        try:
            async with self.session.post(api_url, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if not response.status == 200:
                    error_text = await response.text()
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {error_text}")
                    # Retorna a mensagem de erro da API se disponível, para melhor depuração
                    return f"Uma interferência cósmica impede a clareza. Erro da API: {error_text}", {}
                
                result = await response.json()
                
                # Verifica se a resposta do candidato está vazia ou malformada
                if not result.get("candidates") or not result["candidates"][0].get("content"):
                    # Se houver um prompt de bloqueio, a razão estará em 'promptFeedback'
                    feedback = result.get("promptFeedback", {})
                    block_reason = feedback.get("blockReason", "desconhecida")
                    if block_reason != "SAFETY":
                        print(f"AVISO: A resposta do LLM estava vazia. Verifique a resposta completa: {result}")
                    return f"O LLM parece estar em silêncio... (Razão do bloqueio: {block_reason})", result

                parts = result["candidates"][0]["content"]["parts"]
                tool_calls = [part for part in parts if "functionCall" in part]

                # Se não houver chamadas de ferramenta, a conversa terminou. Retorna o texto.
                if not tool_calls:
                    return (parts[0].get("text") or "").strip(), result

                # Se houver chamadas de ferramenta, processa-as.
                print(f"INFO: LLM solicitou a execução de {len(tool_calls)} ferramenta(s)...")
                tool_responses = await self.tool_processor.process(tool_calls)
                
                # Adiciona o turno da IA (com as chamadas de ferramenta) e o nosso turno (com os resultados) ao histórico
                chat_history_context.append({"role": "model", "parts": tool_calls})
                chat_history_context.append({"role": "user", "parts": tool_responses})
                
                # Chama recursivamente a função, mas desta vez SEM as declarações de ferramentas.
                # O prompt original não é mais necessário, pois o histórico contém toda a conversa.
                return await self.call(model_name, prompt=None, tools_declarations=None, chat_history_context=chat_history_context)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Uma interferência cósmica impede a clareza. Erro interno: {e}", {}

"""
### Resumo da Correção

1.  **Parâmetro Opcional:** O parâmetro `tools_declarations` na função `call` agora é opcional.
2.  **Payload Condicional:** A chave `"tools"` só é adicionada ao `payload` da requisição se `tools_declarations` for fornecido.
3.  **Chamada Recursiva Limpa:** Na chamada recursiva, `tools_declarations` é explicitamente passado como `None`, garantindo que a lista de ferramentas não seja enviada novamente.
4.  **Melhoria nos Logs de Erro:** Adicionei uma depuração melhor para quando a API retorna um erro ou uma resposta vazia, o que ajudará a identificar problemas futuros mais rapidamente.

Com esta alteração, o ciclo de chamada de ferramentas seguirá o fluxo correto esperado pela API do Gemini, e o erro 400 não deve mais ocorr
"""
