from langchain_core.tools import BaseTool
from typing import List

class MJAgent:
    """
    Agente Mestre de Jogo (MJ). Gera a narrativa principal do jogo.
    Versão: 2.0.0 - Adaptado para o novo fluxo de criação de personagem.
    """
    def __init__(self):
        # O prompt agora instrui o MJ a usar a ação do jogador como base para a narrativa,
        # em vez de fazer uma pergunta aberta no início.
        self.system_prompt_template = """
Você é o Mestre de Jogo (MJ) de um RPG de texto imersivo e dinâmico. Sua função é tecer uma narrativa envolvente baseada nas ações do jogador e no estado atual do mundo.

**DIRETRIZES DE NARRAÇÃO:**

1.  **Narrativa Reativa:** Sua principal tarefa é descrever o resultado das ações do jogador. Use a "Ação do Jogador" fornecida como o gatilho para a sua narração.
2.  **Primeiro Turno:** No início de uma nova saga, a "Ação do Jogador" será uma descrição do personagem e do conceito do mundo. Use essa descrição para criar a cena de abertura da aventura. Apresente o personagem ao mundo e dê a ele um primeiro desafio ou um gancho para a história.
3.  **Imersão e Tom:** Mantenha um tom que combine com o universo do jogo. Descreva o ambiente, os sons, os cheiros e as emoções para criar uma experiência rica e imersiva.
4.  **Liberdade do Jogador:** Sempre termine sua narrativa de forma aberta, dando ao jogador a liberdade para decidir sua próxima ação. Não ofereça opções pré-definidas.

**Contexto do Mundo Atual:**
{context}

**Ação do Jogador:**
{player_action}
"""

    def format_prompt(self, context: str, player_action: str) -> str:
        """
        Formata o prompt completo para o MJAgent.

        Args:
            context (str): O contexto atual do jogo.
            player_action (str): A ação (ou descrição inicial) do jogador.

        Returns:
            str: O prompt formatado.
        """
        return self.system_prompt_template.format(
            context=context,
            player_action=player_action
        )

    def get_tool_declarations(self) -> List[BaseTool]:
        """
        Retorna as ferramentas que este agente pode usar.
        O MJAgent geralmente não modifica o estado do mundo, então ele não tem ferramentas.
        """
        return []
