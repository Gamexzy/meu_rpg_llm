import chromadb
import os
import json
from sentence_transformers import SentenceTransformer
from config import config

class ChromaDBManager:
    """
    Gerencia a interação com o banco de dados vetorial ChromaDB para uma sessão de jogo específica.
    Versão: 3.0.0 - Unificado para operar com coleções nomeadas por sessão, 
                  combinando a construção inicial com a gestão dinâmica de lore.
    """
    _client = None
    _model = None

    def __init__(self, session_name: str):
        """
        Inicializa o ChromaDBManager para uma sessão de jogo específica.
        O cliente do ChromaDB e o modelo de embedding são carregados apenas uma vez.

        Args:
            session_name (str): O nome da coleção a ser usada para esta sessão.
                                Deve corresponder ao nome da sessão do DataManager.
        """
        # Carrega o modelo de embedding (apenas uma vez)
        if ChromaDBManager._model is None:
            print(f"INFO: Carregando modelo de embedding local: {config.EMBEDDING_MODEL}")
            try:
                ChromaDBManager._model = SentenceTransformer(config.EMBEDDING_MODEL)
                print(f"INFO: Modelo de embedding '{config.EMBEDDING_MODEL}' carregado. Dimensão: {self.get_model().get_sentence_embedding_dimension()}")
            except Exception as e:
                print(f"ERRO CRÍTICO: Falha ao carregar o modelo de embedding '{config.EMBEDDING_MODEL}': {e}")
                raise

        # Conecta ao cliente persistente do ChromaDB (apenas uma vez)
        if ChromaDBManager._client is None:
            db_path = os.path.join(config.PROD_DATA_DIR, "chroma_db")
            os.makedirs(db_path, exist_ok=True)
            ChromaDBManager._client = chromadb.PersistentClient(path=db_path)
            print(f"INFO: ChromaDBManager conectado com sucesso ao diretório: {db_path}")

        self.session_name = session_name
        # Obtém ou cria a coleção específica para esta sessão
        self.collection = ChromaDBManager._client.get_or_create_collection(
            name=self.session_name,
            metadata={"hnsw:space": "cosine"} # 'cosine' é ótimo para embeddings de texto baseados em transformers
        )
        print(f"INFO: Coleção ChromaDB '{self.session_name}' carregada/criada.")

    def get_model(self):
        """Retorna a instância do modelo de embedding carregado."""
        return self._model

    def _get_embedding(self, text: str):
        """Gera um embedding para o texto fornecido usando o modelo local."""
        if not text or not self.get_model():
            return []
        try:
            return self.get_model().encode(text).tolist()
        except Exception as e:
            print(f"ERRO ao gerar embedding: {e}. Texto: {text[:60]}...")
            return []

    def build_collection_from_data(self, all_sqlite_data: dict):
        """
        Constrói (ou reconstrói) a coleção vetorial da sessão a partir dos dados do SQLite.
        Isso apaga os dados existentes na coleção da sessão para garantir um estado limpo.
        """
        print(f"\n--- Construindo coleção vetorial para a sessão '{self.session_name}' ---")
        
        # Limpa a coleção existente para esta sessão antes de reconstruir
        ChromaDBManager._client.delete_collection(name=self.session_name)
        self.collection = ChromaDBManager._client.get_or_create_collection(name=self.session_name, metadata={"hnsw:space": "cosine"})
        print(f"INFO: Coleção '{self.session_name}' limpa e pronta para ser populada.")

        all_documents, all_metadatas, all_ids = [], [], []

        # Mapeia os dados de cada tabela para um formato unificado
        entity_map = {
            'locais': ('local', 'local'),
            'elementos_universais': ('elemento_universal', 'elemento'),
            'personagens': ('personagem', 'personagem'),
            'faccoes': ('faccao', 'faccao'),
            'jogador': ('jogador', 'jogador'),
            'jogador_posses': ('posse', 'posse'),
            'itens': ('item', 'item')
        }

        for table_name, (tipo_meta, id_prefix) in entity_map.items():
            for row in all_sqlite_data.get(table_name, []):
                id_canonico = row.get('id_canonico')
                if not id_canonico:
                    continue
                
                nome = row.get('nome', row.get('item_nome', 'N/A'))
                tipo = row.get('tipo', 'genérico')
                perfil = row.get('perfil_json') or row.get('perfil_completo_json')
                perfil_dict = json.loads(perfil) if perfil else {}
                
                # Cria um texto descritivo para ser vetorizado
                text_content = f"Entidade: {nome} (ID: {id_canonico}). Tipo: {tipo_meta}/{tipo}. Detalhes: {json.dumps(perfil_dict, ensure_ascii=False)}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo_entidade": tipo_meta, "nome": nome, "subtipo": tipo})
                all_ids.append(f"{id_prefix}_{id_canonico}")

        if not all_documents:
            print("AVISO: Nenhum documento para adicionar à coleção.")
            return

        print(f"INFO: {len(all_documents)} documentos coletados. Gerando embeddings e adicionando em lotes...")
        
        # Adiciona ao ChromaDB em lotes para eficiência
        batch_size = 50
        for i in range(0, len(all_documents), batch_size):
            documents_batch = all_documents[i:i+batch_size]
            metadatas_batch = all_metadatas[i:i+batch_size]
            ids_batch = all_ids[i:i+batch_size]
            
            embeddings_batch = self.get_model().encode(documents_batch).tolist()
            
            self.collection.add(
                embeddings=embeddings_batch,
                documents=documents_batch,
                metadatas=metadatas_batch,
                ids=ids_batch
            )
            print(f"INFO: Lote {i//batch_size + 1} adicionado à coleção '{self.session_name}'.")

        print(f"\nSUCESSO: Coleção vetorial '{self.session_name}' populada com {len(all_documents)} documentos.")

    def add_or_update_lore(self, id_canonico: str, text_content: str, metadata: dict):
        """
        Adiciona ou atualiza um único documento (lore) na coleção da sessão.
        Ideal para canonização dinâmica de novas informações.
        """
        try:
            embedding = self._get_embedding(text_content)
            if not embedding:
                print(f"AVISO: Não foi possível gerar embedding para '{id_canonico}'. Lore não adicionado.")
                return

            self.collection.upsert(
                ids=[id_canonico],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[text_content]
            )
        except Exception as e:
            print(f"ERRO ao adicionar/atualizar lore para '{id_canonico}' na coleção '{self.session_name}': {e}")
            raise

    def query_lore(self, query_text: str, n_results: int = 5, where_filter: dict = None):
        """
        Busca por documentos de lore relevantes na coleção da sessão.

        Args:
            query_text (str): O texto para a busca de similaridade.
            n_results (int): O número de resultados a retornar.
            where_filter (dict, optional): Um filtro para os metadados. 
                                           Ex: {"tipo_entidade": "personagem"}
        
        Returns:
            Uma lista de resultados formatados ou uma lista vazia.
        """
        try:
            query_embedding = self._get_embedding(query_text)
            if not query_embedding:
                return []

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )
            return results
        except Exception as e:
            print(f"ERRO ao consultar lore na coleção '{self.session_name}': {e}")
            return None

    def get_lore_by_id(self, id_canonico: str):
        """Obtém um documento de lore específico pelo seu ID na coleção da sessão."""
        try:
            return self.collection.get(ids=[id_canonico])
        except Exception as e:
            print(f"ERRO ao obter lore por ID '{id_canonico}' na coleção '{self.session_name}': {e}")
            return None

