import asyncio
from config import config
from servidor.engine.context_builder import ContextBuilder
from servidor.llm.client import LLMClient
from agents.mj_agent import MJAgent
# Importa o novo agente unificado. As importações dos agentes antigos foram removidas.
from agents.world_agent import WorldAgent


class GameEngine:
    """
    Motor principal do jogo. Orquestra cada turno.
    Versão: 2.2.0 - Refatorado para usar um único WorldAgent e refletir a separação de responsabilidades (MJAgent não tem mais ferramentas).
    """
    def __init__(self, context_builder: ContextBuilder, llm_client: LLMClient):
        """
        Inicializa o motor do jogo com os componentes necessários.
        """
        self.context_builder = context_builder
        self.llm_client = llm_client
        self.mj_agent = MJAgent()
        # Instancia o novo agente unificado, que agora lida com todas as atualizações do mundo.
        self.world_agent = WorldAgent()
    
    async def execute_turn(self, player_action: str):
        """
        Simula um único turno do jogo de forma assíncrona.
        Este método agora faz apenas duas chamadas de IA por turno: uma para o Mestre de Jogo (narrativa)
        e uma para o WorldAgent (atualização do mundo).
        """
        print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
        context = await self.context_builder.get_current_context()
        
        print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
        prompt_narrativa = self.mj_agent.format_prompt(context, player_action)
        
        # 1ª Chamada de IA: Gerar a narrativa do Mestre de Jogo.
        # O método get_tool_declarations() do MJAgent agora retorna None, efetivamente desabilitando ferramentas para ele.
        narrative, _ = await self.llm_client.call(
            config.GENERATIVE_MODEL, 
            prompt_narrativa, 
            self.mj_agent.get_tool_declarations()
        )
        
        print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrative)

        if not narrative or "interferência cósmica" in narrative:
            print("\033[1;31m--- Análise do mundo suspensa devido a um erro na geração da narrativa. ---\033[0m")
            return narrative

        print("\n\033[1;36m--- Agente Arquiteto do Mundo está a analisar e a planear... ---\033[0m")
        
        # Prepara o prompt e as ferramentas para o agente unificado.
        world_agent_prompt = self.world_agent.format_prompt(narrative, context)
        world_agent_tools = self.world_agent.get_tool_declarations()
        
        # 2ª Chamada de IA: O WorldAgent analisa a narrativa e executa todas as atualizações de estado.
        # A parte de texto da resposta (analysis_and_plan_text) contém o "raciocínio" do agente.
        analysis_and_plan_text, _ = await self.llm_client.call(
            config.AGENT_GENERATIVE_MODEL,
            world_agent_prompt,
            world_agent_tools
        )

        # Imprime o "raciocínio" do agente para depuração, mostrando sua análise e plano.
        if analysis_and_plan_text:
            print("\n\033[1;34m--- Raciocínio do Arquiteto do Mundo ---\033[0m")
            print(analysis_and_plan_text)
        
        print("\033[1;32m--- Atualização do mundo concluída. ---\033[0m")
        return narrative
