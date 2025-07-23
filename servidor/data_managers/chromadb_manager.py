import chromadb
import os
from sentence_transformers import SentenceTransformer
from langchain.tools import tool
from config import config

class ChromaDBManager:
    """
    Gerencia a interação com o banco de dados vetorial ChromaDB para uma sessão específica.
    Versão: 2.1.0 - Adicionadas anotações @tool para exposição ao LLM.
    """
    _model = None
    _client = None

    def __init__(self, session_name: str):
        if ChromaDBManager._model is None:
            print("INFO: Loading local embedding model: all-MiniLM-L6-v2")
            ChromaDBManager._model = SentenceTransformer('all-MiniLM-L6-v2')
            print("INFO: Local embedding model 'all-MiniLM-L6-v2' loaded. Dimension: 384")

        if ChromaDBManager._client is None:
            db_path = os.path.join(config.PROD_DATA_DIR, "chroma_db")
            os.makedirs(db_path, exist_ok=True)
            ChromaDBManager._client = chromadb.PersistentClient(path=db_path)
            print(f"INFO: ChromaDBManager connected successfully to Pillar A at: {db_path}")

        self.session_name = session_name
        self.collection = ChromaDBManager._client.get_or_create_collection(
            name=self.session_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"INFO: ChromaDB collection '{self.session_name}' loaded/created.")

    def get_model(self):
        return self._model

    @tool
    def add_or_update_lore(self, id_canonico: str, text_content: str, metadata: dict):
        """
        Adiciona ou atualiza um documento de 'lore' (conhecimento do mundo) para uma entidade específica.
        Use esta função para registrar descrições, histórias ou fatos sobre personagens, locais ou itens.
        """
        try:
            embedding = self.get_model().encode(text_content).tolist()
            self.collection.upsert(
                ids=[id_canonico],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[text_content]
            )
            print(f"INFO: Lore '{id_canonico}' adicionado/atualizado no ChromaDB para a sessão '{self.session_name}'.")
        except Exception as e:
            print(f"Erro ao adicionar/atualizar lore para '{id_canonico}' na coleção '{self.session_name}': {e}")
            raise

    def query_lore(self, query_text: str, n_results: int = 5):
        """Busca por documentos de lore relevantes na coleção da sessão."""
        try:
            query_embedding = self.get_model().encode(query_text).tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"Erro ao consultar lore na coleção '{self.session_name}': {e}")
            return None
