import os
import sys
import json
import datetime # Importado para gerar timestamps
import asyncio
import aiohttp

# Adiciona o diretório raiz do projeto ao path do sistema
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PROJECT_ROOT))

# Agora podemos importar o DataManager e o ChromaDBManager
from servidor.data_manager import DataManager
from servidor.chromadb_manager import ChromaDBManager # Importar ChromaDBManager

# --- Módulo Principal do Agente Mestre de Jogo (MJ) ---

class AgenteMJ:
    """
    O cérebro do Mestre de Jogo (v2.13).
    Responsável por gerir o estado do jogo, interagir com o LLM
    e usar o DataManager para obter e guardar informações.
    (Change: Ajustado _setup_initial_campaign para passar posse_id_canonico em add_player_possession.)
    """
    def __init__(self):
        """
        Inicializa o AgenteMJ e a sua conexão com o mundo através do DataManager.
        """
        print("--- Agente Mestre de Jogo (MJ) v2.13 a iniciar... ---")
        try:
            # Observação: GEMINI_API_KEY no chromadb_manager.py deve ser "" para que o Canvas injete a chave.
            self.chroma_manager = ChromaDBManager() # Instanciar ChromaDBManager
            # Passar a instância do chroma_manager para o DataManager
            self.data_manager = DataManager(chroma_manager=self.chroma_manager)
            print("INFO: Conexão com o DataManager e ChromaDB estabelecida com sucesso.")
        except FileNotFoundError as e:
            print(f"ERRO CRÍTICO: {e}")
            print("Por favor, execute o script 'scripts/build_world.py' antes de iniciar o servidor.")
            sys.exit(1)

    async def _setup_initial_campaign(self, player_id_canonico='pj_gabriel_oliveira', player_name='Gabriel Oliveira', initial_location_id_canonico='braco_orion'):
        """
        Simula a criação de um novo personagem e um ponto de partida mínimo no mundo.
        Isso seria acionado pela UI do usuário ao iniciar uma nova campanha.
        """
        print("\n--- Configurando Campanha Inicial: Criando Personagem e Ponto de Partida ---")

        # Exemplo de uso da nova função: Adicionar uma coluna 'nivel_perigo' a locais
        print("\n--- Demonstração: Adicionando coluna 'nivel_perigo' à tabela 'locais' ---")
        # add_column_to_table não é async, então não precisa de await
        self.data_manager.add_column_to_table('locais', 'nivel_perigo', 'INTEGER', default_value=0)
        self.data_manager.add_column_to_table('locais', 'presenca_magica', 'TEXT', default_value='Nenhuma')
        print("--------------------------------------------------------------------")


        # 1. Criar locais essenciais com os novos tipos compatíveis com v9.1
        locais_essenciais = [
            {'id_canonico': 'braco_orion', 'nome': "Braço de Órion", 'tipo_nome': "Braço Espiral", 'parent_id_canonico': None, 'perfil_json_data': {"descricao": "Uma vasta região galáctica."}},
            {'id_canonico': 'margem_espiral_orion', 'nome': "Margem da Espiral de Órion", 'tipo_nome': "Região Galáctica", 'parent_id_canonico': 'braco_orion', 'perfil_json_data': {"descricao": "Região menos densa, com atividade de colonização."}},
            {'id_canonico': 'estacao_base_alfa', 'nome': "Estação Base Alfa", 'tipo_nome': "Estação Espacial", 'parent_id_canonico': 'margem_espiral_orion', 'perfil_json_data': {"funcao": "Hub de pesquisa e comércio.", "populacao": 500}},
            {'id_canonico': 'lab_central_alfa', 'nome': "Laboratório Central Alfa", 'tipo_nome': "Sala", 'parent_id_canonico': 'estacao_base_alfa', 'perfil_json_data': {"descricao": "Principal laboratório de pesquisa."}},
        ]
        
        # Gerar o timestamp inicial para a campanha
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print("\n--- Populando/Verificando Locais Iniciais com 'add_or_get_location' ---")
        for loc_data in locais_essenciais:
            # add_or_get_location é async, então precisa de await
            await self.data_manager.add_or_get_location(
                loc_data['id_canonico'],
                loc_data['nome'],
                loc_data['tipo_nome'],
                loc_data['perfil_json_data'],
                loc_data['parent_id_canonico']
            )
        print("--- Locais Iniciais Processados ---")

        # 2. Adicionar relações de acesso direto (exemplo)
        # add_direct_access_relation é async, então precisa de await
        await self.data_manager.add_direct_access_relation('estacao_base_alfa', 'lab_central_alfa', tipo_acesso='Corredor Principal')
        await self.data_manager.add_direct_access_relation('lab_central_alfa', 'estacao_base_alfa', tipo_acesso='Corredor Principal')

        # Exemplo de uso de add_or_get_element_universal
        print("\n--- Demonstração: Adicionando/Verificando Elementos Universais ---")
        # add_or_get_element_universal é async, então precisa de await
        await self.data_manager.add_or_get_element_universal(
            'tec_motor_dobra', 'Motor de Dobra Warp 7', 'Tecnologia',
            {'funcao': 'Propulsão FTL', 'velocidade': 'Warp 7'}
        )
        await self.data_manager.add_or_get_element_universal(
            'rec_cristal_mana', 'Cristal de Mana Bruto', 'Recurso',
            {'raridade': 'Comum', 'uso': 'Fonte de energia mágica'}
        )
        print("------------------------------------------------------------------")

        # 3. Criar o personagem (Gabriel)
        player_profile = {
            "raca": "Humano",
            "idade": 28,
            "ocupacao": "Explorador Independente",
            "personalidade": "Curioso, aventureiro.",
            "creditos_conta": 500
        }
        # add_player é async, então precisa de await
        player_id = await self.data_manager.add_player(player_id_canonico, player_name, initial_location_id_canonico, player_profile)

        if player_id:
            # 4. Adicionar status inicial do jogador
            # Métodos add_player_vitals, add_player_skill, add_player_possession, add_log_memory são async
            await self.data_manager.add_player_vitals(player_id_canonico, timestamp_atual=current_timestamp)
            await self.data_manager.add_player_skill(player_id_canonico, 'Exploração', 'Navegação Espacial', 'Novato')
            # NOVO: Para add_player_possession, crie um ID canônico único para a posse
            posse_id_canonico = f"kit_sobrevivencia_{player_id_canonico}"
            await self.data_manager.add_player_possession(player_id_canonico, 'Kit de Sobrevivência', posse_id_canonico, {'estado': 'novo', 'itens': ['ração', 'água', 'ferramentas']})
            await self.data_manager.add_log_memory(player_id_canonico, 'log_evento', 'Campanha iniciada.', timestamp_evento=current_timestamp)
            print("INFO: Campanha inicial configurada com sucesso!")
        else:
            print("ERRO: Falha ao configurar a campanha inicial.")

        # População inicial do ChromaDB a partir do SQLite APÓS todos os dados iniciais serem canonizados no SQLite
        print("\n--- Iniciando população inicial do ChromaDB (Pilar A) ---")
        await self.chroma_manager.build_collection_from_sqlite() # É uma chamada async, precisa de await
        print("--- População inicial do ChromaDB concluída ---")


    async def obter_contexto_atual(self): 
        """
        Usa o DataManager e o ChromaDBManager para obter um snapshot completo do estado atual do jogo.
        """
        print("\n--- A obter contexto para o turno atual... ---")
        contexto = {}
        
        # 1. Obter o estado completo do jogador (este método no DataManager é síncrono, NÃO precisa de await)
        JOGADOR_ID_CANONICO = 'pj_gabriel_oliveira' 
        estado_jogador = self.data_manager.get_player_full_status(JOGADOR_ID_CANONICO) 
        if not estado_jogador:
            print("ERRO: Não foi possível obter o estado do jogador. Certifique-se de que o jogador foi criado.")
            return None
        contexto['jogador'] = estado_jogador
        
        # 2. Obter os IDs necessários a partir do estado do jogador
        local_id_canonico = estado_jogador['base'].get('local_id_canonico')
        local_id_numerico = estado_jogador['base'].get('local_id')

        if not local_id_canonico or not local_id_numerico:
            print("ERRO: ID do local atual não encontrado no estado do jogador. O jogador precisa estar em um local válido.")
            return None

        # 3. Obter os detalhes completos do local atual (este método no DataManager é síncrono, NÃO precisa de await)
        contexto['local_atual'] = self.data_manager.get_entity_details_by_canonical_id('locais', local_id_canonico)
        if not contexto['local_atual']:
            print(f"ERRO: Detalhes do local não encontrados para o ID canónico {local_id_canonico}.")
            return None
        # O perfil_json vem como string, precisamos parsear para usar
        contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual']['perfil_json'])


        # 4. Obter o resto do contexto usando o ID numérico
        # Estes métodos no DataManager são síncronos, NÃO precisam de await
        contexto['caminho_local'] = self.data_manager.get_ancestors(local_id_numerico)
        contexto['locais_contidos'] = self.data_manager.get_children(local_id_numerico)
        # get_direct_accesses é síncrono (não async def), então REMOVER await
        contexto['locais_acessos_diretos'] = self.data_manager.get_direct_accesses(local_id_numerico) 
        contexto['locais_vizinhos'] = self.data_manager.get_siblings(local_id_numerico)
        
        # Busca de Lore Relevante no ChromaDB (Exemplo de RAG)
        query_rag = f"Descreva o local {contexto['local_atual']['nome']} (tipo: {contexto['local_atual'].get('tipo', 'Desconhecido')}) e o que há de interessante ou perigoso nele."
        relevante_lore = await self.chroma_manager.find_relevant_lore(query_rag, n_results=3) # Este é async, precisa de await
        contexto['lore_relevante'] = [r['document'] for r in relevante_lore]
        print(f"INFO: {len(contexto['lore_relevante'])} documentos de lore relevante obtidos via ChromaDB.")

        print("INFO: Contexto do jogo obtido com sucesso.")
        return contexto

    def _formatar_prompt_para_llm(self, contexto, acao_do_jogador):
        """Formata o dicionário de contexto num prompt de texto para o LLM."""
        
        # Regras e Diretrizes agora deveriam ser recuperadas do DB (ChromaDB ou SQLite)
        # ou passadas como strings estáticas se forem universais e fixas.
        
        # Exemplo de regras e diretrizes estáticas (idealmente viriam do DB)
        regras_universais = """
        Regras de Jogo:
        - Necessidades Físicas e Mentais: Gestão de energia, fome, sede, fadiga, humor e temperatura.
        - Escolhas com Consequência: Decisões que impactam diretamente a história, relações e oportunidades.
        - Progresso Narrativo e Sistêmico: A evolução do personagem está ligada às suas decisões e esforços.
        - Realismo na Criação de Corpos Celestes: Criação de planetas, estrelas e outros corpos celestes deve ser o mais realista possível.
        """
        diretrizes_narracao = """
        Diretrizes de Narração:
        - Narrativa Fluida e Ações (Sem Opções Numeradas): A história segue de forma natural com as decisões do personagem.
        - Descrições Opcionais: Descrições de ambientes são omitidas, a menos que solicitadas.
        - Progresso Implícito: O progresso em habilidades é comunicado de maneira narrativa, não de forma técnica.
        - Imersão Total: O jogador vivencia o mundo através dos sentidos e limitações do personagem.
        """

        jogador_base = contexto['jogador']['base']
        jogador_vitals = contexto['jogador']['vitals']
        local_atual = contexto['local_atual']
        lore_relevante_str = "\n".join([f"- {doc}" for doc in contexto['lore_relevante']]) if contexto.get('lore_relevante') else "Nenhuma informação adicional relevante."
        
        # Processar perfil_completo_jogador
        perfil_completo_jogador = json.loads(jogador_base.get('perfil_completo_json', '{}')) if isinstance(jogador_base.get('perfil_completo_json'), str) else jogador_base.get('perfil_completo_jogador', {})

        prompt = f"""
# ORDENS DO MESTRE
Você é um Mestre de Jogo de um RPG de texto. Sua função é descrever o resultado das ações do jogador de forma narrativa, coesa e criativa, seguindo as regras e o estado do mundo fornecidos. O cenário do jogo pode ser fantasia, ficção científica ou qualquer outro, adaptando a linguagem à descrição.

# DIRETRIZES DE NARRAÇÃO
{diretrizes_narracao}

# REGRAS DE JOGO UNIVERSAIS
{regras_universais}

# ESTADO ATUAL DO MUNDO
## JOGADOR
- Nome: {jogador_base['nome']} ({jogador_base['id_canonico']})
- Perfil: {json.dumps(perfil_completo_jogador, ensure_ascii=False)}
- Status Físico e Emocional: {json.dumps(jogador_vitals, ensure_ascii=False)}
- Habilidades: {json.dumps(contexto['jogador']['habilidades'], ensure_ascii=False)}
- Conhecimentos: {json.dumps(contexto['jogador']['conhecimentos'], ensure_ascii=False)}
- Posses: {json.dumps(contexto['jogador']['posses'], ensure_ascii=False)}
- Logs Recentes: {json.dumps(contexto['jogador']['logs_recentes'], ensure_ascii=False)}

## LOCALIZAÇÃO
- Caminho Hierárquico: {' -> '.join([l['nome'] for l in reversed(contexto['caminho_local'])])}
- Local Atual: {local_atual['nome']} ({local_atual['id_canonico']})
- Tipo de Local: {local_atual.get('tipo', 'Desconhecido')} 
- Descrição: {local_atual['perfil_json'].get('descricao', 'Nenhuma descrição disponível.')}
- Propriedades do Local: {json.dumps(local_atual['perfil_json'], ensure_ascii=False)}
- Locais Contidos (Filhos): {[l['nome'] for l in contexto['locais_contidos']] or 'Nenhum'}
- Locais Vizinhos (Adjacentes por hierarquia): {[l['nome'] for l in contexto['locais_vizinhos']] or 'Nenhum'}
- Acessos Diretos (Navegáveis): {[f"{a['nome']} (via {a.get('tipo_acesso', 'passagem')}, Condição: {a.get('condicoes_acesso', 'Normal')})" for a in contexto['locais_acessos_diretos']] or 'Nenhum'}

## LORE ADICIONAL RELEVANTE (Recuperada da Memória)
{lore_relevante_str}

# AÇÃO DO JOGADOR
"{acao_do_jogador}"

# SUA RESPOSTA
Agora, narre o resultado desta ação. Seja descritivo, envolvente e avance a história. Adapte sua narrativa ao cenário implícito pelos dados do mundo.
"""
        return prompt

    async def _chamar_llm(self, session, prompt_formatado):
        """Envia o prompt para a API do LLM usando aiohttp e retorna a resposta."""
        print("\n--- A contactar o LLM... ---")
        
        chatHistory = [{"role": "user", "parts": [{"text": prompt_formatado}]}]
        payload = {"contents": chatHistory}
        # A chave de API no Canvas será injetada em tempo de execução.
        # NÃO COLOQUE SUA CHAVE AQUI DIRETAMENTE. DEIXE-A VAZIA.
        apiKey = "" 
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}";
        

        try:
            async with session.post(apiUrl, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("candidates"):
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        return text.strip()
                    else:
                        print(f"AVISO: Resposta do LLM inválida. {await response.text()}")
                        return "O Mestre parece estar em silêncio..."
                else:
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {await response.text()}")
                    return "Uma interferência cósmica impede a clareza."
        except Exception as e:
            print(f"ERRO ao chamar a API do LLM: {e}")
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado."

    async def executar_turno_de_jogo(self, session, acao_do_jogador=""):
        """Simula um único turno do jogo de forma assíncrona."""
        contexto = await self.obter_contexto_atual() # AGORA COM await
        if not contexto:
            return

        prompt = self._formatar_prompt_para_llm(contexto, acao_do_jogador)
        
        narrativa_mj = await self._chamar_llm(session, prompt)
        
        print("\n--- RESPOSTA DO MESTRE DE JOGO (LLM) ---")
        print(narrativa_mj)
        
        return narrativa_mj

# --- Ponto de Entrada Principal ---
async def main():
    """Função principal assíncrona para executar o servidor do jogo."""
    build_script_path = os.path.join(PROJECT_ROOT, '..', 'scripts', 'build_world.py')
    
    # 1. Executar build_world.py para garantir o esquema vazio
    if os.path.exists(build_script_path):
        print("Executando 'build_world.py' para criar o esquema do DB...")
        os.system(f'python "{build_script_path}"')
    else:
        print(f"ERRO: Script 'build_world.py' não encontrado em '{build_script_path}'.")
        sys.exit(1)
    
    agente_mj = AgenteMJ()

    async with aiohttp.ClientSession() as session:
        # 2. Configurar a campanha inicial (criação do personagem e primeiro local)
        await agente_mj._setup_initial_campaign(
            player_id_canonico='pj_gabriel_oliveira',
            player_name='Gabriel Oliveira',
            initial_location_id_canonico='estacao_base_alfa' # Onde o jogador começa na nova campanha
        )

        # Agora, o jogo pode começar com o turno
        await agente_mj.executar_turno_de_jogo(session, acao_do_jogador="Olho para o terminal à minha frente, tentando entender a nova anomalia.")


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())

