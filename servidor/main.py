import os
import sys
import json
import datetime
import asyncio
import aiohttp
import inspect 
import time

# Adiciona o diretório da raiz do projeto ao sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config')) # Para importar config
sys.path.append(os.path.join(PROJECT_ROOT, 'servidor')) # Para importar managers
sys.path.append(os.path.join(PROJECT_ROOT, 'agents')) # Para importar os novos agentes

# Importar as configurações globais
import config as config 

# Importar os gestores dos pilares
from data_manager import DataManager
from chromadb_manager import ChromaDBManager
from neo4j_manager import Neo4jManager 

# Importar os novos agentes
from sqlite_agent import SQLiteAgent 
from mj_agent import MJAgent 
from chromadb_agent import ChromaDBAgent 
from neo4j_agent import Neo4jAgent 

class AgenteMJ:
    """
    O cérebro do Mestre de Jogo (v2.36).
    Responsável por gerir o estado do jogo e interagir com o LLM.
    AGORA ATUA COMO ORQUESTRADOR DIRETO DAS ATUALIZAÇÕES DOS PILARES (SQLite + ChromaDB + Neo4j) EM TEMPO REAL.
    (Change: Adicionada verificação de jogador existente para um início mais inteligente.
             Versão: 2.36)
    """
    def __init__(self):
        """
        Inicializa o AgenteMJ e as conexões com os gestores dos pilares.
        """
        self.data_manager = DataManager() 
        self.chroma_manager = ChromaDBManager()
        self.neo4j_manager = Neo4jManager() 
        self.sqlite_agent = SQLiteAgent()
        self.mj_agent = MJAgent() 
        self.chromadb_agent = ChromaDBAgent() 
        self.neo4j_agent = Neo4jAgent() 

    async def obter_contexto_atual(self): 
        """
        Usa o DataManager e o ChromaDBManager para obter um snapshot completo do estado atual do jogo.
        Adaptado para um cenário de "folha em branco" onde o jogador pode não existir inicialmente.
        """
        contexto = {}
        
        JOGADOR_ID_CANONICO = config.DEFAULT_PLAYER_ID_CANONICO 
        estado_jogador = self.data_manager.get_player_full_status(JOGADOR_ID_CANONICO) 
        
        if not estado_jogador:
            # Contexto para um mundo que ainda não foi criado pelo LLM
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
        
        local_id_canonico = estado_jogador['base'].get('local_id_canonico')
        local_id_numerico = estado_jogador['base'].get('local_id')

        if not local_id_canonico or not local_id_numerico:
            contexto['local_atual'] = {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}}
            contexto['caminho_local'] = []
            contexto['locais_contidos'] = []
            contexto['locais_acessos_diretos'] = []
            contexto['locais_vizinhos'] = []
        else:
            contexto['local_atual'] = self.data_manager.get_entity_details_by_canonical_id('locais', local_id_canonico)
            if not contexto['local_atual']:
                contexto['local_atual'] = {'id_canonico': 'o_vazio_inicial', 'nome': 'O Vazio', 'tipo': 'Espaço', 'perfil_json': {"descricao": "Um vazio sem forma, aguardando a criação de um universo."}}
            else:
                contexto['local_atual']['perfil_json'] = json.loads(contexto['local_atual'].get('perfil_json') or '{}')

            contexto['caminho_local'] = self.data_manager.get_ancestors(local_id_numerico)
            contexto['locais_contidos'] = self.data_manager.get_children(local_id_numerico)
            contexto['locais_acessos_diretos'] = self.data_manager.get_direct_accesses(local_id_numerico) 
            contexto['locais_vizinhos'] = self.data_manager.get_siblings(local_id_numerico)
        
        query_rag = f"Descreva o local {contexto['local_atual']['nome']} (tipo: {contexto['local_atual'].get('tipo', 'Desconhecido')}) e o que há de interessante ou perigoso nele."
        relevante_lore = await self.chroma_manager.find_relevant_lore(query_rag, n_results=3)
        contexto['lore_relevante'] = [r['document'] for r in relevante_lore]
        
        return contexto

    async def _process_tool_calls(self, session, tool_calls_from_llm):
        """
        Processa e executa as chamadas de ferramenta (funções) geradas por um LLM,
        e orquestra as atualizações em ChromaDB e Neo4j.
        """
        tool_responses_parts = []
        table_name_map = {
            "add_or_get_location": "locais",
            "add_or_get_player": "jogador",
            "add_or_get_element_universal": "elementos_universais",
            "add_or_get_personagem": "personagens",
            "add_or_get_faccao": "faccoes",
            "add_or_get_player_possession": "jogador_posses"
        }
        available_functions_dm = {
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
            "add_new_entity_type": self.data_manager.add_new_entity_type,
            "add_or_update_lore": self.chroma_manager.add_or_update_lore,
            "add_or_update_parent_child_relation": self.neo4j_manager.add_or_update_parent_child_relation,
        }

        for tc in tool_calls_from_llm:
            function_call = tc["functionCall"]
            function_name = function_call["name"]
            function_args = function_call.get("args", {})
            
            if function_name in available_functions_dm:
                func_to_call = available_functions_dm[function_name]
                
                processed_args = {}
                for k, v in function_args.items():
                    if isinstance(v, str) and (k.endswith('_json_data') or k.endswith('_data') or k == 'metadata'):
                        try:
                            processed_args[k] = json.loads(v)
                        except json.JSONDecodeError:
                            processed_args[k] = v
                    else:
                        processed_args[k] = v
                
                processed_args['__function_name__'] = function_name

                try:
                    if asyncio.iscoroutinefunction(func_to_call):
                        function_response = await func_to_call(**processed_args)
                    else:
                        function_response = func_to_call(**processed_args)
                    
                    if function_name in table_name_map and function_response not in [None, False]: 
                        id_canonico_to_sync = processed_args.get("id_canonico") or processed_args.get("player_canonical_id") 
                        table_name = table_name_map.get(function_name)
                        
                        if id_canonico_to_sync and table_name:
                            await self._sync_pillars_for_entity(id_canonico_to_sync, table_name, processed_args)

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    function_response = f"ERRO: {e}" 
                
                tool_responses_parts.append({
                    "functionResponse": {
                        "name": function_name,
                        "response": {"result": str(function_response)}
                    }
                })
        return tool_responses_parts
    
    async def _sync_pillars_for_entity(self, id_canonico, table_name, processed_args):
        """Sincroniza ChromaDB e Neo4j para uma entidade recém-criada/atualizada."""
        entity_details = self.data_manager.get_entity_details_by_canonical_id(table_name, id_canonico)
        if not entity_details:
            return

        text_content, metadata = self._prepare_chroma_data(entity_details, table_name, processed_args)
        if text_content:
            await self.chroma_manager.add_or_update_lore(id_canonico, text_content, metadata)

        await self._update_neo4j_graph(entity_details, table_name, processed_args)

    def _prepare_chroma_data(self, entity_details, table_name, processed_args):
        """Prepara os dados para o ChromaDB."""
        text_content = ""
        metadata = {"id_canonico": entity_details['id_canonico'], "tipo": table_name}
        nome = entity_details.get('nome', '')
        tipo = entity_details.get('tipo', 'Desconhecido')
        perfil = json.loads(entity_details.get('perfil_json') or entity_details.get('perfil_completo_json') or '{}')

        if table_name == "locais":
            text_content = f"Local: {nome}. Tipo: {tipo}. Descrição: {perfil.get('descricao', 'N/A')}."
        elif table_name == "jogador":
            text_content = f"O Jogador principal: {nome}. Raça: {perfil.get('raca', 'N/A')}. Ocupação: {perfil.get('ocupacao', 'N/A')}."
        
        metadata.update({"nome": nome, "subtipo": tipo})
        return text_content, metadata

    async def _update_neo4j_graph(self, entity_details, table_name, processed_args):
        """Atualiza o grafo Neo4j com base na entidade e nos argumentos da função."""
        neo4j_label_map = {
            "locais": "Local", "jogador": "Jogador", "elementos_universais": "ElementoUniversal",
            "personagens": "Personagem", "faccoes": "Faccao",
        }
        base_label = neo4j_label_map.get(table_name)
        if not base_label:
            return

        node_properties = {k: v for k, v in entity_details.items() if isinstance(v, (str, int, float, bool))}
        self.neo4j_manager.add_or_update_node(
            id_canonico=entity_details['id_canonico'], label_base=base_label,
            properties=node_properties, main_label=entity_details.get('tipo', '').replace(" ", "")
        )

        function_name = processed_args.get('__function_name__')
        if function_name == "add_or_get_location" and processed_args.get("parent_id_canonico"):
            self.neo4j_manager.add_or_update_parent_child_relation(entity_details['id_canonico'], processed_args["parent_id_canonico"])
        elif function_name == "add_or_get_player" and processed_args.get("local_inicial_id_canonico"):
            self.neo4j_manager.add_or_update_player_location_relation(entity_details['id_canonico'], processed_args["local_inicial_id_canonico"])

    async def _chamar_llm(self, session, prompt, tools_declarations, available_functions_map, model_name, chat_history_context=None):
        """
        Envia um prompt para a API do LLM usando aiohttp e retorna a resposta.
        """
        if chat_history_context is None:
            chat_history_context = [{"role": "user", "parts": [{"text": prompt}]}]
        
        payload = {"contents": chat_history_context, "tools": tools_declarations}
        apiKey = config.GEMINI_API_KEY 
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={apiKey}"
        
        try:
            async with session.post(apiUrl, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get("candidates"):
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            
                            tool_calls = [part for part in parts if "functionCall" in part]
                            if tool_calls:
                                tool_responses = await self._process_tool_calls(session, tool_calls)
                                chat_history_context.append({"role": "model", "parts": tool_calls})
                                chat_history_context.append({"role": "user", "parts": tool_responses})
                                
                                response_after_tools = await session.post(apiUrl, json={"contents": chat_history_context, "tools": tools_declarations}, headers={'Content-Type': 'application/json'})
                                
                                if response_after_tools.status == 200:
                                    final_result = await response_after_tools.json()
                                    if final_result.get("candidates"):
                                        final_candidate = final_result["candidates"][0]
                                        if "content" in final_candidate and "parts" in final_candidate["content"]:
                                            final_parts = final_candidate["content"]["parts"]
                                            text_part = next((p["text"] for p in final_parts if "text" in p), None)
                                            return (text_part or "").strip(), final_result
                                return "O LLM não conseguiu gerar uma resposta narrativa coerente.", {}
                            
                            text = (parts[0].get("text") or "")
                            return text.strip(), result 
                
                response_text = await response.text()
                print(f"ERRO: Falha na API do LLM ({model_name}) com status {response.status}: {response_text}")
                return "Uma interferência cósmica impede a clareza.", {}
        except Exception as e:
            import traceback
            traceback.print_exc() 
            return "Uma interferência cósmica impede a clareza. A sua ação parece não ter resultado.", {}

    async def executar_turno_de_jogo(self, session, acao_do_jogador=""):
        """Simula um único turno do jogo de forma assíncrona."""
        print("\n\033[1;36m--- Obtendo contexto para o turno... ---\033[0m")
        contexto = await self.obter_contexto_atual()
        
        print("\033[1;36m--- Mestre de Jogo está a pensar... ---\033[0m")
        prompt_narrativa = self.mj_agent.format_prompt(contexto, acao_do_jogador)
        main_llm_tools = self.mj_agent.get_tool_declarations()
        narrativa_mj, _ = await self._chamar_llm(session, prompt_narrativa, main_llm_tools, {}, config.GENERATIVE_MODEL)
        
        print("\n\033[1;35m--- RESPOSTA DO MESTRE DE JOGO ---\033[0m\n" + narrativa_mj)

        print("\n\033[1;36m--- Agentes de IA estão a analisar a narrativa para atualizar o mundo... ---\033[0m")
        prompts_agentes = {
            "SQLite": (self.sqlite_agent.format_prompt(narrativa_mj, contexto), self.sqlite_agent.get_tool_declarations()),
            "ChromaDB": (self.chromadb_agent.format_prompt(narrativa_mj, contexto), self.chromadb_agent.get_tool_declarations()),
            "Neo4j": (self.neo4j_agent.format_prompt(narrativa_mj, contexto), self.neo4j_agent.get_tool_declarations()),
        }
        
        tasks = []
        for nome_agente, (prompt, tools) in prompts_agentes.items():
            task = self._chamar_llm(session, prompt, tools, {}, config.AGENT_GENERATIVE_MODEL)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        print("\033[1;32m--- Atualização do mundo concluída. ---\033[0m")
        return narrativa_mj 

def show_detailed_loading_screen():
    """Exibe uma animação de carregamento mais detalhada e bonita."""
    steps = [
        ("Conectando ao Pilar B (SQLite)", 0.5),
        ("Conectando ao Pilar A (ChromaDB)", 0.7),
        ("Conectando ao Pilar C (Neo4j)", 0.6),
        ("Acordando Agentes de IA...", 1.0),
    ]
    
    print("\n\033[1;34m===========================================\033[0m")
    print("\033[1;34m=    INICIANDO SIMULAÇÃO DE UNIVERSO    =\033[0m")
    print("\033[1;34m===========================================\033[0m\n")
    
    for i, (step, duration) in enumerate(steps):
        sys.stdout.write(f"  \033[1;36m[ ]\033[0m {step}")
        sys.stdout.flush()
        
        # Animação de pontos
        for _ in range(int(duration * 10)):
            time.sleep(0.1)
            sys.stdout.write(".")
            sys.stdout.flush()
        
        sys.stdout.write(f"\r  \033[1;32m[✓]\033[0m {step} - Concluído\n")
        time.sleep(0.2)
        
    print("\n\033[1;32mSISTEMA PRONTO. BEM-VINDO AO UNIVERSO!\033[0m")
    print("\033[1;34m===========================================\033[0m\n")


# --- Ponto de Entrada Principal ---
async def main():
    """Função principal assíncrona para executar o servidor do jogo."""
    
    # PASSO 1: Garantir que o arquivo da base de dados exista.
    db_path = config.DB_PATH_SQLITE
    if not os.path.exists(db_path):
        print("--- Arquivo de banco de dados não encontrado. Criando esquema inicial... ---")
        build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py') 
        if os.path.exists(build_script_path):
            os.system(f'python "{build_script_path}"')
        else:
            print(f"ERRO CRÍTICO: Script 'build_world.py' não encontrado em '{build_script_path}'.")
            sys.exit(1)

    # PASSO 2: Verificar se um jogo está em andamento (se existe um jogador)
    # A inicialização do DataManager é leve e segura após o passo 1.
    temp_data_manager = DataManager()
    existing_players = temp_data_manager.get_all_entities_from_table('jogador')
    is_new_game = not existing_players
    del temp_data_manager # Libera o objeto temporário

    if is_new_game:
        print("--- Nenhum jogo salvo detectado. Preparando para um novo universo... ---")
    else:
        print("--- Jogo salvo encontrado. Carregando universo... ---")
    
    # PASSO 3: Inicializar o sistema principal com feedback visual
    agente_mj = None
    try:
        initialization_task = asyncio.to_thread(AgenteMJ)
        loading_task = asyncio.create_task(asyncio.to_thread(show_detailed_loading_screen))
        
        agente_mj = await initialization_task
        await loading_task

    except Exception as e:
        print("\n\n\033[1;31m=======================================\033[0m")
        print("\033[1;31m=   ERRO CRÍTICO DURANTE A INICIALIZAÇÃO   =\033[0m")
        print("\033[1;31m=======================================\033[0m")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # PASSO 4: Iniciar o loop do jogo com a mensagem de boas-vindas correta
    async with aiohttp.ClientSession() as session:
        if is_new_game:
            print("--- O MUNDO É UMA FOLHA EM BRANCO. ---")
            print("    O Mestre de Jogo irá criar o seu personagem e o local inicial.")
            print("    Para começar, apenas pressione Enter ou descreva o que você gostaria de ser.")
        else:
            player_context = await agente_mj.obter_contexto_atual()
            player_name = player_context.get('jogador', {}).get('base', {}).get('nome', 'Aventureiro')
            print(f"\033[1;32m--- Bem-vindo de volta, {player_name}. Continue sua jornada. ---\033[0m")

        while True:
            try:
                acao_do_jogador = await asyncio.to_thread(input, "\n\033[1;33mSua ação: \033[0m")
                if acao_do_jogador.lower() in ['sair', 'exit', 'quit']:
                    print("Encerrando a simulação...")
                    break
                
                await agente_mj.executar_turno_de_jogo(session, acao_do_jogador)
            except KeyboardInterrupt:
                print("\nSimulação interrompida pelo utilizador. Adeus!")
                break
            except Exception as e:
                print("\n\033[1;31mOcorreu um erro inesperado no loop do jogo:\033[0m")
                import traceback
                traceback.print_exc()


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
