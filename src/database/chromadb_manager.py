# src/database/chromadb_manager.py
import chromadb
import os
import json
from sentence_transformers import SentenceTransformer
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List
from src import config

class AddOrUpdateLoreArgs(BaseModel):
    universe_id: int = Field(description="O ID do universo ao qual este lore pertence.")
    canonical_id: str = Field(description="O ID canônico da entidade que está sendo descrita (ex: 'cidade_valor_eterno').")
    text_content: str = Field(description="O texto completo do fragmento de lore a ser armazenado.")
    metadata: str = Field(description="Um objeto JSON como string contendo metadados. Ex: '{\"tipo\": \"local\", \"nome\": \"Valor Eterno\"}'.")

class ChromaDBManager:
    """
    Gere a interação com o banco de dados vetorial ChromaDB.
    Versão: 6.0.0 - Refatorado para ser centrado no Universo.
    """
    _model = None
    _client = None

    def __init__(self):
        if ChromaDBManager._model is None:
            print(f"INFO: Carregando modelo de embedding: {config.EMBEDDING_MODEL}")
            ChromaDBManager._model = SentenceTransformer(config.EMBEDDING_MODEL)
            print(f"INFO: Modelo de embedding '{config.EMBEDDING_MODEL}' carregado.")

        if ChromaDBManager._client is None:
            os.makedirs(config.CHROMA_PATH, exist_ok=True)
            ChromaDBManager._client = chromadb.PersistentClient(path=config.CHROMA_PATH)
            print(f"INFO: ChromaDBManager conectado com sucesso ao Pilar A em: {config.CHROMA_PATH}")

    def _get_collection_name(self, universe_id: int) -> str:
        """Gera um nome de coleção padronizado para um universo."""
        return f"universo_{universe_id}_lore"

    def get_or_create_universe_collection(self, universe_id: int):
        """Obtém ou cria uma coleção de lore para um universo específico."""
        collection_name = self._get_collection_name(universe_id)
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def delete_universe_collection(self, universe_id: int) -> bool:
        """Apaga a coleção de lore inteira associada a um universo."""
        collection_name = self._get_collection_name(universe_id)
        try:
            self._client.delete_collection(name=collection_name)
            print(f"INFO: Coleção de lore '{collection_name}' apagada do ChromaDB.")
            return True
        except ValueError:
            print(f"AVISO: Coleção '{collection_name}' não encontrada no ChromaDB para apagar.")
            return False
        except Exception as e:
            print(f"ERRO: Falha ao apagar a coleção '{collection_name}': {e}")
            return False

    @tool(args_schema=AddOrUpdateLoreArgs)
    def add_or_update_lore(self, universe_id: int, canonical_id: str, text_content: str, metadata: str) -> bool:
        """Adiciona ou atualiza um documento de 'lore' para um universo específico."""
        collection_name = self._get_collection_name(universe_id)
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            print(f"ERRO: Metadados para o lore '{canonical_id}' não é um JSON válido.")
            return False

        try:
            collection = self.get_or_create_universe_collection(universe_id)
            embedding = self._model.encode(text_content).tolist()
            collection.upsert(
                ids=[canonical_id],
                embeddings=[embedding],
                metadatas=[metadata_dict],
                documents=[text_content]
            )
            print(f"INFO: Lore '{canonical_id}' adicionado/atualizado na coleção '{collection_name}'.")
            return True
        except Exception as e:
            print(f"ERRO ao adicionar/atualizar lore em '{collection_name}': {e}")
            return False

    def query_lore(self, universe_id: int, query_text: str, n_results: int = 5) -> List[str]:
        """Busca por documentos de lore relevantes na coleção de um universo."""
        collection_name = self._get_collection_name(universe_id)
        try:
            collection = self.get_or_create_universe_collection(universe_id)
            query_embedding = self._model.encode(query_text).tolist()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results.get('documents', [[]])[0]
        except Exception as e:
            print(f"ERRO ao consultar lore na coleção '{collection_name}': {e}")
            return []
