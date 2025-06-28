import os
import sys
import json
import datetime
import asyncio
import aiohttp

# Adiciona o diretório da raiz do projeto ao sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config')) # Para importar config
sys.path.append(os.path.join(PROJECT_ROOT, 'servidor')) # Para importar managers

# Importar as configurações globais
import config as config 

# Importar os gestores dos pilares
from data_manager import DataManager
from chromadb_manager import ChromaDBManager
from neo4j_manager import Neo4jManager 

class AgenteMJ:
    """
    O cérebro do Mestre de Jogo (v2.25).
    Responsável por gerir o estado do jogo e interagir com o LLM.
    AGORA ATUA COMO ORQUESTRADOR DIRETO DAS ATUALIZAÇÕES DOS PILARES (SQLite + ChromaDB + Neo4j) EM TEMPO REAL.
    (Change: Corrigida a lógica de determinação do 'tipo' para nós do jogador no Neo4j,
             evitando a atribuição de 'Desconhecido'.
             Versão: 2.25)
    """
    def __init__(self):
        """
        Inicializa o AgenteMJ e as conexões com os gestores dos pilares.
        """
        print("--- Agente Mestre de Jogo (MJ) v2.25 a iniciar... ---")
        try:
            # DataManager AGORA É SÍNCRONO e NÃO recebe chroma_manager mais.
            self.data_manager = DataManager() 
            self.chroma_manager = ChromaDBManager()
            self.neo4j_manager = Neo4jManager() 

            print("INFO: Conexão com DataManager, ChromaDBManager e Neo4jManager estabelecida.")
            # Verificar se o genai_client no ChromaDBManager foi inicializado
            if not self.chroma_manager.genai_initialized:
                 print("AVISO: O ChromaDBManager não foi totalmente inicializado (API Key pode estar faltando). Embeddings podem falhar.")

        except FileNotFoundError as e:
            print(f"ERRO CRÍTICO: {e}")
            print("Por favor, execute o script 'scripts/build_world.py' antes de iniciar o servidor.")
            sys.exit(1)
        except Exception as e:
            print(f"ERRO CRÍTICO: Falha na inicialização do AgenteMJ: {e}")
            sys.exit(1)


    async def _setup_initial_campaign(self, player_id_canonico, player_name, initial_location_id_canonico):
        """
        Este método agora serve apenas como um ponto de entrada para futuras customizações
        de setup inicial que NÃO envolvem população automática de dados.
        A criação de personagem, locais e outros elementos iniciais será feita
        dinamicamente através de interações com o LLM.
        """
        print("\n--- Modo 'Folha em Branco': Nenhuma Campanha Inicial será populada automaticamente. ---")
        print("    A lore e o estado do mundo emergirão das interações do jogo.")
        # Removido todo o código de população de dados
        # O jogo começará sem um jogador ou locais pré-definidos no DB.
        # O LLM e a lógica do jogo precisarão criar isso dinamicamente.


    async def obter_contexto_atual(self): # Continua sendo async
        """
        Usa o DataManager e o ChromaDBManager para obter um snapshot completo do estado atual do jogo.
        Adaptado para um cenário de "folha em branco" onde o jogador pode não existir inicialmente.
        """
        print("\n--- A obter contexto para o turno atual... ---")
        contexto = {}
        
        # 1. Obter o estado completo do jogador
        JOGADOR_ID_CANONICO = config.DEFAULT_PLAYER_ID_CANONICO # Ainda usado como o ID canônico que *deve* ser criado
        estado_jogador = self.data_manager.get_player_full_status(JOGADOR_ID_CANONICO) 
        
        if not estado_jogador:
            print(f"AVISO: Jogador '{JOGADOR_ID_CANONICO}' não encontrado. O mundo está em branco. O LLM precisará criar o jogador.")
            # Para um sistema "folha em branco", é esperado que o jogador não exista inicialmente.
            # Retornamos um contexto mínimo e o LLM será instruído a criar o jogador.
            return {
                'jogador': {
                    'base': {'id_canonico': JOGADOR_ID_CANONICO, 'nome': 'Aguardando Criação'},
                    'vitals': {}, 'habilidades': [], 'conhecimentos': [], 'posses': [], 'logs_recentes': []
                },
                'local_atual': {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}},
                'caminho_local': [],
                'locais_contidos': [],
                'locais_acessos_diretos': [],
                'locais_vizinhos': [],
                'lore_relevante': []
            }
        
        contexto['jogador'] = estado_jogador
        
        # 2. Obter os IDs necessários a partir do estado do jogador
        local_id_canonico = estado_jogador['base'].get('local_id_canonico')
        local_id_numerico = estado_jogador['base'].get('local_id')

        # NOVO: Se o jogador existe mas não tem local (cenário inicial), tentar buscar o local padrão 'o_vazio_inicial'
        if not local_id_canonico or not local_id_numerico:
            print(f"AVISO: ID do local atual não encontrado no estado do jogador para '{JOGADOR_ID_CANONICO}'. Tentando buscar local padrão 'o_vazio_inicial'.")
            
            # Tentar obter os detalhes do local padrão, ou usar o mock se não existir
            local_vazio_details = self.data_manager.get_entity_details_by_canonical_id('locais', 'o_vazio_inicial')
            if local_vazio_details:
                contexto['local_atual'] = dict(local_vazio_details)
                contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual']['perfil_json'])
                contexto['caminho_local'] = [] # O vazio não tem hierarquia
                contexto['locais_contidos'] = []
                contexto['locais_acessos_diretos'] = []
                contexto['locais_vizinhos'] = []
            else:
                # Fallback para o mock se nem 'o_vazio_inicial' existe no DB
                contexto['local_atual'] = {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}}
                contexto['caminho_local'] = []
                contexto['locais_contidos'] = []
                contexto['locais_acessos_diretos'] = []
                contexto['locais_vizinhos'] = []
        else:
            # 3. Obter os detalhes completos do local atual (este método no DataManager é síncrono)
            contexto['local_atual'] = self.data_manager.get_entity_details_by_canonical_id('locais', local_id_canonico)
            if not contexto['local_atual']:
                print(f"AVISO: Detalhes do local '{local_id_canonico}' não encontrados. Usando local padrão 'O Vazio'.")
                contexto['local_atual'] = {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}}
            else:
                # O perfil_json vem como string, precisamos parsear para usar
                contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual']['perfil_json'])

            # 4. Obter o resto do contexto usando o ID numérico (estes métodos no DataManager são síncronos)
            contexto['caminho_local'] = self.data_manager.get_ancestors(local_id_numerico)
            contexto['locais_contidos'] = self.data_manager.get_children(local_id_numerico)
            contexto['locais_acessos_diretos'] = self.data_manager.get_direct_accesses(local_id_numerico) 
            contexto['locais_vizinhos'] = self.data_manager.get_siblings(local_id_numerico)
        
        # Busca de Lore Relevante no ChromaDB (Exemplo de RAG)
        # Se não há jogador ou local, a query de RAG será genérica ou vazia.
        query_rag = f"Descreva o local {contexto['local_atual']['nome']} (tipo: {contexto['local_atual'].get('tipo', 'Desconhecido')}) e o que há de interessante ou perigoso nele."
        relevante_lore = await self.chroma_manager.find_relevant_lore(query_rag, n_results=3)
        contexto['lore_relevante'] = [r['document'] for r in relevante_lore]
        print(f"INFO: {len(contexto['lore_relevante'])} documentos de lore relevante obtidos via ChromaDB.")

        print("INFO: Contexto do jogo obtido com sucesso.")
        return contexto

    def _formatar_prompt_para_llm(self, contexto, acao_do_jogador):
        """
        Formata o dicionário de contexto num prompt de texto para o LLM.
        Otimizado para reduzir a verbosidade em listas.
        """
        
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
        - **Criação Inicial do Mundo**: Se o jogador não existir, você DEVE iniciar a aventura criando o jogador e seu local inicial. Você tem TOTAL LIBERDADE CRIATIVA para definir o nome do jogador, suas características, o tipo de ambiente inicial (planeta, estação, floresta, cidade, etc.) e o nome desse local. Crie IDs canônicos únicos (ex: 'pj_nome_inventado', 'local_planeta_verde'). Não há restrições de cenário; crie o que você sentir ser mais interessante para o início da história.
          Ao criar entidades, o parâmetro 'tipo' é uma STRING LIVRE. Por exemplo, para um local, você pode usar 'Floresta Envelhecida', 'Estação Espacial Comercial', 'Templo Subterrâneo' etc. A IA tem total liberdade para nomear os tipos das entidades.
        """

        jogador_base = contexto['jogador']['base']
        jogador_vitals = contexto['jogador']['vitals']
        local_atual = contexto['local_atual']
        lore_relevante_str = "\n".join([f"- {doc}" for doc in contexto['lore_relevante']]) if contexto.get('lore_relevante') else "Nenhuma informação adicional relevante."
        
        perfil_completo_jogador = json.loads(jogador_base.get('perfil_completo_json', '{}')) if isinstance(jogador_base.get('perfil_completo_json'), str) else jogador_base.get('perfil_completo_jogador', {})

        # --- Funções auxiliares para formatar listas de dicionários de forma mais concisa ---
        def format_skills(skills_list):
            if not skills_list: return "Nenhuma."
            return "\n".join([f"- {s.get('categoria', '')}: {s.get('nome', '')} ({s.get('nivel_subnivel', 'N/A')})" for s in skills_list])

        def format_knowledge(knowledge_list):
            if not knowledge_list: return "Nenhum."
            return "\n".join([f"- {k.get('categoria', '')}: {k.get('nome', '')} (Nível: {k.get('nivel', 1)})" for k in knowledge_list])
        
        def format_possessions(possessions_list):
            if not possessions_list: return "Nenhuma."
            formatted_items = []
            for p in possessions_list:
                item_name = p.get('item_nome', 'Item Desconhecido')
                profile_data = json.loads(p.get('perfil_json', '{}')) if p.get('perfil_json') else {}
                details = ', '.join([f"{k}: {v}" for k, v in profile_data.items()])
                formatted_items.append(f"- {item_name} ({details})")
            return "\n".join(formatted_items)

        def format_logs(logs_list):
            if not logs_list: return "Nenhum log recente."
            return "\n".join([f"- [{l.get('timestamp_evento', 'N/A')}] {l.get('tipo', '')}: {l.get('conteudo', '')}" for l in logs_list])
        # ----------------------------------------------------------------------------------

        # Adicionar instrução para o LLM criar o jogador se o ID canônico for o placeholder
        player_creation_instruction = ""
        if jogador_base['nome'] == 'Aguardando Criação':
            player_creation_instruction = f"""
# INSTRUÇÃO CRÍTICA PARA CRIAÇÃO DO MUNDO (Se o Jogador não existir):
O jogo está começando do zero. Seu objetivo é estabelecer o ponto de partida da aventura.
Você DEVE realizar as seguintes ações, usando as funções do DataManager (via Function Calling):
1. Crie um local inicial (add_or_get_location). Dê a ele um nome, um 'tipo' (STRING LIVRE, ex: 'Planeta Verdejante', 'Estação de Mineração Abandonada') e uma descrição em 'perfil_json_data'. Crie um 'id_canonico' único (ex: 'local_floresta_sombria').
2. Crie o personagem do jogador (add_or_get_player) com o id_canonico '{config.DEFAULT_PLAYER_ID_CANONICO}'. Dê a ele um nome (ex: 'Gabriel', 'Elara'), um perfil completo em 'perfil_completo_data' (raça, ocupação, personalidade) e vincule-o ao 'id_canonico' do local que você acabou de criar.
Após a criação, inicie a narrativa descrevendo o ambiente e o que o jogador (com o nome que você definiu para o personagem com ID '{config.DEFAULT_PLAYER_ID_CANONICO}') percebe.
"""
            
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
- Habilidades:
{format_skills(contexto['jogador']['habilidades'])}
- Conhecimentos:
{format_knowledge(contexto['jogador']['conhecimentos'])}
- Posses:
{format_possessions(contexto['jogador']['posses'])}
- Logs Recentes:
{format_logs(contexto['jogador']['logs_recentes'])}

## LOCALIZAÇÃO
- Caminho Hierárquico: {' -> '.join([l['nome'] for l in reversed(contexto['caminho_local'])]) if contexto['caminho_local'] else 'Nenhum'}
- Local Atual: {local_atual['nome']} ({local_atual['id_canonico']})
- Tipo de Local: {local_atual.get('tipo', 'Desconhecido')} 
- Descrição: {local_atual['perfil_json'].get('descricao', 'Nenhuma descrição disponível.')}
- Propriedades do Local: {json.dumps(local_atual['perfil_json'], ensure_ascii=False)}
- Locais Contidos (Filhos): {[l['nome'] for l in contexto['locais_contidos']] or 'Nenhum'}
- Locais Vizinhos (Adjacentes por hierarquia): {[l['nome'] for l in contexto['locais_vizinhos']] or 'Nenhum'}
- Acessos Diretos (Navegáveis): {[f"{a['nome']} (via {a.get('tipo_acesso', 'passagem')}, Condição: {a.get('condicoes_acesso', 'Normal')})" for a in contexto['locais_acessos_diretos']] or 'Nenhum'}

## LORE ADICIONAL RELEVANTE (Recuperada da Memória)
{lore_relevante_str}

{player_creation_instruction}

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
        # A chave de API será lida do config.py que, por sua vez, lê da variável de ambiente GEMINI_API_KEY.
        apiKey = config.GEMINI_API_KEY 
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GENERATIVE_MODEL}:generateContent?key={apiKey}";
        
        # Adicionar ferramentas disponíveis para Function Calling
        tools = [
            # Funções do DataManager que o LLM pode chamar
            {"functionDeclarations": [
                {
                    "name": "add_or_get_location",
                    "description": "Adiciona um novo local ao universo ou retorna o ID se já existe. Use para criar planetas, estações, salas, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id_canonico": {"type": "string", "description": "ID canônico único do local (ex: 'estacao_alfa', 'planeta_gaia')."},
                            "nome": {"type": "string", "description": "Nome legível do local."},
                            "tipo": {"type": "string", "description": "Tipo do local (STRING LIVRE, ex: 'Estação Espacial', 'Planeta', 'Sala')."},
                            "perfil_json_data": {"type": "string", "description": "Dados adicionais do local em formato JSON string (ex: '{\"descricao\": \"Um hub de comércio.\"}' ).", "nullable": True},
                            "parent_id_canonico": {"type": "string", "description": "ID canônico do local pai, se houver (ex: uma sala dentro de uma estação).", "nullable": True}
                        },
                        "required": ["id_canonico", "nome", "tipo"]
                    }
                },
                {
                    "name": "add_or_get_player",
                    "description": "Adiciona um novo jogador ao banco de dados ou retorna o ID se já existe. Use para criar o personagem principal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id_canonico": {"type": "string", "description": "ID canônico único do jogador (ex: 'pj_gabriel_oliveira')."},
                            "nome": {"type": "string", "description": "Nome do jogador."},
                            "local_inicial_id_canonico": {"type": "string", "description": "ID canônico do local onde o jogador inicia."},
                            "perfil_completo_data": {"type": "string", "description": "Dados completos do perfil do jogador em formato JSON string (ex: '{\"raca\": \"Humano\", \"ocupacao\": \"Explorador\"}')."}
                        },
                        "required": ["id_canonico", "nome", "local_inicial_id_canonico", "perfil_completo_data"]
                    }
                },
                {
                    "name": "add_player_vitals",
                    "description": "Adiciona ou atualiza o status físico e emocional do jogador.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jogador_id_canonico": {"type": "string", "description": "ID canônico do jogador."},
                            "fome": {"type": "string", "description": "Nível de fome (ex: 'Normal', 'Com Fome').", "nullable": True},
                            "sede": {"type": "string", "description": "Nível de sede (ex: 'Normal', 'Com Sede').", "nullable": True},
                            "cansaco": {"type": "string", "description": "Nível de cansaço (ex: 'Descansado', 'Fadigado').", "nullable": True},
                            "humor": {"type": "string", "description": "Estado de humor (ex: 'Neutro', 'Curioso').", "nullable": True},
                            "motivacao": {"type": "string", "description": "Nível de motivação (ex: 'Neutro', 'Motivado').", "nullable": True},
                            "timestamp_atual": {"type": "string", "description": "Timestamp atual no formato अवलंब-MM-DD HH:MM:SS.", "nullable": True}
                        },
                        "required": ["jogador_id_canonico"]
                    }
                },
                {
                    "name": "add_player_skill",
                    "description": "Adiciona uma nova habilidade ao jogador. Já é idempotente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jogador_id_canonico": {"type": "string", "description": "ID canônico do jogador."},
                            "categoria": {"type": "string", "description": "Categoria da habilidade (ex: 'Exploração', 'Combate')."},
                            "nome": {"type": "string", "description": "Nome da habilidade (ex: 'Navegação Espacial', 'Tiro Preciso')."},
                            "nivel_subnivel": {"type": "string", "description": "Nível ou subnível da habilidade (ex: 'Novato', 'Avançado').", "nullable": True},
                            "observacoes": {"type": "string", "description": "Observações adicionais sobre a habilidade.", "nullable": True}
                        },
                        "required": ["jogador_id_canonico", "categoria", "nome"]
                    }
                },
                {
                    "name": "add_player_knowledge",
                    "description": "Adiciona um novo conhecimento ao jogador. Já é idempotente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jogador_id_canonico": {"type": "string", "description": "ID canônico do jogador."},
                            "categoria": {"type": "string", "description": "Categoria do conhecimento (ex: 'Ciência', 'História')."},
                            "nome": {"type": "string", "description": "Nome do conhecimento (ex: 'Anomalias Gravitacionais', 'Cultura Antiga')."},
                            "nivel": {"type": "integer", "description": "Nível do conhecimento (1-5).", "nullable": True},
                            "descricao": {"type": "string", "description": "Descrição detalhada do conhecimento.", "nullable": True}
                        },
                        "required": ["jogador_id_canonico", "categoria", "nome"]
                    }
                },
                {
                    "name": "add_or_get_player_possession",
                    "description": "Adiciona uma nova posse ao jogador ou retorna o ID se já existe. Use para itens do inventário.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jogador_id_canonico": {"type": "string", "description": "ID canônico do jogador."},
                            "item_nome": {"type": "string", "description": "Nome do item (ex: 'Kit de Sobrevivência')."},
                            "posse_id_canonico": {"type": "string", "description": "ID canônico único da posse (ex: 'kit_sobrevivencia_gabriel')."},
                            "perfil_json_data": {"type": "string", "description": "Dados adicionais da posse em formato JSON string (ex: '{\"estado\": \"novo\"}').", "nullable": True}
                        },
                        "required": ["jogador_id_canonico", "item_nome", "posse_id_canonico"]
                    }
                },
                {
                    "name": "add_log_memory",
                    "description": "Adiciona um log ou memória consolidada para o jogador.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jogador_id_canonico": {"type": "string", "description": "ID canônico do jogador."},
                            "tipo": {"type": "string", "description": "Tipo de log (ex: 'log_evento', 'memoria_consolidada')."},
                            "conteudo": {"type": "string", "description": "Conteúdo do log ou memória."},
                            "timestamp_evento": {"type": "string", "description": "Timestamp do evento no formato अवलंब-MM-DD HH:MM:SS.", "nullable": True}
                        },
                        "required": ["jogador_id_canonico", "tipo", "conteudo"]
                    }
                },
                {
                    "name": "update_player_location",
                    "description": "Atualiza a localização atual do jogador no DB.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_canonical_id": {"type": "string", "description": "ID canônico do jogador."},
                            "new_local_canonical_id": {"type": "string", "description": "ID canônico do novo local do jogador."}
                        },
                        "required": ["player_canonical_id", "new_local_canonical_id"]
                    }
                },
                {
                    "name": "add_direct_access_relation",
                    "description": "Adiciona uma relação de acesso direto entre dois locais. Já é idempotente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origem_id_canonico": {"type": "string", "description": "ID canônico do local de origem."},
                            "destino_id_canonico": {"type": "string", "description": "ID canônico do local de destino."},
                            "tipo_acesso": {"type": "string", "description": "Tipo de acesso (ex: 'Corredor', 'Portal').", "nullable": True},
                            "condicoes_acesso": {"type": "string", "description": "Condições de acesso (ex: 'Aberto', 'Requer Chave').", "nullable": True}
                        },
                        "required": ["origem_id_canonico", "destino_id_canonico"]
                    }
                },
                {
                    "name": "add_universal_relation",
                    "description": "Adiciona uma relação universal entre quaisquer duas entidades. Já é idempotente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origem_id_canonico": {"type": "string", "description": "ID canônico da entidade de origem."},
                            "origem_tipo_tabela": {"type": "string", "description": "Nome da tabela da entidade de origem (ex: 'personagens', 'locais')."},
                            "tipo_relacao": {"type": "string", "description": "Tipo da relação (ex: 'AFILIADO_A', 'CONTROLA')."},
                            "destino_id_canonico": {"type": "string", "description": "ID canônico da entidade de destino."},
                            "destino_tipo_tabela": {"type": "string", "description": "Nome da tabela da entidade de destino (ex: 'faccoes', 'elementos_universais')."},
                            "propriedades_data": {"type": "string", "description": "Dados adicionais da relação em formato JSON string (ex: '{\"intensidade\": 0.8}').", "nullable": True}
                        },
                        "required": ["origem_id_canonico", "origem_tipo_tabela", "tipo_relacao", "destino_id_canonico", "destino_tipo_tabela"]
                    }
                },
                {
                    "name": "add_column_to_table",
                    "description": "Adiciona uma nova coluna a uma tabela existente. Idempotente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string", "description": "Nome da tabela para adicionar a coluna."},
                            "column_name": {"type": "string", "description": "Nome da nova coluna."},
                            "column_type": {"type": "string", "description": "Tipo de dado da coluna (ex: 'TEXT', 'INTEGER')."},
                            "default_value": {"type": "string", "description": "Valor padrão opcional para a nova coluna.", "nullable": True}
                        },
                        "required": ["table_name", "column_name", "column_type"]
                    }
                },
                {
                    "name": "add_or_get_element_universal",
                    "description": "Adiciona um novo elemento universal (tecnologia, magia, recurso) ou retorna o ID se já existe.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id_canonico": {"type": "string", "description": "ID canônico único do elemento."},
                            "nome": {"type": "string", "description": "Nome legível do elemento."},
                            "tipo": {"type": "string", "description": "Tipo do elemento (STRING LIVRE, ex: 'Tecnologia Antiga', 'Magia Elemental')."},
                            "perfil_json_data": {"type": "string", "description": "Dados adicionais do elemento em JSON string.", "nullable": True}
                        },
                        "required": ["id_canonico", "nome", "tipo"]
                    }
                },
                {
                    "name": "add_or_get_personagem",
                    "description": "Adiciona um novo personagem (NPC, monstro) ou retorna o ID se já existe.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id_canonico": {"type": "string", "description": "ID canônico único do personagem."},
                            "nome": {"type": "string", "description": "Nome legível do personagem."},
                            "tipo": {"type": "string", "description": "Tipo do personagem (STRING LIVRE, ex: 'Comerciante Itinerante', 'Cientista Rebelde')."},
                            "perfil_json_data": {"type": "string", "description": "Dados adicionais do personagem em JSON string.", "nullable": True}
                        },
                        "required": ["id_canonico", "nome", "tipo"]
                    }
                },
                {
                    "name": "add_or_get_faccao",
                    "description": "Adiciona uma nova facção (reino, corporação) ou retorna o ID se já existe.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id_canonico": {"type": "string", "description": "ID canônico único da facção."},
                            "nome": {"type": "string", "description": "Nome legível da facção."},
                            "tipo": {"type": "string", "description": "Tipo da facção (STRING LIVRE, ex: 'Reino Subterrâneo', 'Corporação Interestelar')."},
                            "perfil_json_data": {"type": "string", "description": "Dados adicionais da facção em JSON string.", "nullable": True}
                        },
                        "required": ["id_canonico", "nome", "tipo"]
                    }
                },
            ]}
        ]

        payload["tools"] = tools

        # Mapeamento de funções para o AgenteMJ (para despachar chamadas de função)
        available_functions = {
            "add_or_get_location": self.data_manager.add_or_get_location,
            "add_or_get_player": self.data_manager.add_or_get_player,
            "add_player_vitals": self.data_manager.add_player_vitals,
            "add_player_skill": self.data_manager.add_player_skill,
            "add_player_knowledge": self.data_manager.add_player_knowledge,
            "add_or_get_player_possession": self.data_manager.add_or_get_player_possession,
            "add_log_memory": self.data_manager.add_log_memory,
            "update_player_location": self.data_manager.update_player_location,
            "add_direct_access_relation": self.data_manager.add_direct_access_relation,
            "add_universal_relation": self.data_manager.add_universal_relation,
            "add_column_to_table": self.data_manager.add_column_to_table,
            "add_or_get_element_universal": self.data_manager.add_or_get_element_universal,
            "add_or_get_personagem": self.data_manager.add_or_get_personagem,
            "add_or_get_faccao": self.data_manager.add_or_get_faccao,
        }

        try:
            async with session.post(apiUrl, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get("candidates"):
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            
                            # Lidar com chamadas de função
                            tool_calls = [part for part in parts if "functionCall" in part]
                            if tool_calls:
                                print("\n--- CHAMADA DE FUNÇÃO DETECTADA ---")
                                tool_responses_parts = []
                                for tc in tool_calls:
                                    function_call = tc["functionCall"]
                                    function_name = function_call["name"]
                                    function_args = function_call.get("args", {})
                                    
                                    print(f"Chamando função: {function_name} com args: {function_args}")
                                    
                                    if function_name in available_functions:
                                        func_to_call = available_functions[function_name]
                                        
                                        # Processar argumentos JSON strings
                                        processed_args = {}
                                        for k, v in function_args.items():
                                            if isinstance(v, str) and (k.endswith('_json_data') or k == 'perfil_completo_data' or k == 'propriedades_data'):
                                                try:
                                                    processed_args[k] = json.loads(v)
                                                except json.JSONDecodeError:
                                                    print(f"AVISO: Não foi possível parsear JSON para o argumento '{k}': {v}. Usando string literal.")
                                                    processed_args[k] = v
                                            else:
                                                processed_args[k] = v

                                        # Chamar a função do DataManager (SQLite)
                                        if asyncio.iscoroutinefunction(func_to_call):
                                            function_response = await func_to_call(**processed_args)
                                        else:
                                            function_response = func_to_call(**processed_args)
                                        
                                        print(f"Resposta da função DataManager '{function_name}': {function_response}")
                                        
                                        # --- ADICIONADO: ORQUESTRAÇÃO DO CHROMADB E NEO4J APÓS CHAMADAS DE FUNÇÃO ---
                                        # Esta seção é responsável por manter os outros pilares sincronizados.
                                        if function_response: # Verifica se a função do DataManager foi bem-sucedida
                                            # Recupera os detalhes completos do DB para formatar o texto/nó
                                            # e para garantir que o id_canonico retornado seja o correto.
                                            
                                            # Mapeamento para nomes de tabela SQLite
                                            table_name_map = {
                                                "add_or_get_location": "locais",
                                                "add_or_get_player": "jogador",
                                                "add_or_get_element_universal": "elementos_universais",
                                                "add_or_get_personagem": "personagens",
                                                "add_or_get_faccao": "faccoes",
                                                "add_or_get_player_possession": "jogador_posses"
                                            }
                                            
                                            # Obter ID canônico e nome da tabela para operações nos outros pilares
                                            id_canonico_to_sync = processed_args.get("id_canonico", processed_args.get("player_canonical_id")) # Adapta para player_canonical_id
                                            table_name = table_name_map.get(function_name)
                                            
                                            if id_canonico_to_sync and table_name:
                                                entity_details = self.data_manager.get_entity_details_by_canonical_id(table_name, id_canonico_to_sync)
                                                if entity_details:
                                                    # --- ORQUESTRAÇÃO CHROMADB ---
                                                    text_content_for_chroma = ""
                                                    metadata_for_chroma = {"id_canonico": id_canonico_to_sync, "tipo": table_name}

                                                    # Corrigido: Para jogador, use uma string de tipo mais específica ou 'Jogador'
                                                    if table_name == "jogador":
                                                        # Tenta usar raça ou ocupação do perfil completo, caso contrário, usa 'Jogador'
                                                        profile_data = json.loads(entity_details.get('perfil_completo_json', '{}'))
                                                        entity_type_string_for_node = profile_data.get('raca') or profile_data.get('ocupacao') or 'Jogador'
                                                    else:
                                                        # Para outras tabelas, 'tipo' já está na linha
                                                        entity_type_string_for_node = entity_details.get('tipo', 'Desconhecido')


                                                    if table_name == "locais":
                                                        desc = json.loads(entity_details.get('perfil_json', '{}')).get('descricao', 'N/A')
                                                        text_content_for_chroma = f"Local: {entity_details.get('nome')}. Tipo: {entity_type_string_for_node}. Descrição: {desc}. Propriedades: {entity_details.get('perfil_json')}"
                                                        metadata_for_chroma["nome"] = entity_details.get('nome')
                                                        metadata_for_chroma["subtipo"] = entity_type_string_for_node # 'subtipo' agora usa a string direta
                                                    elif table_name == "jogador":
                                                        profile_data = json.loads(entity_details.get('perfil_completo_json', '{}'))
                                                        text_content_for_chroma = f"O Jogador principal: {entity_details.get('nome')} (ID: {id_canonico_to_sync}). Raça: {profile_data.get('raca', 'N/A')}. Ocupação: {profile_data.get('ocupacao', 'N/A')}. Personalidade: {profile_data.get('personalidade', 'N/A')}."
                                                        metadata_for_chroma["nome"] = entity_details.get('nome')
                                                    elif table_name == "jogador_posses":
                                                        profile_data = json.loads(entity_details.get('perfil_json', '{}'))
                                                        text_content_for_chroma = f"Posse: {entity_details.get('item_nome')} (ID: {id_canonico_to_sync}) de {processed_args.get('jogador_id_canonico')}. Detalhes: {profile_data}."
                                                        metadata_for_chroma["nome"] = entity_details.get('item_nome')
                                                        metadata_for_chroma["jogador"] = processed_args.get('jogador_id_canonico')
                                                    elif table_name == "elementos_universais":
                                                        profile_data = json.loads(entity_details.get('perfil_json', '{}'))
                                                        text_content_for_chroma = f"Elemento Universal ({entity_type_string_for_node}): {entity_details.get('nome')}. Detalhes: {profile_data}."
                                                        metadata_for_chroma["nome"] = entity_details.get('nome')
                                                        metadata_for_chroma["subtipo"] = entity_type_string_for_node
                                                    elif table_name == "personagens":
                                                        profile_data = json.loads(entity_details.get('perfil_json', '{}'))
                                                        text_content_for_chroma = f"Personagem ({entity_type_string_for_node}): {entity_details.get('nome')}. Descrição: {profile_data.get('personalidade', 'N/A')}. Histórico: {profile_data.get('historico', 'N/A')}."
                                                        metadata_for_chroma["nome"] = entity_details.get('nome')
                                                        metadata_for_chroma["subtipo"] = entity_type_string_for_node
                                                    elif table_name == "faccoes":
                                                        profile_data = json.loads(entity_details.get('perfil_json', '{}'))
                                                        text_content_for_chroma = f"Facção ({entity_type_string_for_node}): {entity_details.get('nome')}. Ideologia: {profile_data.get('ideologia', 'N/A')}. Influência: {profile_data.get('influencia', 'N/A')}."
                                                        metadata_for_chroma["nome"] = entity_details.get('nome')
                                                        metadata_for_chroma["subtipo"] = entity_type_string_for_node
                                                    
                                                    if text_content_for_chroma:
                                                        await self.chroma_manager.add_or_update_lore(id_canonico_to_sync, text_content_for_chroma, metadata_for_chroma)
                                                else:
                                                    print(f"AVISO: Entidade recém-criada/atualizada '{id_canonico_to_sync}' não encontrada no DataManager para ChromaDB.")
                                            else:
                                                print(f"AVISO: Não foi possível mapear função '{function_name}' para adicionar ao ChromaDB.")

                                            # --- ORQUESTRAÇÃO NEO4J ---
                                            # Aqui adicionamos a lógica para atualizar o Neo4j
                                            neo4j_label_map = {
                                                "locais": "Local",
                                                "jogador": "Jogador", # Label base para o jogador
                                                "elementos_universais": "ElementoUniversal",
                                                "personagens": "Personagem",
                                                "faccoes": "Faccao",
                                                # 'jogador_posses' não é um nó primário no Neo4j, mas suas propriedades podem ir para o jogador.
                                            }
                                            
                                            base_label = neo4j_label_map.get(table_name)
                                            
                                            if entity_details and base_label:
                                                node_properties = {
                                                    "id_canonico": entity_details['id_canonico'],
                                                    "nome": entity_details['nome'],
                                                    "nome_tipo": entity_type_string_for_node # Usa a string de tipo determinada acima
                                                }
                                                if entity_details.get('perfil_json'):
                                                    try:
                                                        node_properties.update(json.loads(entity_details['perfil_json']))
                                                    except json.JSONDecodeError:
                                                        node_properties['perfil_json_raw'] = entity_details['perfil_json']
                                                
                                                # specific_label para Neo4j (ex: 'EstacaoEspacial') vem da string de tipo
                                                specific_label = entity_type_string_for_node # Usa a string de tipo determinada acima
                                                
                                                # 1. Adicionar/Atualizar o nó principal
                                                self.neo4j_manager.add_or_update_node(
                                                    id_canonico=entity_details['id_canonico'],
                                                    label_base=base_label,
                                                    properties=node_properties,
                                                    main_label=specific_label # Passa o rótulo específico (string 'tipo' limpa)
                                                )
                                                print(f"INFO: Nó Neo4j para '{entity_details['nome']}' ({entity_details['id_canonico']}) atualizado.")

                                                # 2. Lidar com relações específicas
                                                if function_name == "add_or_get_location" and processed_args.get("parent_id_canonico"):
                                                    self.neo4j_manager.add_or_update_parent_child_relation(
                                                        child_id_canonico=entity_details['id_canonico'],
                                                        parent_id_canonico=processed_args["parent_id_canonico"]
                                                    )
                                                    print(f"INFO: Relação DENTRO_DE para '{entity_details['nome']}' e pai '{processed_args['parent_id_canonico']}' atualizada no Neo4j.")
                                                
                                                if function_name == "add_or_get_player":
                                                    # Se o jogador foi criado/obtido, vincular ao local inicial
                                                    local_inicial_id_canonico = processed_args.get("local_inicial_id_canonico")
                                                    if local_inicial_id_canonico:
                                                        self.neo4j_manager.add_or_update_player_location_relation(
                                                            player_id_canonico=entity_details['id_canonico'],
                                                            local_id_canonico=local_inicial_id_canonico
                                                        )
                                                        print(f"INFO: Relação ESTA_EM para jogador '{entity_details['nome']}' e local '{local_inicial_id_canonico}' atualizada no Neo4j.")
                                                
                                                elif function_name == "update_player_location":
                                                    # Se a localização do jogador foi atualizada
                                                    player_id_canonico = processed_args.get("player_canonical_id")
                                                    new_local_id_canonico = processed_args.get("new_local_canonical_id")
                                                    self.neo4j_manager.add_or_update_player_location_relation(
                                                        player_id_canonico=player_id_canonico,
                                                        local_id_canonico=new_local_id_canonico
                                                    )
                                                    print(f"INFO: Relação ESTA_EM para jogador '{player_id_canonico}' e local '{new_local_id_canonico}' atualizada no Neo4j.")

                                                elif function_name == "add_direct_access_relation":
                                                    self.neo4j_manager.add_or_update_direct_access_relation(
                                                        origem_id_canonico=processed_args['origem_id_canonico'],
                                                        destino_id_canonico=processed_args['destino_id_canonico'],
                                                        tipo_acesso=processed_args.get('tipo_acesso'),
                                                        condicoes_acesso=processed_args.get('condicoes_acesso')
                                                    )
                                                    print(f"INFO: Relação DA_ACESSO_A entre '{processed_args['origem_id_canonico']}' e '{processed_args['destino_id_canonico']}' atualizada no Neo4j.")
                                                
                                                elif function_name == "add_universal_relation":
                                                    # origem_tipo_tabela e destino_tipo_tabela são os nomes das tabelas (ex: 'personagens')
                                                    # A função add_or_update_universal_relation no neo4j_manager já limpa esses rótulos
                                                    self.neo4j_manager.add_or_update_universal_relation(
                                                        origem_id_canonico=processed_args['origem_id_canonico'],
                                                        origem_label=neo4j_label_map.get(processed_args['origem_tipo_tabela'], processed_args['origem_tipo_tabela'].capitalize()), 
                                                        tipo_relacao=processed_args['tipo_relacao'],
                                                        destino_id_canonico=processed_args['destino_id_canonico'],
                                                        destino_label=neo4j_label_map.get(processed_args['destino_tipo_tabela'], processed_args['destino_tipo_tabela'].capitalize()), 
                                                        propriedades_data=processed_args.get('propriedades_data')
                                                    )
                                                    print(f"INFO: Relação universal '{processed_args['tipo_relacao']}' atualizada no Neo4j.")

                                            else:
                                                print(f"AVISO: Dados insuficientes para atualizar Neo4j após função '{function_name}'.")
                                        else:
                                            print(f"AVISO: Função DataManager '{function_name}' não retornou sucesso. Neo4j não atualizado.")

                                        tool_responses_parts.append({
                                            "functionResponse": {
                                                "name": function_name,
                                                "response": {"result": str(function_response)} # Converte resposta para string
                                            }
                                        })
                                
                                # Enviar as respostas das ferramentas de volta ao LLM para uma resposta narrativa
                                chatHistory.append({"role": "model", "parts": tool_calls})
                                chatHistory.append({"role": "user", "parts": tool_responses_parts})
                                
                                # Fazer uma nova requisição com as respostas das ferramentas
                                print("\n--- Enviando respostas das funções de volta ao LLM para narrativa final ---")
                                response_after_tools = await session.post(apiUrl, json={"contents": chatHistory, "tools": tools}, headers={'Content-Type': 'application/json'})
                                
                                if response_after_tools.status == 200:
                                    final_result = await response_after_tools.json()
                                    if final_result.get("candidates"):
                                        final_text = final_result["candidates"][0]["content"]["parts"][0]["text"]
                                        return final_text.strip()
                                    else:
                                        print(f"AVISO: Resposta final do LLM inválida após ferramentas. {await response_after_tools.text()}")
                                        return "O Mestre parece estar em silêncio após uma ação importante..."
                                else:
                                    response_text_after_tools = await response_after_tools.text()
                                    print(f"ERRO: Falha na API do LLM após ferramentas com status {response_after_tools.status}: {response_text_after_tools}")
                                    return "Uma interferência cósmica impede a clareza após as ações."
                            
                            # Se não houve chamada de função, retorna o texto direto
                            text = parts[0]["text"]
                            return text.strip()
                        else:
                            print(f"AVISO: Resposta do LLM inválida (sem 'content' ou 'parts'). {await response.text()}")
                            return "O Mestre parece estar em silêncio..."
                    else:
                        print(f"AVISO: Resposta do LLM sem 'candidates'. {await response.text()}")
                        return "O Mestre parece estar em silêncio."
                else:
                    response_text = await response.text()
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {response_text}")
                    if "403" in str(response_text) or "PERMISSION_DENIED" in str(response_text):
                        print("DICA: Verifique se sua GEMINI_API_KEY está correta e tem permissões para o modelo generativo.")
                    elif "429" in str(response_text) or "Resource has been exhausted" in str(response_text):
                         print("DICA: Você atingiu o limite de cota da API. Aguarde um pouco e tente novamente, ou verifique/aumente suas cotas.")
                    return "Uma interferência cósmica impede a clareza."
        except Exception as e:
            print(f"ERRO ao chamar a API do LLM: {e}")
            import traceback
            traceback.print_exc() # Imprime o stack trace completo
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado."

    async def executar_turno_de_jogo(self, session, acao_do_jogador=""):
        """Simula um único turno do jogo de forma assíncrona."""
        contexto = await self.obter_contexto_atual()
        # Não precisa verificar contexto, ele sempre retorna um (mesmo que seja o "Vazio")
        
        prompt = self._formatar_prompt_para_llm(contexto, acao_do_jogador)
        
        narrativa_mj = await self._chamar_llm(session, prompt)
        
        print("\n--- RESPOSTA DO MESTRE DE JOGO (LLM) ---")
        print(narrativa_mj)
        
        return narrativa_mj

# --- Ponto de Entrada Principal ---
async def main():
    """Função principal assíncrona para executar o servidor do jogo."""
    # NOVO: Caminho para o build_world.py ajustado para a nova estrutura de pastas
    build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py') # Usa config.BASE_DIR
    
    # 1. Executar build_world.py para garantir o esquema vazio
    # build_world.py agora é idempotente e não apaga o DB.
    if os.path.exists(build_script_path):
        print(f"Executando '{build_script_path}' para criar/verificar o esquema do DB...")
        os.system(f'python "{build_script_path}"')
    else:
        print(f"ERRO: Script 'build_world.py' não encontrado em '{build_script_path}'.")
        sys.exit(1)
    
    agente_mj = AgenteMJ()

    async with aiohttp.ClientSession() as session:
        # 2. REMOVIDA A CHAMADA AUTOMÁTICA DE _setup_initial_campaign.
        # Agora o mundo começa realmente em branco.
        print("\n--- INICIANDO JOGO: O MUNDO É UMA FOLHA EM BRANCO. ---")
        print("    O LLM e suas ações definirão o início da campanha.")

        # Loop principal do jogo
        while True:
            # Pega a ação do jogador
            acao_do_jogador = input("\nSua ação, Gabriel: ")
            if acao_do_jogador.lower() == 'sair':
                print("Encerrando o jogo...")
                break
            
            await agente_mj.executar_turno_de_jogo(session, acao_do_jogador)


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
