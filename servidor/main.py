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
# from neo4j_manager import Neo4jManager # Instanciação e construção agora via sync_databases.py

class AgenteMJ:
    """
    O cérebro do Mestre de Jogo (v2.16).
    Responsável por gerir o estado do jogo e interagir com o LLM.
    AGORA ATUA COMO ORQUESTRADOR DIRETO DAS ATUALIZAÇÕES DOS PILARES (SQLite + ChromaDB) EM TEMPO REAL.
    (Change: main.py se torna o orquestrador explícito das atualizações de dados em tempo real.
             DataManager.py e ChromaDBManager.py são chamados diretamente e orquestrados aqui.
             Versão: 2.16 - Otimização de prompt para LLM.)
    """
    def __init__(self):
        """
        Inicializa o AgenteMJ e as conexões com os gestores dos pilares.
        """
        print("--- Agente Mestre de Jogo (MJ) v2.16 a iniciar... ---")
        try:
            # DataManager AGORA É SÍNCRONO e NÃO recebe chroma_manager mais.
            self.data_manager = DataManager() 
            self.chroma_manager = ChromaDBManager()
            # self.neo4j_manager = Neo4jManager() # Neo4j será sincronizado em lote via sync_databases.py

            print("INFO: Conexão com DataManager e ChromaDBManager estabelecida.")
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


    async def _setup_initial_campaign(self, player_id_canonico=config.DEFAULT_PLAYER_ID_CANONICO, player_name='Gabriel Oliveira', initial_location_id_canonico=config.DEFAULT_INITIAL_LOCATION_ID_CANONICO):
        """
        Configura a campanha inicial, criando o personagem e o mundo básico.
        O AgenteMJ ORQUESTRA a adição aos pilares diretamente.
        """
        print("\n--- Configurando Campanha Inicial: Criando Personagem e Ponto de Partida ---")

        # Gerar o timestamp inicial para a campanha
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. Adicionar colunas customizadas (exemplo de expansão de esquema)
        print("\n--- Demonstração: Adicionando colunas 'nivel_perigo' e 'presenca_magica' à tabela 'locais' ---")
        self.data_manager.add_column_to_table('locais', 'nivel_perigo', 'INTEGER', default_value=0)
        self.data_manager.add_column_to_table('locais', 'presenca_magica', 'TEXT', default_value='Nenhuma')
        print("--------------------------------------------------------------------")

        # 2. Criar locais essenciais - AGORA ORQUESTRANDO SQLITE E CHROMADB AQUI
        locais_essenciais = [
            {'id_canonico': 'braco_orion', 'nome': "Braço de Órion", 'tipo_nome': "Braço Espiral", 'parent_id_canonico': None, 'perfil_json_data': {"descricao": "Uma vasta região galáctica."}},
            {'id_canonico': 'margem_espiral_orion', 'nome': "Margem da Espiral de Órion", 'tipo_nome': "Região Galáctica", 'parent_id_canonico': 'braco_orion', 'perfil_json_data': {"descricao": "Região menos densa, com atividade de colonização."}},
            {'id_canonico': 'estacao_base_alfa', 'nome': "Estação Base Alfa", 'tipo_nome': "Estação Espacial", 'parent_id_canonico': 'margem_espiral_orion', 'perfil_json_data': {"funcao": "Hub de pesquisa e comércio.", "populacao": 500}},
            {'id_canonico': 'lab_central_alfa', 'nome': "Laboratório Central Alfa", 'tipo_nome': "Sala", 'parent_id_canonico': 'estacao_base_alfa', 'perfil_json_data': {"descricao": "Principal laboratório de pesquisa."}},
        ]
        
        print("\n--- Populando/Verificando Locais Iniciais (SQLite e ChromaDB) ---")
        for loc_data in locais_essenciais:
            # DataManager.add_or_get_location é SÍNCRONO.
            local_id = self.data_manager.add_or_get_location(
                loc_data['id_canonico'],
                loc_data['nome'],
                loc_data['tipo_nome'],
                loc_data['perfil_json_data'],
                loc_data['parent_id_canonico']
            )
            # ORQUESTRAÇÃO DO CHROMADB (async):
            if local_id and self.chroma_manager:
                text_content = f"Local: {loc_data['nome']}. Tipo: {loc_data['tipo_nome']}. Descrição: {loc_data['perfil_json_data'].get('descricao', 'N/A')}. Propriedades: {json.dumps(loc_data['perfil_json_data'], ensure_ascii=False)}"
                metadata = {"id_canonico": loc_data['id_canonico'], "tipo": "local", "nome": loc_data['nome'], "subtipo": loc_data['tipo_nome']}
                await self.chroma_manager.add_or_update_lore(loc_data['id_canonico'], text_content, metadata)
        print("--- Locais Iniciais Processados ---")

        # 3. Adicionar relações de acesso direto (SQLite e ChromaDB)
        acessos_iniciais = [
            {'origem_id': 'estacao_base_alfa', 'destino_id': 'lab_central_alfa', 'tipo_acesso': 'Corredor Principal', 'condicoes_acesso': 'Aberto'},
            {'origem_id': 'lab_central_alfa', 'destino_id': 'estacao_base_alfa', 'tipo_acesso': 'Corredor Principal', 'condicoes_acesso': 'Aberto'},
        ]
        for acesso in acessos_iniciais:
            # DataManager.add_direct_access_relation é SÍNCRONO.
            added = self.data_manager.add_direct_access_relation(
                acesso['origem_id'],
                acesso['destino_id'],
                acesso['tipo_acesso'],
                acesso['condicoes_acesso']
            )
            # ORQUESTRAÇÃO DO CHROMADB (async):
            if added and self.chroma_manager:
                origem_nome = (self.data_manager.get_entity_details_by_canonical_id('locais', acesso['origem_id']) or {}).get('nome', acesso['origem_id'])
                destino_nome = (self.data_manager.get_entity_details_by_canonical_id('locais', acesso['destino_id']) or {}).get('nome', acesso['destino_id'])
                text_content = f"Acesso direto entre {origem_nome} e {destino_nome}. Tipo: {acesso['tipo_acesso']}. Condições: {acesso['condicoes_acesso']}."
                metadata = {"id_canonico": f"acesso_{acesso['origem_id']}_{acesso['destino_id']}", "tipo": "acesso_direto", "origem": acesso['origem_id'], "destino": acesso['destino_id']}
                await self.chroma_manager.add_or_update_lore(f"acesso_{acesso['origem_id']}_{acesso['destino_id']}", text_content, metadata)


        # 4. Exemplo de uso de add_or_get_element_universal (SQLite e ChromaDB)
        print("\n--- Demonstração: Adicionando/Verificando Elementos Universais ---")
        elementos_iniciais = [
            {'id_canonico': 'tec_motor_dobra', 'nome': 'Motor de Dobra Warp 7', 'tipo_nome': 'Tecnologia', 'perfil_json_data': {'funcao': 'Propulsão FTL', 'velocidade': 'Warp 7'}},
            {'id_canonico': 'rec_cristal_mana', 'nome': 'Cristal de Mana Bruto', 'tipo_nome': 'Recurso', 'perfil_json_data': {'raridade': 'Comum', 'uso': 'Fonte de energia mágica'}}
        ]
        for elem_data in elementos_iniciais:
            # DataManager.add_or_get_element_universal é SÍNCRONO.
            element_id = self.data_manager.add_or_get_element_universal(
                elem_data['id_canonico'],
                elem_data['nome'],
                elem_data['tipo_nome'],
                elem_data['perfil_json_data']
            )
            # ORQUESTRAÇÃO DO CHROMADB (async):
            if element_id and self.chroma_manager:
                text_content = f"Elemento Universal: {elem_data['nome']}. Tipo: {elem_data['tipo_nome']}. Detalhes: {json.dumps(elem_data['perfil_json_data'], ensure_ascii=False)}"
                metadata = {"id_canonico": elem_data['id_canonico'], "tipo": "elemento_universal", "nome": elem_data['nome'], "subtipo": elem_data['tipo_nome']}
                await self.chroma_manager.add_or_update_lore(elem_data['id_canonico'], text_content, metadata)
        print("------------------------------------------------------------------")

        # 5. Criar o personagem (Gabriel) - SQLite e ChromaDB
        player_profile = {
            "raca": "Humano",
            "idade": 28,
            "ocupacao": "Explorador Independente",
            "personalidade": "Curioso, aventureiro.",
            "creditos_conta": 500
        }
        # DataManager.add_player é SÍNCRONO.
        player_id = self.data_manager.add_player(player_id_canonico, player_name, initial_location_id_canonico, player_profile)

        if player_id:
            # 6. Adicionar status inicial do jogador (SQLite e ChromaDB)
            # Esses métodos add_player_* são SÍNCRONOS no DataManager.
            self.data_manager.add_player_vitals(player_id_canonico, timestamp_atual=current_timestamp)
            self.data_manager.add_player_skill(player_id_canonico, 'Exploração', 'Navegação Espacial', 'Novato')
            
            # Posse também precisa de orquestração do ChromaDB
            posse_id_canonico = f"kit_sobrevivencia_{player_id_canonico}"
            self.data_manager.add_player_possession(player_id_canonico, 'Kit de Sobrevivência', posse_id_canonico, {'estado': 'novo', 'itens': ['ração', 'água', 'ferramentas']})
            # ORQUESTRAÇÃO DO CHROMADB (async) para posse:
            if self.chroma_manager:
                text_content = f"Posse: Kit de Sobrevivência (ID: {posse_id_canonico}). Detalhes: {json.dumps({'estado': 'novo', 'itens': ['ração', 'água', 'ferramentas']}, ensure_ascii=False)}. Pertence a: {player_id_canonico}."
                metadata = {"id_canonico": posse_id_canonico, "tipo": "posse", "nome": 'Kit de Sobrevivência', "jogador": player_id_canonico}
                await self.chroma_manager.add_or_update_lore(posse_id_canonico, text_content, metadata)

            # Log/Memória (SQLite, não precisa de ChromaDB no add_log_memory, mas você pode adicionar se quiser o log na memória vetorial)
            self.data_manager.add_log_memory(player_id_canonico, 'log_evento', 'Campanha iniciada.', timestamp_evento=current_timestamp)
            
            print("INFO: Campanha inicial configurada com sucesso!")
        else:
            print("ERRO: Falha ao configurar a campanha inicial.")

        # ATENÇÃO: build_collection_from_sqlite() NÃO será chamado aqui.
        # Ele será chamado pelo sync_databases.py para sincronização em lote.
        print("\nAVISO: A população inicial em lote do ChromaDB será realizada pelo 'sync_databases.py'.")
        print("AVISO: Este script (main.py) agora apenas adiciona dados incrementais ao ChromaDB.")


    async def obter_contexto_atual(self): # Continua sendo async
        """
        Usa o DataManager e o ChromaDBManager para obter um snapshot completo do estado atual do jogo.
        """
        print("\n--- A obter contexto para o turno atual... ---")
        contexto = {}
        
        # 1. Obter o estado completo do jogador (este método no DataManager é síncrono)
        JOGADOR_ID_CANONICO = config.DEFAULT_PLAYER_ID_CANONICO
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

        # 3. Obter os detalhes completos do local atual (este método no DataManager é síncrono)
        contexto['local_atual'] = self.data_manager.get_entity_details_by_canonical_id('locais', local_id_canonico)
        if not contexto['local_atual']:
            print(f"ERRO: Detalhes do local não encontrados para o ID canónico {local_id_canonico}.")
            return None
        # O perfil_json vem como string, precisamos parsear para usar
        contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual']['perfil_json'])


        # 4. Obter o resto do contexto usando o ID numérico (estes métodos no DataManager são síncronos)
        contexto['caminho_local'] = self.data_manager.get_ancestors(local_id_numerico)
        contexto['locais_contidos'] = self.data_manager.get_children(local_id_numerico)
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
        """
        Formata o dicionário de contexto num prompt de texto para o LLM.
        Otimizado para reduzir a verbosidade em listas.
        """
        
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
        
        # Processar perfil_completo_json
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
        # A chave de API será lida do config.py que, por sua vez, lê da variável de ambiente GEMINI_API_KEY.
        apiKey = config.GEMINI_API_KEY 
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GENERATIVE_MODEL}:generateContent?key={apiKey}";
        

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
                    response_text = await response.text()
                    print(f"ERRO: Falha na API do LLM com status {response.status}: {response_text}")
                    if "403" in str(response_text) or "PERMISSION_DENIED" in str(response_text):
                        print("DICA: Verifique se sua GEMINI_API_KEY está correta e tem permissões para o modelo generativo.")
                    elif "429" in str(response_text) or "Resource has been exhausted" in str(response_text):
                         print("DICA: Você atingiu o limite de cota da API. Aguarde um pouco e tente novamente, ou verifique/aumente suas cotas.")
                    return "Uma interferência cósmica impede a clareza."
        except Exception as e:
            print(f"ERRO ao chamar a API do LLM: {e}")
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado."

    async def executar_turno_de_jogo(self, session, acao_do_jogador=""):
        """Simula um único turno do jogo de forma assíncrona."""
        contexto = await self.obter_contexto_atual()
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
    # NOVO: Caminho para o build_world.py ajustado para a nova estrutura de pastas
    build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py') # Usa config.BASE_DIR
    
    # 1. Executar build_world.py para garantir o esquema vazio
    if os.path.exists(build_script_path):
        print(f"Executando '{build_script_path}' para criar o esquema do DB...")
        os.system(f'python "{build_script_path}"')
    else:
        print(f"ERRO: Script 'build_world.py' não encontrado em '{build_script_path}'.")
        sys.exit(1)
    
    agente_mj = AgenteMJ()

    async with aiohttp.ClientSession() as session:
        # 2. Configurar a campanha inicial (criação do personagem e primeiro local)
        await agente_mj._setup_initial_campaign(
            player_id_canonico=config.DEFAULT_PLAYER_ID_CANONICO, # Usa config.DEFAULT_PLAYER_ID_CANONICO
            player_name='Gabriel Oliveira',
            initial_location_id_canonico=config.DEFAULT_INITIAL_LOCATION_ID_CANONICO # Usa config.DEFAULT_INITIAL_LOCATION_ID_CANONICO
        )

        # Agora, o jogo pode começar com o turno
        await agente_mj.executar_turno_de_jogo(session, acao_do_jogador="Olho para o terminal à minha frente, tentando entender a nova anomalia.")


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())

