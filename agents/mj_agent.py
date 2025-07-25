# agents/mj_agent.py
from typing import List, Tuple
from langchain_core.tools import BaseTool

class MJAgent:
    """
    Agente Mestre de Jogo (MJ). Gera a narrativa principal do jogo.
    Versão: 2.2.0 - Refinado o prompt para lidar explicitamente com o turno de construção de mundo.
    """
    def __init__(self):
        self.system_prompt = """
Você é o Mestre de Jogo (MJ) de um RPG de texto imersivo e dinâmico. Sua função é tecer uma narrativa envolvente baseada nas ações do jogador e no estado atual do mundo.

**DIRETRIZES DE NARRAÇÃO:**

1.  **Narrativa Reativa:** Sua principal tarefa é descrever o resultado das ações do jogador. Use a "Ação do Jogador" fornecida como o gatilho para a sua narração.

2.  **Turno de Construção de Mundo (Primeiro Turno):** No início de uma nova saga, a "Ação do Jogador" será uma **META-INSTRUÇÃO** contendo o nome do personagem e o conceito do mundo. O Arquiteto do Mundo já terá criado as entidades iniciais (jogador, local, etc.) com base nesta instrução. Sua tarefa é usar essa mesma instrução para criar a **CENA DE ABERTURA** da aventura. Apresente o personagem recém-criado ao mundo, descreva o local e dê a ele um primeiro desafio ou um gancho para a história.

3.  **Imersão e Tom:** Mantenha um tom que combine com o universo do jogo. Descreva o ambiente, os sons, os cheiros e as emoções para criar uma experiência rica e imersiva.

4.  **Liberdade do Jogador:** Sempre termine sua narrativa de forma aberta, dando ao jogador a liberdade para decidir sua próxima ação. Não ofereça opções pré-definidas (a menos que seja um elemento diegético, como um menu de computador no jogo).
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

**Ação do Jogador / Meta-Instrução:**
{player_action}
"""
        return self.system_prompt, user_prompt

    def get_tool_declarations(self) -> List[BaseTool]:
        """O MJAgent não modifica o estado do mundo, então ele não tem ferramentas."""
        return []

