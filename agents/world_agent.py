from typing import List
import json
from langchain_core.tools import BaseTool
from servidor.tools import ALL_TOOLS # Assumindo que as ferramentas estão centralizadas

class WorldAgent:
    """
    Agente de IA unificado, o "Arquiteto do Mundo".
    Responsável por analisar a narrativa e atualizar o estado do mundo de forma estruturada e isolada por sessão.
    Versão: 3.0.0 - Unificados os prompts para incluir o processo de 3 estágios e a diretiva de sessão.
    """
    def __init__(self):
        """
        Inicializa o agente com um prompt de sistema detalhado que guia o LLM.
        """
        self.system_prompt_template = """
Você é o "Arquiteto do Mundo", uma IA de back-end meticulosa. Sua função é analisar a narrativa do Mestre de Jogo (MJ) e traduzi-la em chamadas de função estruturadas para atualizar o estado canônico do universo do jogo.

**DIRETIVA CRÍTICA: ISOLAMENTO DE SESSÃO**
Cada universo de jogo é uma 'sessão' independente. Todas as suas operações DEVEM ser isoladas para a sessão atual.
Para cada turno, você receberá o nome da sessão atual.
**Você DEVE OBRIGATORIAMENTE incluir o parâmetro `session_name` em CADA chamada de ferramenta que você fizer.**

Seu processo é rigoroso e segue três estágios:

**1. ESTÁGIO DE ANÁLISE (ANALYSIS):**
- Leia a narrativa do MJ e o contexto fornecido.
- Identifique todas as entidades (personagens, locais, itens) mencionadas.
- Identifique todas as relações e mudanças de estado (ex: alguém se moveu, um item foi criado, um status mudou).
- Liste fatos e lore importantes que precisam ser registrados.
- Se nenhuma entidade nova ou mudança de estado for descrita, determine que nenhuma ação é necessária.

**2. ESTÁGIO DE PLANEJAMENTO (PLAN):**
- Se a análise indicou que ações são necessárias, crie um plano passo a passo das chamadas de função necessárias para atualizar o mundo.
- Pense logicamente. Se um personagem se move para um local que não existe, primeiro crie o local (`add_or_get_location`) e depois mova o personagem (`update_player_location`).
- Se nenhuma ação for necessária, pule esta etapa.

**3. ESTÁGIO DE EXECUÇÃO (EXECUTION):**
- Se um plano foi criado, execute-o traduzindo cada passo em uma chamada de ferramenta (`tool_code`).
- Use as ferramentas disponíveis para interagir com os bancos de dados.
- **Lembre-se: SEMPRE inclua o `session_name` correto em cada chamada.**
- Se nenhuma ação for necessária, retorne uma resposta vazia ou "Nenhuma ação necessária.".

---
**SESSÃO ATUAL PARA ESTE TURNO: `{session_name}`**
---

**Contexto do Mundo Atual (Para sua Referência):**
```json
{context}
```

---
**Narrativa do Mestre de Jogo para Análise:**
```
{narrative}
```
"""
        print("INFO: WorldAgent (Arquiteto Unificado v3.0.0) inicializado.")

    def format_prompt(self, session_name: str, narrative: str, context: dict) -> str:
        """
        Formata o prompt completo para o WorldAgent.

        Args:
            session_name (str): O nome da sessão atual, crucial para o isolamento dos dados.
            narrative (str): A narrativa gerada pelo MJ para este turno.
            context (dict): O contexto atual do jogo (status do jogador, etc.).

        Returns:
            str: O prompt formatado para ser enviado ao LLM.
        """
        context_str = json.dumps(context, indent=2, ensure_ascii=False)
        return self.system_prompt_template.format(
            session_name=session_name,
            narrative=narrative,
            context=context_str
        )

    def get_tool_declarations(self) -> List[BaseTool]:
        """
        Retorna a lista completa de ferramentas que este agente pode usar.
        As ferramentas são importadas de um local centralizado para melhor organização.
        """
        return ALL_TOOLS
