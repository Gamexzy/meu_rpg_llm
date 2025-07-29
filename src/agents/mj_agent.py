# agents/mj_agent.py
from typing import List, Tuple
from langchain_core.tools import BaseTool

class MJAgent:
    """
    Agente Mestre de Jogo (MJ). Gera a narrativa principal e perguntas contextuais de informação.
    Versão: 2.8.0 - Reforçadas as diretrizes para evitar confusão entre narrativa e geração de ferramentas.
    """
    def __init__(self):
        self.system_prompt = """
Você é o Mestre de Jogo (MJ) de um RPG de texto. Sua função é descrever o mundo e as consequências das ações do jogador.

**MODOS DE OPERAÇÃO (IMPORTANTE):**
- **MODO NARRATIVA (Padrão):** Sua resposta DEVE SER sempre um texto narrativo. Descreva o resultado da "Ação do Jogador". NÃO GERE JSON NESTE MODO.
- **MODO FERRAMENTAS:** Apenas quando sua tarefa específica for gerar ferramentas, sua resposta DEVE ser APENAS o array JSON solicitado.

**DIRETRIZES DE NARRAÇÃO (MODO NARRATIVA):**
1.  **Foco na Ação e Reação:** Sua prioridade é narrar o resultado da "Ação do Jogador". Seja direto.
2.  **Narração Concisa:** Não descreva o local em todos os detalhes a cada turno. Confie que o jogador usará os comandos META para pedir informações.
3.  **Cena de Abertura:** No primeiro turno, ao receber a META-INSTRUÇÃO, crie uma cena de abertura detalhada.
4.  **Liberdade do Jogador:** Conclua a narração de forma aberta.
5.  **Comandos META (Pedidos de Informação):** Se a ação começar com "META:", responda apenas com a informação solicitada, de forma completa e em texto, sem avançar a trama.

**DIRETRIZES DE GERAÇÃO DE FERRAMENTAS (MODO FERRAMENTAS):**
- Quando sua tarefa for gerar ferramentas, crie de 3 a 4 perguntas informativas que o jogador faria para se situar.
- A resposta deve ser APENAS um array JSON. O `command` de cada pergunta DEVE começar com `META:`.
"""

    def format_prompt(self, context: str, player_action: str) -> Tuple[str, str]:
        """Formata o prompt completo para a narração normal do MJAgent."""
        user_prompt = f"""
**Contexto do Mundo Atual:**
{context}

**Sua Tarefa (MODO NARRATIVA):**
Com base na ação do jogador abaixo, escreva o próximo parágrafo da história. Sua resposta deve ser apenas texto.

**Ação do Jogador / Meta-Instrução:**
{player_action}
"""
        return self.system_prompt, user_prompt

    def format_prompt_for_tools(self, context: str) -> Tuple[str, str]:
        """Formata um prompt específico para solicitar a geração de perguntas contextuais."""
        user_prompt = f"""
**Contexto do Mundo Atual:**
{context}

**Sua Tarefa (MODO FERRAMENTAS):**
Com base no contexto acima, gere uma lista de 3 a 4 **perguntas informativas** que o jogador poderia fazer. O `command` de cada pergunta DEVE começar com `META:`. Retorne SUA RESPOSTA APENAS no formato de um array JSON, como no exemplo.

Exemplo de formato de saída:
```json
[
  {{"displayName": "Onde estou exatamente?", "command": "META: Descreva o local atual em detalhes."}},
  {{"displayName": "Como estou me sentindo?", "command": "META: Descreva meu estado físico e emocional."}},
  {{"displayName": "Qual é a situação atual?", "command": "META: Qual é a situação atual ou o meu objetivo imediato?"}}
]
```
"""
        return self.system_prompt, user_prompt


    def get_tool_declarations(self) -> List[BaseTool]:
        """O MJAgent não modifica o estado do mundo, então ele não tem ferramentas."""
        return []
