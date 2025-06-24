import os
import sys
import json
import yaml

# Adiciona o diretório raiz do projeto ao path do sistema
# para que possamos importar o DataManager.
# Isto é necessário porque estamos a executar o script de dentro da pasta 'servidor'.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PROJECT_ROOT))

# Agora podemos importar o DataManager
from servidor.data_manager import DataManager

# --- Módulo Principal do Agente Mestre de Jogo (MJ) ---

class AgenteMJ:
    """
    O cérebro do Mestre de Jogo.
    Responsável por gerir o estado do jogo, interagir com o LLM
    e usar o DataManager para obter e guardar informações.
    """
    def __init__(self):
        """
        Inicializa o AgenteMJ e a sua conexão com o mundo através do DataManager.
        """
        print("--- Agente Mestre de Jogo (MJ) a iniciar... ---")
        try:
            self.data_manager = DataManager()
            print("INFO: Conexão com o DataManager estabelecida com sucesso.")
        except FileNotFoundError as e:
            print(f"ERRO CRÍTICO: {e}")
            print("Por favor, execute o script 'scripts/build_world.py' antes de iniciar o servidor.")
            sys.exit(1) # Termina a execução se a base de dados não existir.

    def obter_contexto_atual(self):
        """
        Usa o DataManager para obter um snapshot completo do estado atual do jogo,
        que será usado para formular o prompt para o LLM.
        """
        print("\n--- A obter contexto para o turno atual... ---")
        contexto = {}
        
        # 1. Obter o estado completo do jogador
        estado_jogador = self.data_manager.get_player_full_status()
        if not estado_jogador:
            print("ERRO: Não foi possível obter o estado do jogador.")
            return None
            
        contexto['jogador'] = estado_jogador
        
        # 2. Obter informações detalhadas sobre a localização atual
        local_atual_id = estado_jogador['base']['local_atual_id']
        contexto['local_atual'] = self.data_manager.get_local_details_by_id(local_atual_id)
        
        # 3. Obter o "caminho" para a localização atual (ancestrais)
        contexto['caminho_local'] = self.data_manager.get_ancestors(local_atual_id)
        
        # 4. Obter o que está contido no local atual (filhos)
        contexto['conteudo_local'] = self.data_manager.get_children(local_atual_id)

        # 5. Obter as tecnologias do local
        id_canonico_local = contexto['local_atual']['id_canonico']
        contexto['tecnologias_locais'] = self.data_manager.get_tecnologias_for_local(id_canonico_local)
        
        print("INFO: Contexto do jogo obtido com sucesso.")
        return contexto

    def executar_turno_de_jogo(self, acao_do_jogador=""):
        """
        Simula um único turno do jogo.
        """
        # Passo 1: Obter o contexto completo do estado do mundo.
        contexto = self.obter_contexto_atual()

        if not contexto:
            return

        # Passo 2: (FUTURO) Formular o prompt para o LLM com base no contexto.
        print("\n--- Contexto para o LLM (resumido) ---")
        print(f"Jogador: {contexto['jogador']['base']['nome']}")
        print(f"Localização: {contexto['local_atual']['nome']}")
        print(f"Descrição do Local: {yaml.safe_load(contexto['local_atual']['perfil_yaml']).get('descricao', 'N/A')}")
        print(f"Vitals: Humor: {contexto['jogador']['vitals']['humor']}")
        if acao_do_jogador:
            print(f"Ação do Jogador: {acao_do_jogador}")

        # Passo 3: (FUTURO) Enviar prompt para o LLM e obter a resposta.
        # Por agora, vamos apenas mostrar o contexto recolhido.
        
        # Passo 4: (FUTURO) Analisar a resposta do LLM e atualizar o estado do mundo
        # usando métodos de escrita no DataManager (ex: dm.update_player_location(...))
        
        # Passo 5: (FUTURO) Retornar a descrição narrativa para o jogador.


# --- Ponto de Entrada Principal ---
def main():
    """
    Função principal para executar o servidor do jogo.
    """
    # Recria a base de dados para garantir um estado inicial limpo para o teste.
    build_script_path = os.path.join(PROJECT_ROOT, 'scripts', 'build_world.py')
    if os.path.exists(build_script_path):
        print("Executando 'build_world.py' para garantir uma base de dados limpa e atualizada...")
        os.system(f'python "{build_script_path}"')
    
    # Inicia o Agente MJ
    agente_mj = AgenteMJ()

    # Simula um turno de jogo
    agente_mj.executar_turno_de_jogo(acao_do_jogador="Olho para o terminal à minha frente, tentando entender a nova anomalia.")


if __name__ == '__main__':
    main()
