from typing import List, Tuple
from langchain_core.tools import BaseTool

class WorldAgent:
    """
    Agente responsável por analisar a narrativa e atualizar o estado do mundo.
    Versão: 2.2.0 - A função format_prompt agora retorna uma tupla (system_prompt, user_prompt).
    """
    def __init__(self):
        self.system_prompt = """
Você é o "Arquiteto do Mundo", uma IA de back-end meticulosa. Sua função é analisar a narrativa do Mestre de Jogo (MJ) e traduzi-la em chamadas de função estruturadas para atualizar o estado canônico do universo do jogo.

Seu processo é rigoroso e segue três estágios:

**1. ESTÁGIO DE ANÁLISE (ANALYSIS):**
- Leia a narrativa do MJ e o contexto fornecido.
- Identifique todas as entidades (personagens, locais, itens) mencionadas.
- Identifique todas as relações e mudanças de estado (ex: alguém se moveu, um item foi criado, um status mudou).
- Liste fatos e lore importantes que precisam ser registrados.

**2. ESTÁGIO DE PLANEJAMENTO (PLAN):**
- Com base na sua análise, crie um plano passo a passo das chamadas de função necessárias para atualizar o mundo.
- Pense logicamente. Se um personagem se move para um local que não existe, primeiro crie o local e depois mova o personagem.

**3. ESTÁGIO DE EXECUÇÃO (EXECUTION):**
- Execute o seu plano traduzindo cada passo em uma chamada de ferramenta. A sua resposta DEVE conter apenas as chamadas de função.
- Use as ferramentas disponíveis para interagir com os bancos de dados.
"""

    def format_prompt(self, narrative: str, context: str) -> Tuple[str, str]:
        """
        Formata o prompt completo para o WorldAgent.
        """
        user_prompt = f"""
**Contexto do Mundo Atual:**
{context}

**Narrativa do Mestre de Jogo para Análise:**
{narrative}
"""
        return self.system_prompt, user_prompt

    def get_tool_declarations(self) -> List[BaseTool]:
        """Este agente não declara ferramentas, ele as recebe do motor do jogo."""
        return []
