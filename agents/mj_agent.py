import json
import datetime

class MJAgent:
    """
    Agente de IA principal (Mestre de Jogo) responsável exclusivamente pela geração da narrativa.
    Versão: 2.2.0 - O prompt inicial foi generalizado para suportar uma criação de mundo interativa ou automática.
    """

    def __init__(self):
        print("INFO: MJAgent (Narrador Puro v2.2) inicializado.")

    def format_prompt(self, contexto, acao_do_jogador):
        """
        Formata o dicionário de contexto num prompt de texto para o LLM principal (narrativa).
        """
        
        # --- Bloco de Instrução para Criação de Mundo (se aplicável) ---
        player_creation_instruction = ""
        if contexto['jogador']['base']['nome'] == 'Aguardando Criação':
            player_creation_instruction = f"""
# INSTRUÇÃO CRÍTICA: INÍCIO DO JOGO - MODO DE CRIAÇÃO
O jogo está começando. Você é o Mestre da Criação. Sua primeira tarefa é interagir com o jogador para criar o personagem e o mundo, ou criar uma história por conta própria.

**Cenário 1: O jogador quer participar da criação.**
- A ação do jogador pode ser uma descrição ("quero ser um mago em um mundo de fantasia") ou uma pergunta.
- Sua função é conversar. Faça perguntas para refinar a ideia. Ex: "Interessante! Como você se chama?", "Como é esse mundo de fantasia?".

**Cenário 2: O jogador quer ser surpreendido.**
- A ação do jogador será algo como "surpreenda-me", "comece o jogo" ou um simples Enter.
- Neste caso, use sua total liberdade criativa. Narre o despertar do personagem, descreva o ambiente inicial (planeta, estação espacial, etc.), dê um nome ao local e ao personagem. Crie uma introdução rica e envolvente.

**IMPORTANTE:** Sua única função é narrar ou dialogar. O 'Agente Arquiteto' irá ler sua resposta e criar as entidades no banco de dados. Foque apenas na história.

**Ação Inicial do Jogador:** "{acao_do_jogador}"
"""
        else:
            player_creation_instruction = f"""
# AÇÃO DO JOGADOR
"{acao_do_jogador}"
"""

        # --- Diretrizes Gerais de Narração ---
        diretrizes_narracao = """
        Diretrizes de Narração:
        - Narrativa Fluida e Ações (Sem Opções Numeradas): A história segue de forma natural com as decisões do personagem.
        - Descrições Opcionais: Descrições de ambientes são omitidas, a menos que solicitadas.
        - Progresso Implícito: O progresso em habilidades é comunicado de maneira narrativa, não de forma técnica.
        - Imersão Total: O jogador vivencia o mundo através dos sentidos e limitações do personagem.
        """
        
        # --- Funções Auxiliares para Formatação do Contexto ---
        def format_vitals(vitals):
            if not vitals: return "N/A"
            return ", ".join([f"{key.capitalize()}: {value}" for key, value in vitals.items() if key not in ['id', 'jogador_id', 'timestamp_atual']])

        def format_list(items, name_key, details_map):
            if not items: return "Nenhum(a)."
            lines = []
            for item in items:
                name = item.get(name_key, "N/A")
                details = []
                for key, label in details_map.items():
                    value = item.get(key)
                    if value:
                        details.append(f"{label}: {value}")
                details_str = f"({', '.join(details)})" if details else ""
                lines.append(f"- {name} {details_str}")
            return "\n".join(lines)

        def format_possessions(items):
            if not items: return "Nada."
            lines = []
            for item in items:
                name = item.get('item_nome', 'Item Desconhecido')
                try:
                    profile = json.loads(item.get('perfil_json', '{}')) if item.get('perfil_json') else {}
                    details_str = f"({', '.join([f'{k}: {v}' for k, v in profile.items()])})" if profile else ""
                    lines.append(f"- {name} {details_str}")
                except (json.JSONDecodeError, TypeError):
                    lines.append(f"- {name}")
            return "\n".join(lines)

        # --- Extração e Formatação do Contexto ---
        jogador_base = contexto['jogador']['base']
        local_atual = contexto['local_atual']
        
        try:
            perfil_jogador = json.loads(jogador_base.get('perfil_completo_json', '{}')) if jogador_base.get('perfil_completo_json') else {}
        except (json.JSONDecodeError, TypeError):
            perfil_jogador = {}

        lore_relevante_str = "\n".join([f"- {doc}" for doc in contexto['lore_relevante']]) if contexto.get('lore_relevante') else "Nenhuma informação adicional relevante."

        # --- Montagem Final do Prompt ---
        prompt = f"""
# ORDENS DO MESTRE
Você é um Mestre de Jogo de um RPG de texto. Sua função é descrever o resultado das ações do jogador ou conduzir a criação do mundo de forma narrativa, coesa e criativa. O cenário do jogo é genérico e pode se adaptar a qualquer gênero.

# DIRETRIZES DE NARRAÇÃO
{diretrizes_narracao}

# ESTADO ATUAL DO MUNDO
## Jogador: {jogador_base.get('nome', 'N/A')} ({jogador_base.get('id_canonico', 'N/A')})
- **Perfil:** {json.dumps(perfil_jogador, ensure_ascii=False)}
- **Estado Físico e Emocional:** {format_vitals(contexto['jogador']['vitals'])}
- **Habilidades:**
{format_list(contexto['jogador']['habilidades'], 'nome', {'categoria': 'Cat.', 'nivel_subnivel': 'Nível'})}
- **Conhecimentos:**
{format_list(contexto['jogador']['conhecimentos'], 'nome', {'categoria': 'Cat.', 'nivel': 'Nível'})}
- **Posses:**
{format_possessions(contexto['jogador']['posses'])}

## Ambiente
- **Localização:** {' -> '.join([l['nome'] for l in reversed(contexto.get('caminho_local', []))]) if contexto.get('caminho_local') else local_atual.get('nome', 'Desconhecida')}
- **Descrição do Local ({local_atual.get('nome', 'N/A')}):** {local_atual.get('perfil_json', {}).get('descricao', 'Nenhuma descrição disponível.')}
- **Locais Contidos:** {[l['nome'] for l in contexto.get('locais_contidos', [])] or 'Nenhum'}
- **Acessos Diretos:** {[a['nome'] for a in contexto.get('locais_acessos_diretos', [])] or 'Nenhum'}

## Memória Recente (Lore Relevante)
{lore_relevante_str}

{player_creation_instruction}

# SUA RESPOSTA
Agora, narre o resultado ou continue a conversa de criação. Seja descritivo, envolvente e avance a história.
"""
        return prompt

    def get_tool_declarations(self):
        """
        O Mestre de Jogo não possui mais ferramentas de escrita. Sua única função é narrar.
        """
        return None
