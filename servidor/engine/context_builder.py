import json
from config import config
from servidor.data_managers.data_manager import DataManager
from servidor.data_managers.chromadb_manager import ChromaDBManager

class ContextBuilder:
    """
    Constrói o dicionário de contexto completo para um turno do jogo.
    Versão: 1.2.0 - Simplificada a busca do jogador, delegando a lógica para o DataManager.
    """
    def __init__(self, data_manager: DataManager, chromadb_manager: ChromaDBManager):
        self.data_manager = data_manager
        self.chromadb_manager = chromadb_manager

    async def get_current_context(self):
        """
        Usa os gestores para obter um snapshot completo do estado atual do jogo.
        """
        # Tenta obter o estado do jogador. O DataManager lida com a lógica de encontrar o jogador.
        estado_jogador = self.data_manager.get_player_full_status()

        # Se nenhum jogador for encontrado, significa que é um novo jogo.
        if not estado_jogador:
            # Retorna um contexto inicial para o Mestre de Jogo criar o mundo.
            return {
                'jogador': {
                    'base': {'id_canonico': 'jogador_inexistente', 'nome': 'Aguardando Criação'},
                    'vitals': {}, 'habilidades': [], 'conhecimentos': [], 'posses': [], 'logs_recentes': []
                },
                'local_atual': {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}},
                'caminho_local': [],
                'locais_contidos': [],
                'locais_acessos_diretos': [],
                'locais_vizinhos': [],
                'lore_relevante': []
            }

        # Se um jogador foi encontrado, constrói o contexto completo.
        contexto = {'jogador': estado_jogador}
        local_id_canonico = estado_jogador['base'].get('local_id_canonico')
        local_id_numerico = estado_jogador['base'].get('local_id')

        if not local_id_canonico or not local_id_numerico:
            contexto['local_atual'] = {'id_canonico': 'limbo_desconhecido', 'nome': 'Limbo', 'perfil_json': {}}
            contexto['caminho_local'] = []
            contexto['locais_contidos'] = []
            contexto['locais_acessos_diretos'] = []
            contexto['locais_vizinhos'] = []
        else:
            contexto['local_atual'] = self.data_manager.get_entity_details_by_canonical_id('locais', local_id_canonico) or \
                                    {'id_canonico': local_id_canonico, 'nome': 'Local Desconhecido', 'perfil_json': {}}
            contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual'].get('perfil_json') or '{}')

            contexto['caminho_local'] = self.data_manager.get_ancestors(local_id_numerico)
            contexto['locais_contidos'] = self.data_manager.get_children(local_id_numerico)
            contexto['locais_acessos_diretos'] = self.data_manager.get_direct_accesses(local_id_numerico)
            contexto['locais_vizinhos'] = self.data_manager.get_siblings(local_id_numerico)

        query_rag = f"Descreva o local {contexto['local_atual']['nome']} (tipo: {contexto['local_atual'].get('tipo', 'Desconhecido')}) e o que há de interessante ou perigoso nele."
        relevante_lore = await self.chromadb_manager.find_relevant_lore(query_rag, n_results=3)
        contexto['lore_relevante'] = [r['document'] for r in relevante_lore] if relevante_lore else []

        return contexto
