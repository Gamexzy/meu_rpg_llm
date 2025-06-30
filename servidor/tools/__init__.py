# servidor/tools/__init__.py

from .sqlite_tools import SQLITE_TOOL_DECLARATIONS
from .neo4j_tools import NEO4J_TOOL_DECLARATIONS
from .chromadb_tools import CHROMADB_TOOL_DECLARATIONS

# Combina todas as 'functionDeclarations' de cada pilar em uma única super-lista.
# Isso cria a lista completa de ferramentas que o WorldAgent poderá usar.
ALL_FUNCTIONS = (
    SQLITE_TOOL_DECLARATIONS[0].get('functionDeclarations', []) +
    NEO4J_TOOL_DECLARATIONS[0].get('functionDeclarations', []) +
    CHROMADB_TOOL_DECLARATIONS[0].get('functionDeclarations', [])
)

# Empacota a super-lista de volta no formato esperado pela API da IA.
ALL_TOOLS = [{"functionDeclarations": ALL_FUNCTIONS}]