import json
import datetime
from config import config

class SQLiteAgent:
    """
    Agente de IA especializado em estruturar informações para o banco de dados SQLite.
    Versão: 1.5.0 - Prompt refinado para enfatizar a resposta em lote único.
    """

    def __init__(self):
        print("INFO: SQLiteAgent (Disparo Único) inicializado (v1.5.0).")

    def format_prompt(self, narrative_mj, contexto):
        """
        Formata um prompt detalhado para a IA do SQLite, instruindo-a a extrair
        dados estruturados da narrativa para persistência no SQLite.
        """
        jogador_info_simples = {
            'id_canonico': contexto['jogador']['base'].get('id_canonico', 'N/A'),
            'nome': contexto['jogador']['base'].get('nome', 'N/A'),
            'local_atual_id_canonico': contexto['jogador']['base'].get('local_id_canonico', 'N/A')
        }
        local_info_simples = {
            'id_canonico': contexto['local_atual']['id_canonico'],
            'nome': contexto['local_atual']['nome'],
            'tipo': contexto['local_atual']['tipo'],
            'descricao': contexto['local_atual']['perfil_json'].get('descricao', 'N/A')
        }

        return f"""
        # INSTRUÇÃO PARA AGENTE DE ESTRUTURAÇÃO DE DADOS (SQLite AI)
        Você é um agente de IA que processa narrativas de RPG e as converte em chamadas de função para um banco de dados SQLite.

        **TAREFA CRÍTICA: RESPOSTA ÚNICA E COMPLETA**
        Analise a narrativa fornecida e identifique **TODAS** as novas entidades (locais, personagens, itens) ou atualizações necessárias. Você deve retornar **UMA LISTA COM TODAS AS CHAMADAS DE FUNÇÃO `tool_code` necessárias EM UMA ÚNICA RESPOSTA**.

        **DIRETRIZES CRÍTICAS:**
        1.  **SEJA CONSERVADOR AO CRIAR LOCAIS:** Não crie locais duplicados ou triviais (como "área rochosa"). Crie um novo local apenas se for uma área distinta e com propósito (ex: "Caverna Escondida", "Laboratório Secreto").
        2.  **IDs Canônicos Únicos**: Ao criar uma entidade GENUINAMENTE nova, SEMPRE crie um `id_canonico` único e descritivo.
        3.  **Responda APENAS com a lista de chamadas de função**: Se não houver nada a ser adicionado/atualizado, retorne uma resposta vazia.

        **Contexto Atual do Jogo (Para Referência):**
        - Jogador: {json.dumps(jogador_info_simples, ensure_ascii=False)}
        - Local Atual: {json.dumps(local_info_simples, ensure_ascii=False)}

        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrative_mj}
        \"\"\"

        **Sua Análise e Lista Completa de Chamadas de Função:**
        """

    def get_tool_declarations(self):
        """
        Retorna as declarações de ferramentas que a IA do SQLite pode chamar.
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
                # add_or_get_player não deve ser chamada diretamente pela IA do SQLite para evitar recriar o jogador principal.
                # Ele é criado pelo LLM principal na inicialização.
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
                            "timestamp_atual": {"type": "string", "description": "Timestamp atual no formato अवलंब-MM-DD HH:MM:S.", "nullable": True}
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
                    "description": "Adiciona uma nova coluna a uma tabela existente. Idempotente. Use APENAS se uma nova propriedade crucial não puder ser armazenada em perfil_json.",
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
