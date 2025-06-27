

# Dicionário que define os tipos genéricos base para cada tabela.
# Estes tipos servem como raízes para a hierarquia de tipos no sistema.
GENERIC_ENTITY_TYPES = {
    'locais': ["Espacial", "Construção", "Natural", "Ambiental", "Dimensional"],
    'elementos_universais': ["Objeto", "Energia", "Habilidade", "Fenômeno"],
    'personagens': ["Ser", "Autômato", "Força"],
    'faccoes': ["Grupo", "Estrutura", "Coletivo"]
}

# Versão deste arquivo de dados
ENTITY_TYPES_DATA_VERSION = "1.0.0"

# Função auxiliar para converter strings para snake_case.
# Colocada aqui para centralizar a lógica de formatação de nomes de tipo.
def to_snake_case(text):
    """Converte uma string para snake_case."""
    if not text:
        return ""
    text = text.replace(' ', '_').replace('-', '_').lower()
    return ''.join(c for c in text if c.isalnum() or c == '_')
