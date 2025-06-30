import json
import datetime
from config import config

class MJAgent:
    """
    Agente de IA principal (Mestre de Jogo) responsável pela geração da narrativa
    e pelas ações diretas que moldam o início do mundo e o estado básico do jogador.
    (Versão: 1.2.0 - Instrução de prompt atualizada para que a IA crie o ID do jogador.)
    """

    def __init__(self):
        print("INFO: MJAgent principal inicializado (v1.2.0).")

    def format_prompt(self, contexto, acao_do_jogador):
        """
        Formata o dicionário de contexto num prompt de texto para o LLM principal (narrativa).
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

        player_creation_instruction = ""
        if jogador_base['nome'] == 'Aguardando Criação':
            player_creation_instruction = f"""
# INSTRUÇÃO CRÍTICA PARA CRIAÇÃO DO MUNDO (Se o Jogador não existir):
O jogo está começando do zero. Seu objetivo é estabelecer o ponto de partida da aventura.
Você DEVE realizar as seguintes ações, usando as funções do DataManager (via Function Calling):
1. Crie um local inicial (add_or_get_location). Dê a ele um nome, um 'tipo' (STRING LIVRE, ex: 'Planeta Verdejante', 'Estação de Mineração Abandonada') e uma descrição em 'perfil_json_data'. Crie um 'id_canonico' único para o local (ex: 'local_floresta_sombria').
2. Crie o personagem do jogador (add_or_get_player). Crie um 'id_canonico' único e descritivo para ele (ex: 'pj_kael_o_explorador', 'personagem_lyra_a_nomade'). Dê a ele um nome, um perfil completo em 'perfil_completo_data' (raça, ocupação, personalidade) e vincule-o ao 'id_canonico' do local que você acabou de criar.
Após a criação, inicie a narrativa descrevendo o ambiente e o que o jogador percebe.
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

    def get_tool_declarations(self):
        """
        Retorna as declarações de ferramentas (funções do DataManager)
        que o LLM principal pode chamar.
        """
        return [
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
                            "id_canonico": {"type": "string", "description": "ID canônico único e criativo para o jogador (ex: 'pj_kael_o_explorador')."},
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
                }
            ]}
        ]
