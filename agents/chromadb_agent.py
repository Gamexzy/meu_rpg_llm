import json
from config import config

class ChromaDBAgent:
    """
    Agente especializado em analisar a narrativa do Mestre de Jogo (MJ)
    e CONSOLIDAR informações relevantes para serem armazenadas no ChromaDB.
    Versão: 1.2.0 - O agente agora é instruído a realizar até 5 operações de consolidação em lote.
    """
    def __init__(self):
        """
        Inicializa o agente do ChromaDB.
        """
        print("INFO: ChromaDBAgent (Consolidador em Lote) inicializado (v1.2.0).")

    def get_tool_declarations(self):
        """
        Retorna a declaração de ferramentas que este agente pode usar.
        """
        return [{
            "functionDeclarations": [
                {
                    "name": "add_or_update_lore",
                    "description": "Adiciona ou ATUALIZA um fragmento de lore (conhecimento do mundo) no banco de dados vetorial. Use para CONSOLIDAR descrições.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "id_canonico": {"type": "STRING", "description": "O ID canônico da ENTIDADE PRINCIPAL que está a ser descrita (ex: 'planeta_cygnus_prime', 'pj_lyra_a_andarilha')."},
                            "text_content": {"type": "STRING", "description": "O texto COMPLETO e CONSOLIDADO do fragmento de lore a ser armazenado e vetorizado."},
                            "metadata": {"type": "STRING", "description": "Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Cygnus Prime\"}'."}
                        },
                        "required": ["id_canonico", "text_content", "metadata"]
                    }
                }
            ]
        }]

    def format_prompt(self, narrative_text, game_context):
        """
        Cria o prompt para o LLM, instruindo-o a agir como um agente de ChromaDB.
        """
        context_str = json.dumps(game_context, indent=2, ensure_ascii=False)

        return f"""
        # INSTRUÇÃO PARA AGENTE DE MEMÓRIA DE CONTEXTO (CHROMA AI)
        Você é um "Agente de Memória de Contexto", um especialista em analisar e **CONSOLIDAR** conhecimento (lore) de RPG.

        **TAREFA CRÍTICA: PROCESSAMENTO EM LOTE E CONSOLIDAÇÃO!**
        Sua tarefa é analisar a narrativa e, para cada entidade principal descrita, criar **UMA ÚNICA** chamada de função `add_or_update_lore` que **consolide TODA a nova informação sobre ela**. Você pode fazer **ATÉ {config.MAX_AGENT_TOOL_CALLS} chamadas de função no total** na sua resposta, uma para cada entidade diferente que foi descrita.

        **EXEMPLO DE COMO AGIR:**
        - **NARRATIVA:** "Lyra viu o Planeta X, que era vermelho. Perto dali, a Estação Y brilhava. A estação pertencia à Facção Z."
        - **AÇÃO CORRETA (FAÇA ISTO):**
          - `add_or_update_lore(id_canonico='planeta_x', text_content='Planeta X é um planeta vermelho.', ...)`
          - `add_or_update_lore(id_canonico='estacao_y', text_content='Estação Y é uma estação brilhante que pertence à Facção Z.', ...)`

        **REGRAS ADICIONAIS:**
        1.  **Foco na Entidade Principal:** Identifique a entidade principal (local, personagem, etc.) e agrupe todos os detalhes sobre ela. O `id_canonico` da chamada da função deve ser o `id_canonico` da **entidade principal**.
        2.  **Ignore Ações e Eventos Transitórios.**
        3.  **Metadados são Cruciais.**

        **Contexto Atual do Jogo (para referência):**
        {context_str}

        **Narrativa a ser Analisada:**
        "{narrative_text}"

        Analise a narrativa, **CONSOLIDE** as informações e chame a função `add_or_update_lore` UMA VEZ por entidade principal descrita, até um máximo de {config.MAX_AGENT_TOOL_CALLS} chamadas.
        """
