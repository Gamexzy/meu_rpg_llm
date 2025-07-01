import json
from servidor.tools import ALL_TOOLS

class WorldAgent:
    """
    Agente de IA unificado, o "Arquiteto do Mundo".
    Versão: 2.3.0 - Generalizado para suportar uma criação de mundo e personagem interativa ou automática.
    """
    def __init__(self):
        print("INFO: WorldAgent (Arquiteto Unificado v2.3) inicializado.")

    def get_tool_declarations(self):
        """
        Retorna a lista completa de ferramentas do pacote centralizado `servidor.tools`.
        """
        return ALL_TOOLS

    def format_prompt(self, narrative_mj, contexto):
        """
        Cria um prompt abrangente que instrui a IA a seguir o processo de 3 estágios.
        """
        context_str = json.dumps(contexto, indent=2, ensure_ascii=False)

        # Lógica de instrução generalizada.
        # A IA agora decide se deve criar com base na narrativa, em vez de uma regra fixa.
        player_instruction = """
# REGRA CRÍTICA SOBRE A CRIAÇÃO DE ENTIDADES:
Sua principal função é garantir que o estado do mundo digital (banco de dados) reflita a narrativa.
- **SE A NARRATIVA DESCREVER** um personagem, local ou item que ainda não existe no 'Contexto Atual do Jogo', sua tarefa é criá-lo usando as ferramentas apropriadas (ex: `add_or_get_player`, `add_or_get_location`).
- **SE A NARRATIVA FOR APENAS DIÁLOGO** ou uma pergunta para o jogador (ex: "Qual o seu nome?"), você não precisa criar nada. Apenas responda que nenhuma ação é necessária.
- **SE O JOGADOR JÁ EXISTE** (verifique o `id_canonico` no contexto), NÃO o crie novamente. Use o ID existente em outras funções.
"""

        return f"""
        # INSTRUÇÃO PARA AGENTE ARQUITETO DE MUNDO (Processo de 3 Estágios)
        Você é um agente de IA mestre, um "Arquiteto de Mundo" responsável por manter a consistência e a integridade do universo do jogo. Sua tarefa é analisar a narrativa e usar as ferramentas disponíveis para atualizar TODOS os aspectos do mundo de forma coesa e lógica.

        {player_instruction}

        **PROCESSO OBRIGATÓRIO DE 3 ESTÁGIOS:**

        **1. ESTÁGIO DE ANÁLISE (ANALYSIS):**
        Primeiro, leia a narrativa e o contexto. Em texto simples, liste as entidades e relações novas ou atualizadas que você identificou. Se nenhuma ação for necessária, declare isso explicitamente. NÃO GERE CÓDIGO AINDA.
        - Exemplo de Análise (Criação):
          - Entidade: Local "Genesis Prime" (id_canonico: `planeta_genesis_prime`)
          - Entidade: Jogador "Astrea" (id_canonico: `pj_astrea_genesis_prime`)
          - Relação: "Astrea" está em "Genesis Prime".
          - Lore: Genesis Prime é um planeta exuberante.
        - Exemplo de Análise (Sem Ação):
          - A narrativa é apenas um diálogo ou pergunta. Nenhuma entidade nova ou atualização de estado foi descrita. Nenhuma ação de ferramenta é necessária.

        **2. ESTÁGIO DE PLANEJAMENTO (PLAN):**
        Segundo, se a análise indicou que ações são necessárias, crie um plano de execução passo a passo em texto simples. Se nenhuma ação for necessária, pule esta etapa.
        - Exemplo de Plano:
          1. Chamar `add_or_get_location` para criar `planeta_genesis_prime`.
          2. Chamar `add_or_get_player` para criar `pj_astrea_genesis_prime` no local recém-criado.
          3. Chamar `add_or_update_lore` para salvar a descrição do planeta.

        **3. ESTÁGIO DE EXECUÇÃO (EXECUTION):**
        Terceiro, e somente se um plano foi criado, gere o bloco de código final contendo TODAS as chamadas de função (`tool_code`) que você planejou. Se nenhuma ação for necessária, retorne uma resposta vazia ou "Nenhuma ação necessária.".

        ---
        **Contexto Atual do Jogo (Para Referência):**
        {context_str}

        ---
        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrative_mj}
        \"\"\"
        ---

        Agora, inicie o processo de 3 estágios. Forneça sua Análise, seu Plano e, finalmente, o bloco de código de Execução (se aplicável).
        """
