# servidor/tools/neo4j_tools.py

NEO4J_TOOL_DECLARATIONS = [
    {"functionDeclarations": [
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
            "description": "Adiciona uma relação de acesso direto DA_ACESSO_A entre dois locais. Indica um caminho navegável. Idempotente.",
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
            "description": "Adiciona uma relação universal entre quaisquer duas entidades (Locais, Personagens, Facções, Jogador, etc). Idempotente.",
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
        }
    ]}
]