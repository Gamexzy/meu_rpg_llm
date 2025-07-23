from langchain_core.tools import BaseTool
from typing import List

class WorldAgent:
    """
    Agente responsável por analisar a narrativa e atualizar o estado do mundo de forma estruturada.
    Versão: 2.1.0 - Simplificado o prompt, removendo a responsabilidade do LLM de gerenciar a sessão.
    """
    def __init__(self):
        self.system_prompt_template = """
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
- Execute o seu plano traduzindo cada passo em uma chamada de ferramenta (`tool_code`).
- Use as ferramentas disponíveis para interagir com os bancos de dados.

**Contexto do Mundo Atual:**
{context}

**Narrativa do Mestre de Jogo para Análise:**
{narrative}
"""

    def format_prompt(self, narrative: str, context: str) -> str:
        """
        Formata o prompt completo para o WorldAgent.
        """
        return self.system_prompt_template.format(
            narrative=narrative,
            context=context
        )

    def get_tool_declarations(self) -> List[BaseTool]:
        """Retorna as ferramentas que este agente pode usar."""
        return []
