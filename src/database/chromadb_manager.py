# servidor/data_managers/chromadb_manager.py
import chromadb
import os
import json
from sentence_transformers import SentenceTransformer
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Dict, List
from src import config

# --- Modelos Pydantic para Validação de Argumentos das Ferramentas ---

class AddOrUpdateLoreArgs(BaseModel):
    id_canonico: str = Field(description="O ID canónico da ENTIDADE PRINCIPAL que está a ser descrita (ex: 'planeta_cygnus_prime').")
    text_content: str = Field(description="O texto COMPLETO e CONSOLIDADO do fragmento de lore a ser armazenado e vetorizado.")
    metadata: str = Field(description="Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Cygnus Prime\"}'.")
    session_name: str = Field(description="O nome da sessão de jogo atual.")

class ChromaDBManager:
    """
    Gere a interação com o banco de dados vetorial ChromaDB.
    Versão: 5.1.0 - Corrigido para ser uma instância única (singleton) e receber o session_name nos métodos.
    """
    _model = None
    _client = None

    def __init__(self):
        # Esta classe agora é um singleton e não recebe argumentos na inicialização.
        if ChromaDBManager._model is None:
            print("INFO: Loading local embedding model: all-MiniLM-L6-v2")
            ChromaDBManager._model = SentenceTransformer('all-MiniLM-L6-v2')
            print("INFO: Local embedding model 'all-MiniLM-L6-v2' loaded.")

        if ChromaDBManager._client is None:
            db_path = os.path.join(config.PROD_DATA_DIR, "chroma_db")
            os.makedirs(db_path, exist_ok=True)
            ChromaDBManager._client = chromadb.PersistentClient(path=db_path)
            print(f"INFO: ChromaDBManager connected successfully to Pillar A at: {db_path}")

    def get_collection(self, session_name: str):
        """Obtém ou cria uma coleção para uma sessão específica."""
        # Sanitiza o nome da coleção para conformidade com o ChromaDB
        safe_collection_name = "".join(c for c in session_name if c.isalnum() or c in ('_', '-'))
        safe_collection_name = safe_collection_name[:63] # Limita o comprimento

        return self._client.get_or_create_collection(
            name=safe_collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    @tool(args_schema=AddOrUpdateLoreArgs)
    def add_or_update_lore(self, session_name: str, id_canonico: str, text_content: str, metadata: str) -> bool:
        """Adiciona ou atualiza um documento de 'lore' (conhecimento do mundo) para uma entidade específica."""
        try:
            # CORREÇÃO: Converte a string JSON de metadados em um dicionário Python.
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                print(f"ERRO: Metadados para o lore '{id_canonico}' não é um JSON válido. Metadados recebidos: {metadata}")
                return False

            collection = self.get_collection(session_name)
            embedding = self._model.encode(text_content).tolist()
            collection.upsert(
                ids=[id_canonico],
                embeddings=[embedding],
                metadatas=[metadata_dict], # Usa o dicionário convertido
                documents=[text_content]
            )
            print(f"INFO: Lore '{id_canonico}' adicionado/atualizado no ChromaDB para a sessão '{session_name}'.")
            return True
        except Exception as e:
            print(f"Erro ao adicionar/atualizar lore para '{id_canonico}' na coleção '{session_name}': {e}")
            return False

    def query_lore(self, session_name: str, query_text: str, n_results: int = 5) -> List[str]:
        """Busca por documentos de lore relevantes na coleção da sessão."""
        try:
            collection = self.get_collection(session_name)
            query_embedding = self._model.encode(query_text).tolist()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results.get('documents', [[]])[0]
        except Exception as e:
            print(f"Erro ao consultar lore na coleção '{session_name}': {e}")
            return []
