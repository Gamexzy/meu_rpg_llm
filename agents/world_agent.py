import json
# Importe diretamente a lista de ferramentas centralizada
from servidor.tools import ALL_TOOLS

class WorldAgent:
    """
    Agente de IA unificado, o "Arquiteto do Mundo".
    Utiliza um conjunto centralizado de ferramentas para atualizar o estado do mundo.
    Versão: 2.1.0 - Refatorado para usar o pacote de ferramentas centralizado `servidor.tools`.
    """
    def __init__(self):
        # Não precisamos mais instanciar os agentes antigos.
        print("INFO: WorldAgent (Arquiteto Unificado v2.1) inicializado.")

    def get_tool_declarations(self):
        """
        Retorna a lista completa de ferramentas do pacote centralizado `servidor.tools`.
        """
        return ALL_TOOLS

    def format_prompt(self, narrative_mj, contexto):
        """
        Cria um prompt abrangente que instrui a IA a seguir o processo de 3 estágios.
        (O conteúdo desta função permanece o mesmo da versão anterior)
        """
        context_str = json.dumps(contexto, indent=2, ensure_ascii=False)

        return f"""
        # INSTRUÇÃO PARA AGENTE ARQUITETO DE MUNDO (Processo de 3 Estágios)
        Você é um agente de IA mestre, um "Arquiteto de Mundo" responsável por manter a consistência e a integridade do universo do jogo. Sua tarefa é analisar a narrativa e usar as ferramentas disponíveis para atualizar TODOS os aspectos do mundo de forma coesa e lógica.

        **PROCESSO OBRIGATÓRIO DE 3 ESTÁGIOS:**

        **1. ESTÁGIO DE ANÁLISE (ANALYSIS):**
        Primeiro, leia a narrativa e o contexto. Em texto simples, liste as entidades e relações novas ou atualizadas que você identificou. NÃO GERE CÓDIGO AINDA. Apenas liste suas descobertas.
        - Exemplo de Análise:
          - Entidade: Local "Caverna de Cristal" (id_canonico: `caverna_cristal_eden_prime`)
          - Entidade: Item "Cristal Pulsante" (id_canonico: `item_cristal_pulsante_01`)
          - Relação: "Cristal Pulsante" está DENTRO da "Caverna de Cristal".
          - Lore: A caverna tem um brilho azulado por causa dos cristais.

        **2. ESTÁGIO DE PLANEJAMENTO (PLAN):**
        Segundo, com base na sua análise, crie um plano de execução passo a passo em texto simples. Descreva a ordem em que você chamará as ferramentas para garantir que não haja erros de referência (ex: não se pode conectar algo a um local que ainda não foi criado).
        - Exemplo de Plano:
          1. Chamar `add_or_get_location` para criar a `caverna_cristal_eden_prime`.
          2. Chamar `add_or_get_player_possession` para criar o `item_cristal_pulsante_01` para o jogador.
          3. Chamar `add_universal_relation` para registrar que o item está na caverna.
          4. Chamar `add_or_update_lore` para salvar a descrição da caverna.

        **3. ESTÁGIO DE EXECUÇÃO (EXECUTION):**
        Terceiro, e somente após a análise e o plano, gere o bloco de código final contendo TODAS as chamadas de função (`tool_code`) que você planejou.

        ---
        **Contexto Atual do Jogo (Para Referência):**
        {context_str}

        ---
        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrative_mj}
        \"\"\"
        ---

        Agora, inicie o processo de 3 estágios. Forneça sua Análise, seu Plano e, finalmente, o bloco de código de Execução.
        """