import json

class ChromaDBAgent:
    """
    Agente especializado em analisar a narrativa do Mestre de Jogo (MJ)
    e extrair informações relevantes para serem armazenadas ou atualizadas
    no ChromaDB como "lore" ou memória de longo prazo.
    Versão: 1.0.1
    """
    def __init__(self):
        """
        Inicializa o agente do ChromaDB.
        """
        print("INFO: ChromaDBAgent inicializado (v1.0.1).")

    def get_tool_declarations(self):
        """
        Retorna a declaração de ferramentas que este agente pode usar.
        """
        return [{
            "functionDeclarations": [
                {
                    "name": "add_or_update_lore",
                    "description": "Adiciona ou atualiza um fragmento de lore (conhecimento do mundo) no banco de dados vetorial. Use para registrar descrições de locais, eventos históricos, fatos sobre personagens, etc. que foram mencionados na narrativa.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "id_canonico": {"type": "STRING", "description": "Um ID único e canônico para ESTE FRAGMENTO DE LORE. Deve ser descritivo. Se relacionado a uma entidade, use o ID da entidade como base. Ex: 'estacao_lazarus_descricao_visual', 'historia_guerra_clonica_capitulo_1'."},
                            "text_content": {"type": "STRING", "description": "O texto completo do fragmento de lore a ser armazenado e vetorizado."},
                            "metadata": {"type": "STRING", "description": "Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Estação Lazarus\"}'."}
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

        # CORREÇÃO: As chaves {} dentro do exemplo de JSON foram duplicadas para {{}} para evitar o erro de formatação da f-string.
        return f"""
Você é um "Agente de Memória de Contexto", um especialista em analisar narrativas de RPG e identificar fragmentos de conhecimento (lore) que devem ser preservados para referência futura. Sua única ferramenta é `add_or_update_lore`.

**Tarefa:**
Analise a seguinte narrativa do Mestre de Jogo. Identifique qualquer nova informação descritiva, histórica ou factual sobre locais, personagens, itens, facções ou eventos. Para cada fragmento de lore identificado, chame a função `add_or_update_lore`.

**Regras Importantes:**
1.  **Foco em Informação, Não em Ação:** Ignore ações do jogador ou eventos transitórios. Foque em descrições que definem o mundo. Ex: "A estação espacial era antiga, com corredores cobertos de poeira vermelha" -> BOM. "O jogador abriu a porta" -> RUIM.
2.  **ID Canônico do Fragmento:** Crie um `id_canonico` descritivo e único para CADA FRAGMENTO de lore. Se a lore descreve uma entidade existente, use o ID canônico da entidade como base para criar um ID mais específico. Ex: se a entidade é `estacao_lazarus`, um bom ID de lore seria `estacao_lazarus_descricao_visual` ou `estacao_lazarus_historia_fundacao`.
3.  **Metadados são Cruciais:** O campo `metadata` deve ser um JSON em formato de string. Ele ajuda a filtrar a lore no futuro.
    *   `id_canonico` (string): O ID canônico da entidade principal a que esta lore se refere.
    *   `metadata` (JSON STRING): Metadados adicionais em formato JSON string (ex: `'{{ "tipo": "local", "nome": "Estação Lazarus", "subtipo": "Estação Espacial Decadente" }}'`). Sempre inclua `tipo` (nome da tabela SQLite, ex: "locais", "personagens") e, se aplicável, `nome` e `subtipo` (a string de tipo que o MJ usou, ex: "Estação Espacial Decadente").

**Contexto Atual do Jogo (para referência):**
{context_str}

**Narrativa a ser Analisada:**
"{narrative_text}"

Analise a narrativa e chame a função `add_or_update_lore` para cada fragmento de conhecimento relevante que você encontrar. Se não houver nada de novo para adicionar, não chame nenhuma função.
"""