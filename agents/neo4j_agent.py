import json
import datetime
import os
import sys

# Adiciona o diretório raiz do projeto ao sys.path para que o config possa ser importado
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
import config as config

class Neo4jAgent:
    """
    Agente de IA especializado em gerenciar as relações e a estrutura de grafo (Neo4j).
    (Versão: 1.2.0)
    Responsabilidade: Gerar o prompt e as declarações de ferramentas para que um LLM
    possa analisar a narrativa e criar/atualizar relações entre entidades no Neo4j.
    (Change: Adicionadas diretrizes mais estritas para evitar inferências de movimento incorretas.)
    """

    def __init__(self):
        print("INFO: Neo4jAgent inicializado (v1.2.0).")

    def format_prompt(self, narrative_mj, contexto):
        """
        Formata um prompt detalhado para a IA do Neo4j, instruindo-a a identificar
        e estruturar relações entre entidades.
        """
        # Contexto simplificado, focando em IDs e tipos de entidades existentes para facilitar a criação de relações
        # É crucial que esta IA saiba dos IDs canônicos existentes.
        jogador_info_simples = {
            'id_canonico': contexto['jogador']['base']['id_canonico'],
            'nome': contexto['jogador']['base']['nome'],
            'local_atual_id_canonico': contexto['jogador']['base'].get('local_id_canonico', 'N/A')
        }
        local_atual_info_simples = {
            'id_canonico': contexto['local_atual']['id_canonico'],
            'nome': contexto['local_atual']['nome'],
            'tipo': contexto['local_atual']['tipo']
        }
        locais_contidos_simples = [{'id_canonico': l['id_canonico'], 'nome': l['nome'], 'tipo': l['tipo']} for l in contexto['locais_contidos']]
        locais_acessos_diretos_simples = [{'id_canonico': a['id_canonico'], 'nome': a['nome'], 'tipo': a['tipo'], 'tipo_acesso': a.get('tipo_acesso')} for a in contexto['locais_acessos_diretos']]
        locais_vizinhos_simples = [{'id_canonico': l['id_canonico'], 'nome': l['nome'], 'tipo': l['tipo']} for l in contexto['locais_vizinhos']]

        # Também pode ser útil passar alguns exemplos de outras entidades (personagens, elementos, facções)
        # se o DataManager expor um método para obtê-las de forma resumida para contexto.
        # Por simplicidade inicial, focamos no jogador e locais que são mais dinâmicos no turno.

        return f"""
        # INSTRUÇÃO PARA AGENTE DE GRAFO DE DADOS (Neo4j AI)
        Você é um agente de inteligência artificial especializado em analisar narrativas de RPG para atualizar um grafo de dados (Neo4j). Sua tarefa é identificar relações espaciais, hierárquicas e de acesso entre entidades.

        **Seu objetivo principal é GARANTIR que o Neo4j reflita com precisão as CONEXÕES e a ESTRUTURA do mundo.**

        **DIRETRIZES CRÍTICAS:**
        1.  **REGRA DE OURO - NÃO INVENTE MOVIMENTO:** A localização do jogador fornecida no contexto (`local_atual_id_canonico`) é a **verdade absoluta**. Você SÓ DEVE chamar `update_player_location` se a narrativa descrever uma ação **explícita e inequívoca** de movimento (ex: "ele caminhou para a sala ao lado", "ela entrou no laboratório", "a nave viajou para o sistema Beta"). Descrições do ambiente, como "ele estava cercado por escombros" ou "a sala era grande", **NÃO SÃO UM MOVIMENTO** e não devem acionar `update_player_location`.
        2.  **FOCO EM MAPEAMENTO, NÃO EM RASTREAMENTO:** Sua principal responsabilidade é criar o mapa de relações (`DENTRO_DE`, `DA_ACESSO_A`) entre as entidades que o `Agente SQLite` já criou. Você é um cartógrafo, não um rastreador GPS.
        3.  **HIERARQUIA DE AGENTES:** O `Agente SQLite` cria os "lugares" (nós do grafo). Você desenha as "estradas" (relações/arestas) entre eles. Antes de tentar criar uma relação, você deve assumir que o Agente SQLite já fez o seu trabalho e criou os nós necessários.
        4.  **NÃO USE '[desconhecido]':** NUNCA tente criar uma relação de ou para um `id_canonico` literal de '[desconhecido]'. Se o destino de uma passagem não for claro na narrativa, o `Agente SQLite` é responsável por criar um local "placeholder". Você deve aguardar que esse `id_canonico` exista para então criar a relação. Se você não tem um `id_canonico` válido, não faça nada.
        5.  **RELAÇÕES DE LOCALIZAÇÃO:**
            * `add_or_update_parent_child_relation`: Use para relações de *contimento* (ex: uma `sala_contencao` DENTRO_DE `escombros_base_pesquisa`).
            * `add_direct_access_relation`: Use para relações de *passagem/conexão* (ex: um `corredor` DA_ACESSO_A uma `sala`).
        6.  **RELAÇÕES UNIVERSAIS (`add_universal_relation`):** Use para qualquer outra conexão significativa (ex: `pj_gabriel_oliveira` INTERAGIU_COM `simbionte_tecnologico`).
        7.  **SÓ RESPONDA COM CHAMADAS DE FUNÇÃO:** Se a narrativa não fornecer informações claras para criar ou atualizar uma relação, não responda nada.

        **Contexto Atual do Jogo (Para Referência - Entidades Existentes):**
        - Jogador Principal: {json.dumps(jogador_info_simples, ensure_ascii=False)}
        - Local Atual: {json.dumps(local_atual_info_simples, ensure_ascii=False)}
        - Locais Contidos no Local Atual: {json.dumps(locais_contidos_simples, ensure_ascii=False)}
        - Acessos Diretos do Local Atual: {json.dumps(locais_acessos_diretos_simples, ensure_ascii=False)}
        - Locais Vizinhos (compartilhando pai): {json.dumps(locais_vizinhos_simples, ensure_ascii=False)}
        - Momento Atual: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrative_mj}
        \"\"\"

        **Sua Análise e Chamadas de Função (`tool_code`):**
        """

    def get_tool_declarations(self):
        """
        Retorna as declarações de ferramentas (funções do DataManager e Neo4jManager)
        que a IA do Neo4j pode chamar. Foco em operações de grafo.
        """
        return [
            {"functionDeclarations": [
                {
                    "name": "add_or_update_parent_child_relation",
                    "description": "Adiciona ou atualiza uma relação hierárquica DENTRO_DE entre locais. O filho está DENTRO_DE o pai.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "child_id_canonico": {"type": "string", "description": "ID canônico do local filho."},
                            "parent_id_canonico": {"type": "string", "description": "ID canônico do local pai."}
                        },
                        "required": ["child_id_canonico", "parent_id_canonico"]
                    }
                },
                {
                    "name": "add_direct_access_relation",
                    "description": "Adiciona uma relação de acesso direto DA_ACESSO_A entre dois locais. Indica um caminho navegável.",
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
                    "description": "Adiciona uma relação universal entre quaisquer duas entidades (Locais, Personagens, Elementos Universais, Facções, Jogador).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origem_id_canonico": {"type": "string", "description": "ID canônico da entidade de origem."},
                            "origem_tipo_tabela": {"type": "string", "description": "Nome da tabela da entidade de origem (ex: 'personagens', 'locais')."},
                            "tipo_relacao": {"type": "string", "description": "Tipo da relação (STRING LIVRE, ex: 'AFILIADO_A', 'CONTROLA', 'POSSUI_TECNOLOGIA')."},
                            "destino_id_canonico": {"type": "string", "description": "ID canônico da entidade de destino."},
                            "destino_tipo_tabela": {"type": "string", "description": "Nome da tabela da entidade de destino (ex: 'faccoes', 'elementos_universais')."},
                            "propriedades_data": {"type": "string", "description": "Dados adicionais da relação em formato JSON string (ex: '{\"intensidade\": 0.8}').", "nullable": True}
                        },
                        "required": ["origem_id_canonico", "origem_tipo_tabela", "tipo_relacao", "destino_id_canonico", "destino_tipo_tabela"]
                    }
                },
                {
                    "name": "update_player_location",
                    "description": "Atualiza a localização atual do jogador no DB e no grafo Neo4j (relação ESTA_EM). Use APENAS com movimento explícito.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_canonical_id": {"type": "string", "description": "ID canônico do jogador."},
                            "new_local_canonical_id": {"type": "string", "description": "ID canônico do novo local do jogador."}
                        },
                        "required": ["player_canonical_id", "new_local_canonical_id"]
                    }
                },
            ]}
        ]
