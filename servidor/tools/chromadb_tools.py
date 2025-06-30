# servidor/tools/chromadb_tools.py

CHROMADB_TOOL_DECLARATIONS = [{
    "functionDeclarations": [
        {
            "name": "add_or_update_lore",
            "description": "Adiciona ou ATUALIZA um fragmento de lore (conhecimento do mundo) no banco de dados vetorial. Use para CONSOLIDAR descrições.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "id_canonico": {"type": "STRING", "description": "O ID canônico da ENTIDADE PRINCIPAL que está a ser descrita (ex: 'planeta_cygnus_prime', 'pj_lyra_a_andarilha')."},
                    "text_content": {"type": "STRING", "description": "O texto COMPLETO e CONSOLIDADO do fragmento de lore a ser armazenado e vetorizado."},
                    "metadata": {"type": "STRING", "description": "Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Cygnus Prime\"}'."}
                },
                "required": ["id_canonico", "text_content", "metadata"]
            }
        }
    ]
}]