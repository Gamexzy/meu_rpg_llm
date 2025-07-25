# servidor/data_managers/chromadb_manager.py
import chromadb
import os
from sentence_transformers import SentenceTransformer
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json

from config import config

# --- Modelos Pydantic para Validação de Ferramentas ---

class AddOrUpdateLoreArgs(BaseModel):
    id_canonico: str = Field(description="O ID canónico da ENTIDADE PRINCIPAL que está a ser descrita (ex: 'planeta_cygnus_prime', 'pj_lyra_a_andarilha').")
    text_content: str = Field(description="O texto COMPLETO e CONSOLIDADO do fragmento de lore a ser armazenado e vetorizado.")
    metadata: Dict = Field(description="Um dicionário Python contendo metadados. Ex: {'tipo': 'local', 'nome': 'Cygnus Prime'}.")

class ChromaDBManager:
    """
    Gerencia a interação com o banco de dados vetorial ChromaDB para uma sessão específica.
    Versão: 3.1.0 - Corrigida a função query_lore para retornar a lista de documentos corretamente.
    """
    _model = None
    _client = None

    def __init__(self, session_name: str):
        if ChromaDBManager._model is None:
            print("INFO: Loading local embedding model: all-MiniLM-L6-v2")
            ChromaDBManager._model = SentenceTransformer(config.EMBEDDING_MODEL)
            print(f"INFO: Local embedding model '{config.EMBEDDING_MODEL}' loaded.")

        if ChromaDBManager._client is None:
            os.makedirs(config.CHROMA_PATH, exist_ok=True)
            ChromaDBManager._client = chromadb.PersistentClient(path=config.CHROMA_PATH)
            print(f"INFO: ChromaDBManager connected successfully to Pillar A at: {config.CHROMA_PATH}")

        self.session_name = session_name
        self.collection = ChromaDBManager._client.get_or_create_collection(
            name=self.session_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"INFO: ChromaDB collection '{self.session_name}' loaded/created.")

    def get_model(self):
        return self._model

    @tool(args_schema=AddOrUpdateLoreArgs)
    def add_or_update_lore(self, **kwargs):
        """
        Adiciona ou ATUALIZA um fragmento de lore (conhecimento do mundo) no banco de dados vetorial. Use para CONSOLIDAR descrições.
        """
        args = AddOrUpdateLoreArgs(**kwargs)
        try:
            embedding = self.get_model().encode(args.text_content).tolist()
            self.collection.upsert(
                ids=[args.id_canonico],
                embeddings=[embedding],
                metadatas=[args.metadata],
                documents=[args.text_content]
            )
            print(f"INFO: Lore '{args.id_canonico}' adicionado/atualizado no ChromaDB para a sessão '{self.session_name}'.")
        except Exception as e:
            print(f"Erro ao adicionar/atualizar lore para '{args.id_canonico}' na coleção '{self.session_name}': {e}")
            raise

    def query_lore(self, query_text: str, n_results: int = 5) -> Optional[List[str]]:
        """Busca por documentos de lore relevantes na coleção da sessão."""
        try:
            query_embedding = self.get_model().encode(query_text).tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            # --- CORREÇÃO APLICADA AQUI ---
            # Retorna apenas a lista de documentos, que é o que o resto do sistema espera.
            if results and results.get("documents"):
                return results["documents"][0]
            return None
        except Exception as e:
            print(f"Erro ao consultar lore na coleção '{self.session_name}': {e}")
            return None
