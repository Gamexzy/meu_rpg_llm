import json
import datetime
import os
import sys

# Adiciona o diretório raiz do projeto ao sys.path para que o config possa ser importado
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))
import config as config

class SQLiteAgent:
    """
    Agente de IA especializado em estruturar informações para o banco de dados SQLite.
    (Versão: 1.0.1)
    Responsabilidade: Gerar o prompt e as declarações de ferramentas para que um LLM
    possa analisar a narrativa e criar/atualizar entidades e relações no SQLite.
    """

    def __init__(self):
        print("INFO: SQLiteAgent inicializado (v1.0.1).")

    def format_prompt(self, narrative_mj, contexto):
        """
        Formata um prompt detalhado para a IA do SQLite, instruindo-a a extrair
        dados estruturados da narrativa para persistência no SQLite.
        """
        # Simplificando o contexto para o que é essencial para a IA de SQLite,
        # para evitar exceder o limite de tokens e focar a IA.
        jogador_info_simples = {
            'id_canonico': contexto['jogador']['base']['id_canonico'],
            'nome': contexto['jogador']['base']['nome'],
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
        Você é um agente de inteligência artificial especializado em extrair informações factuais de narrativas de RPG e convertê-las em chamadas de função para um banco de dados SQLite. Sua tarefa é analisar a narrativa do Mestre de Jogo e o contexto atual do mundo para identificar NOVAS entidades (locais, personagens, elementos universais, facções), suas propriedades e as relações entre elas, ou ATUALIZAR dados existentes.

        **Seu objetivo principal é GARANTIR A CONSISTÊNCIA E O ENRIQUECIMENTO DO BANCO DE DADOS factual (SQLite).**

        **DIRETRIZES:**
        1.  **Prioridade**: Foque na extração de informações CONCRETAS e CANÔNICAS. Não adicione suposições ou detalhes vagos.
        2.  **Idempotência**: As funções que você chamará são idempotentes. Isso significa que, se uma entidade/relação já existe com o `id_canonico` fornecido, ela será atualizada ou ignorada (sem criar duplicatas). Sinta-se à vontade para chamar funções para entidades que você acha que podem existir.
        3.  **IDs Canônicos**: SEMPRE crie `id_canonico` únicos para novas entidades. Use o formato `entidade_nome_descritivo` (ex: `estacao_lazarus`, `personagem_elara`, `item_kit_medico`).
        4.  **Tipos (Parâmetro 'tipo')**: Para `locais`, `elementos_universais`, `personagens` e `faccoes`, o parâmetro `tipo` é uma **STRING LIVRE**. Descreva o tipo da entidade da forma mais precisa e útil narrativamente (ex: 'Estação Espacial Decadente', 'Mercenário Veterano', 'Artefato Antigo de Energia').
        5.  **perfil_json_data**: Use este campo para detalhes adicionais da entidade que não se encaixam em parâmetros diretos, mas que são importantes para a lore (ex: {{"idade": 30, "historico": "Ex-soldado"}}).
        6.  **Relações Universais (`add_universal_relation`)**: Identifique conexões significativas entre quaisquer duas entidades. O `origem_tipo_tabela` e `destino_tipo_tabela` devem ser os nomes das tabelas SQLite (`locais`, `personagens`, `elementos_universais`, `faccoes`, `jogador`). O `tipo_relacao` é uma STRING LIVRE (ex: 'ALIADO_A', 'CONTROLA', 'POSSUI_TECNOLOGIA', 'INTERAGE_COM').
        7.  **add_player_vitals, add_player_skill, add_player_knowledge, add_or_get_player_possession**: Use estas funções para atualizar o estado do jogador com base na narrativa, se houver informações relevantes (ex: jogador ficou com fome, ganhou uma nova habilidade, encontrou um item).
        8.  **update_player_location**: Use esta função se a narrativa indicar que o jogador MUDOU de local.
        9.  **add_direct_access_relation**: Use esta função se a narrativa indicar uma nova conexão direta entre dois locais.
        10. **add_column_to_table**: Use APENAS se uma nova propriedade CRUCIAL (ex: um novo sistema de combate) não puder ser armazenada em `perfil_json`. É uma exceção, não a regra.
        11. **Não adicione Logs do Jogador (`add_log_memory`)**: O sistema já gerencia os logs do jogador. Você não precisa chamar `add_log_memory`.
        12. **Responda SOMENTE com chamadas de função (`tool_code`) ou um texto vazio se não houver nada a ser adicionado/atualizado.**

        **Contexto Atual do Jogo (Para Referência):**
        - Jogador: {json.dumps(jogador_info_simples, ensure_ascii=False)}
        - Local Atual: {json.dumps(local_info_simples, ensure_ascii=False)}
        - Momento Atual: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        **Narrativa do Mestre de Jogo para Análise:**
        \"\"\"
        {narrativa_mj}
        \"\"\"

        **Sua Análise e Chamadas de Função:**
        """

    def get_tool_declarations(self):
        """
        Retorna as declarações de ferramentas (funções do DataManager)
        que a IA do SQLite pode chamar.
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
