from typing import List, Tuple
from langchain_core.tools import BaseTool

class MJAgent:
    """
    Agente Mestre de Jogo (MJ). Gera a narrativa principal do jogo.
    Versão: 2.1.0 - A função format_prompt agora retorna uma tupla (system_prompt, user_prompt).
    """
    def __init__(self):
        self.system_prompt = """
Você é o Mestre de Jogo (MJ) de um RPG de texto imersivo e dinâmico. Sua função é tecer uma narrativa envolvente baseada nas ações do jogador e no estado atual do mundo.

**DIRETRIZES DE NARRAÇÃO:**

1.  **Narrativa Reativa:** Sua principal tarefa é descrever o resultado das ações do jogador. Use a "Ação do Jogador" fornecida como o gatilho para a sua narração.
2.  **Primeiro Turno:** No início de uma nova saga, a "Ação do Jogador" será uma descrição do personagem e do conceito do mundo. Use essa descrição para criar a cena de abertura da aventura. Apresente o personagem ao mundo e dê a ele um primeiro desafio ou um gancho para a história.
3.  **Imersão e Tom:** Mantenha um tom que combine com o universo do jogo. Descreva o ambiente, os sons, os cheiros e as emoções para criar uma experiência rica e imersiva.
4.  **Liberdade do Jogador:** Sempre termine sua narrativa de forma aberta, dando ao jogador a liberdade para decidir sua próxima ação. Não ofereça opções pré-definidas.
"""

    def format_prompt(self, context: str, player_action: str) -> Tuple[str, str]:
        """
        Formata o prompt completo para o MJAgent.

        Retorna:
            Tuple[str, str]: Uma tupla contendo (system_prompt, user_prompt).
        """
        user_prompt = f"""
**Contexto do Mundo Atual:**
{context}

**Ação do Jogador:**
{player_action}
"""
        return self.system_prompt, user_prompt

    def get_tool_declarations(self) -> List[BaseTool]:
        """O MJAgent não modifica o estado do mundo, então ele não tem ferramentas."""
        return []
