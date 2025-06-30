import json
import datetime
from config import config

class Neo4jAgent:
    """
    Agente de IA especializado em gerenciar as relações e a estrutura de grafo (Neo4j).
    Versão: 1.4.0 - Prompt refinado para enfatizar a resposta em lote único.
    """

    def __init__(self):
        print("INFO: Neo4jAgent (Disparo Único) inicializado (v1.4.0).")

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
        
        return f"""
        # INSTRUÇÃO PARA AGENTE DE GRAFO DE DADOS (Neo4j AI)
        Você é um agente de IA que analisa narrativas de RPG para mapear as relações em um grafo de dados (Neo4j).

        **TAREFA CRÍTICA: RESPOSTA ÚNICA E COMPLETA**
        Sua tarefa é identificar **TODAS as NOVAS relações** (hierárquicas, de acesso, universais) entre as entidades mencionadas na narrativa. Você deve retornar **UMA LISTA COM TODAS AS CHAMADAS DE FUNÇÃO `tool_code` necessárias EM UMA ÚNICA RESPOSTA**.

        **DIRETRIZES CRÍTICAS:**
        1.  **NÃO INVENTE MOVIMENTO:** A localização do jogador no contexto é a verdade absoluta. SÓ chame `update_player_location` se a narrativa descrever um movimento **explícito e inequívoco**.
        2.  **FOCO EM MAPEAMENTO:** Sua responsabilidade é criar o mapa de relações (`DENTRO_DE`, `DA_ACESSO_A`, etc.) entre as entidades que o `Agente SQLite` já criou. Assuma que os nós já existem.
        3.  **Responda APENAS com a lista de chamadas de função**: Se não houver novas relações para criar, retorne uma resposta vazia.

        **Contexto Atual do Jogo (Para Referência - Entidades Existentes):**
        - Jogador Principal: {json.dumps(jogador_info_simples, ensure_ascii=False)}
        - Local Atual: {json.dumps(local_atual_info_simples, ensure_ascii=False)}

        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrative_mj}
        \"\"\"

        **Sua Análise e Lista Completa de Chamadas de Função:**
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
