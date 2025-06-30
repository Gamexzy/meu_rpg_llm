import json
from config import config

class ChromaDBAgent:
    """
    Agente especializado em CONSOLIDAR informações da narrativa para o ChromaDB.
    Versão: 1.3.0 - Prompt refinado para enfatizar a resposta em lote único e consolidada.
    """
    def __init__(self):
        """
        Inicializa o agente do ChromaDB.
        """
        print("INFO: ChromaDBAgent (Consolidador de Disparo Único) inicializado (v1.3.0).")

    def get_tool_declarations(self):
        """
        Retorna a declaração de ferramentas que este agente pode usar.
        """
        return [{
            "functionDeclarations": [
                {
                    "name": "add_or_update_lore",
                    "description": "Adiciona ou ATUALIZA um fragmento de lore (conhecimento do mundo) no banco de dados vetorial.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "id_canonico": {"type": "STRING", "description": "O ID canônico da ENTIDADE PRINCIPAL que está a ser descrita (ex: 'planeta_obsidiana')."},
                            "text_content": {"type": "STRING", "description": "O texto COMPLETO e CONSOLIDADO do fragmento de lore a ser armazenado."},
                            "metadata": {"type": "STRING", "description": "Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Obsidiana\"}'."}
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

        **TAREFA CRÍTICA: RESPOSTA ÚNICA E COMPLETA**
        Sua tarefa é analisar a narrativa e, para cada entidade principal descrita, criar **UMA ÚNICA** chamada de função `add_or_update_lore` que **consolide TODA a nova informação sobre ela**. Você deve retornar **UMA LISTA COM TODAS AS CHAMADAS DE FUNÇÃO `tool_code` necessárias EM UMA ÚNICA RESPOSTA**.

        **EXEMPLO DE COMO AGIR:**
        - **NARRATIVA:** "Arcanus viu o Planeta Obsidiana, que era escuro. Perto dali, a Torre de Obsidiana pulsava."
        - **AÇÃO CORRETA (FAÇA ISTO):**
          - `add_or_update_lore(id_canonico='planeta_obsidiana', text_content='O Planeta Obsidiana é um planeta escuro.', ...)`
          - `add_or_update_lore(id_canonico='torre_obsidiana', text_content='A Torre de Obsidiana é uma torre que pulsa.', ...)`

        **Contexto Atual do Jogo (para referência):**
        {context_str}

        **Narrativa a ser Analisada:**
        "{narrative_text}"

        Analise a narrativa, **CONSOLIDE** as informações e retorne a lista completa de chamadas de função `add_or_update_lore` necessárias.
        """
