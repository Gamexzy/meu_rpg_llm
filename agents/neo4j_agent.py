import json
import datetime
from config import config

class Neo4jAgent:
    """
    Agente de IA especializado em gerenciar as relações e a estrutura de grafo (Neo4j).
    Versão: 1.3.0 - O agente agora é instruído a criar até 5 relações em lote por turno.
    """

    def __init__(self):
        print("INFO: Neo4jAgent (Processador em Lote) inicializado (v1.3.0).")

    def format_prompt(self, narrative_mj, contexto):
        """
        Formata um prompt detalhado para a IA do Neo4j, instruindo-a a identificar
        e estruturar relações entre entidades.
        """
        jogador_info_simples = {
            'id_canonico': contexto['jogador']['base'].get('id_canonico', 'N/A'),
            'nome': contexto['jogador']['base'].get('nome', 'N/A'),
            'local_atual_id_canonico': contexto['jogador']['base'].get('local_id_canonico', 'N/A')
        }
        local_atual_info_simples = {
            'id_canonico': contexto['local_atual']['id_canonico'],
            'nome': contexto['local_atual']['nome'],
            'tipo': contexto['local_atual']['tipo']
        }
        locais_contidos_simples = [{'id_canonico': l['id_canonico'], 'nome': l['nome'], 'tipo': l['tipo']} for l in contexto.get('locais_contidos', [])]
        locais_acessos_diretos_simples = [{'id_canonico': a['id_canonico'], 'nome': a['nome'], 'tipo': a['tipo'], 'tipo_acesso': a.get('tipo_acesso')} for a in contexto.get('locais_acessos_diretos', [])]
        locais_vizinhos_simples = [{'id_canonico': l['id_canonico'], 'nome': l['nome'], 'tipo': l['tipo']} for l in contexto.get('locais_vizinhos', [])]

        return f"""
        # INSTRUÇÃO PARA AGENTE DE GRAFO DE DADOS (Neo4j AI)
        Você é um agente de IA que analisa narrativas de RPG para mapear as relações em um grafo de dados (Neo4j).

        **TAREFA PRINCIPAL: PROCESSAMENTO EM LOTE**
        Sua tarefa é identificar **ATÉ {config.MAX_AGENT_TOOL_CALLS} NOVAS relações** (hierárquicas, de acesso, universais) entre as entidades e fazer **TODAS as chamadas de função necessárias em uma única resposta**.

        **DIRETRIZES CRÍTICAS:**
        1.  **REGRA DE OURO - NÃO INVENTE MOVIMENTO:** A localização do jogador no contexto é a verdade absoluta. SÓ chame `update_player_location` se a narrativa descrever um movimento **explícito e inequívoco**.
        2.  **FOCO EM MAPEAMENTO:** Sua principal responsabilidade é criar o mapa de relações (`DENTRO_DE`, `DA_ACESSO_A`, etc.) entre as entidades que o `Agente SQLite` já criou. Você é um cartógrafo.
        3.  **HIERARQUIA DE AGENTES:** O `Agente SQLite` cria os "nós". Você desenha as "arestas" entre eles. Assuma que os nós já existem.
        4.  **SÓ RESPONDA COM CHAMADAS DE FUNÇÃO:** Se a narrativa não fornecer informações claras para criar ou atualizar uma relação, não responda nada.

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

        **Sua Análise e Chamadas de Função (`tool_code`, até {config.MAX_AGENT_TOOL_CALLS} chamadas):**
        """

    def get_tool_declarations(self):
        """
        Retorna as declarações de ferramentas que a IA do Neo4j pode chamar.
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
