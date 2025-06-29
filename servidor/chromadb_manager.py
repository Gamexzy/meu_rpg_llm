import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
import chromadb
from chromadb.utils import embedding_functions

# Import the official google-generativeai library.
import google.generativeai as genai

# Import the SentenceTransformer library for local embedding models
from sentence_transformers import SentenceTransformer

# Import global configurations
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
import config as config

class ChromaDBManager:
    """
    API dedicada para interagir com o Pilar A (Base de Dados Vetorial - ChromaDB).
    Responsável por armazenar e buscar embeddings para a lore do jogo.
    Versão: 1.4.2 - Corrigido o nome do parâmetro e a lógica em add_or_update_lore.
    """
    def __init__(self, chroma_path=config.CHROMA_PATH):
        """Initializes the manager and the connection to ChromaDB."""
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # The API key will be automatically read from the GOOGLE_API_KEY or GEMINI_API_KEY environment variable
        # by the 'google.generativeai' library.
        if not config.GEMINI_API_KEY:
            print("WARNING: GEMINI_API_KEY not defined in config.py or environment variables. Calls to the Gemini text generation API may fail.")
            self.genai_initialized = False # Indicates that the remote Gemini API may not work
        else:
            self.genai_initialized = True
            print("INFO: google.generativeai module initialized (for main LLM, API Key via environment variable).")


        # Load a local embedding model.
        print(f"INFO: Loading local embedding model: {config.EMBEDDING_MODEL}")
        try:
            self.local_embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
            self.embedding_dimension = self.local_embedding_model.get_sentence_embedding_dimension()
            print(f"INFO: Local embedding model '{config.EMBEDDING_MODEL}' loaded. Dimension: {self.embedding_dimension}")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load local embedding model '{config.EMBEDDING_MODEL}': {e}")
            self.local_embedding_model = None
            self.embedding_dimension = 384 # Fallback to a common dimension
            
        # The collection will be obtained or created, and the dimension will be inferred from the first added embedding.
        self.collection = self.chroma_client.get_or_create_collection(
            name="rpg_lore_collection"
        )
        print(f"INFO: ChromaDBManager connected successfully to Pillar A at: {chroma_path}")

    async def _get_embedding(self, text):
        """
        Generates an embedding for the provided text using the local embedding model.
        """
        if not text:
            return []
        if not self.local_embedding_model: 
            print("ERROR: Local embedding model not loaded. Cannot generate embeddings.")
            return []

        try:
            embedding = self.local_embedding_model.encode(text).tolist()
            return embedding
        except Exception as e:
            print(f"ERROR generating embedding with local model: {e}. Text: {text[:50]}...")
            return [0.0] * self.embedding_dimension


    async def build_collection_from_data(self, all_sqlite_data):
        """
        Reads textual data from an 'all_sqlite_data' dictionary (which comes from DataManager),
        generates embeddings, and populates them in ChromaDB. Forces collection cleanup and reconstruction.
        Now uses the direct 'tipo' string from entities.
        """
        print("\n--- Building Pillar A (ChromaDB) from provided data ---")
        
        try:
            try:
                self.chroma_client.delete_collection(name="rpg_lore_collection")
                print("INFO: Existing ChromaDB collection 'rpg_lore_collection' deleted for reconstruction.")
            except Exception as e:
                print(f"WARNING: Could not delete ChromaDB collection (may not exist): {e}")

            self.collection = self.chroma_client.get_or_create_collection(
                name="rpg_lore_collection"
            )
            print("INFO: ChromaDB collection 'rpg_lore_collection' ready to be populated.")

        except Exception as e:
            print(f"WARNING: Error configuring or cleaning ChromaDB collection: {e}")
            if not self.local_embedding_model:
                print("ERROR: Local embedding model is not initialized, ChromaDB population will fail.")
            return 

        all_documents = []
        all_metadatas = []
        all_ids = []
        
        locais_data = all_sqlite_data.get('locais', [])
        elementos_universais_data = all_sqlite_data.get('elementos_universais', [])
        personagens_data = all_sqlite_data.get('personagens', [])
        faccoes_data = all_sqlite_data.get('faccoes', [])
        jogador_data = all_sqlite_data.get('jogador', [])
        jogador_posses_data = all_sqlite_data.get('jogador_posses', [])
        # tipos_entidades_data is no longer used directly for entity types
        # tipos_entidades_data = all_sqlite_data.get('tipos_entidades', [])

        # Process Locations
        for row in locais_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo = row.get('tipo', 'Desconhecido') # Get 'tipo' directly as a string
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Local: {nome}. Tipo: {tipo}. Descrição: {perfil_json.get('descricao', 'N/A')}. Propriedades: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "local", "nome": nome, "subtipo": tipo})
            all_ids.append(f"local_{id_canonico}")

        # Process Universal Elements
        for row in elementos_universais_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo = row.get('tipo', 'Desconhecido') # Get 'tipo' directly as a string
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Elemento Universal ({tipo}): {nome}. Detalhes: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "elemento_universal", "nome": nome, "subtipo": tipo})
            all_ids.append(f"elemento_{id_canonico}")

        # Process Characters
        for row in personagens_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo = row.get('tipo', 'Desconhecido') # Get 'tipo' directly as a string
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Personagem ({tipo}): {nome}. Descrição: {perfil_json.get('personalidade', 'N/A')}. Histórico: {perfil_json.get('historico', 'N/A')}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "personagem", "nome": nome, "subtipo": tipo})
            all_ids.append(f"personagem_{id_canonico}")

        # Process Factions
        for row in faccoes_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo = row.get('tipo', 'Desconhecido') # Get 'tipo' directly as a string
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Facção ({tipo}): {nome}. Ideologia: {perfil_json.get('ideologia', 'N/A')}. Influência: {perfil_json.get('influencia', 'N/A')}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "faccao", "nome": nome, "subtipo": tipo})
            all_ids.append(f"faccao_{id_canonico}")

        # Process Player
        for row in jogador_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            perfil_completo_json = json.loads(row['perfil_completo_json']) if row['perfil_completo_json'] else {}
            text_content = f"The main Player: {nome} (ID: {id_canonico}). Race: {perfil_completo_json.get('raca', 'N/A')}. Occupation: {perfil_completo_json.get('ocupacao', 'N/A')}. Personality: {perfil_completo_json.get('personalidade', 'N/A')}."
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "jogador", "nome": nome})
            all_ids.append(f"jogador_{id_canonico}")

        # Process Player Possessions
        jogador_data_map = {j['id']: j['id_canonico'] for j in jogador_data} # Map internal ID to canonical ID

        for row in jogador_posses_data:
            posse_id_canonico = row['id_canonico'] 
            item_nome = row['item_nome']
            jogador_id_db = row['jogador_id']
            jogador_id_canonico = jogador_data_map.get(jogador_id_db, "unknown_player")

            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Possession: {item_nome} (ID: {posse_id_canonico}) of {jogador_id_canonico}. Details: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": posse_id_canonico, "tipo": "posse", "nome": item_nome, "jogador": jogador_id_canonico})
            all_ids.append(posse_id_canonico)

        print(f"INFO: Total of {len(all_documents)} documents collected for embedding.")
        
        if all_documents:
            batch_size = 10 
            for i in range(0, len(all_documents), batch_size):
                documents_batch = all_documents[i:i+batch_size]
                metadatas_batch = all_metadatas[i:i+batch_size]
                ids_batch = all_ids[i:i+batch_size]

                embeddings_batch = []
                for doc_text in documents_batch: 
                    embed = await self._get_embedding(doc_text)
                    if embed:
                        embeddings_batch.append(embed)
                    else:
                        embeddings_batch.append([0.0] * self.embedding_dimension) 

                if embeddings_batch and len(embeddings_batch) == len(ids_batch): 
                    try:
                        self.collection.add(
                            embeddings=embeddings_batch,
                            documents=documents_batch,
                            metadatas=metadatas_batch,
                            ids=ids_batch
                        )
                        print(f"INFO: Batch {i // batch_size + 1}/{ (len(all_documents) + batch_size - 1) // batch_size } of embeddings added to ChromaDB.")
                    except Exception as e:
                        print(f"ERROR adding batch to ChromaDB: {e}")
                else:
                    print(f"WARNING: Inconsistent or empty embeddings/IDs batch in batch {i // batch_size + 1}. Not added.")
        else:
            print("WARNING: No documents to add to ChromaDB.")

        print("\nSUCCESS: ChromaDB collection populated with lore embeddings.")

    async def add_or_update_lore(self, id_canonico, text_content, metadata):
        """
        Adiciona ou atualiza um documento de lore no ChromaDB.
        Usado para canonização dinâmica de nova lore.
        id_canonico: Um ID canônico único para o fragmento de lore (ex: 'estacao_lazarus_descricao_visual').
        metadata: Um dicionário de metadados.
        """
        doc_id = id_canonico  # O ID canônico do lore é o ID do documento
        
        print(f"INFO: Adicionando/Atualizando lore no ChromaDB para '{doc_id}'...")

        # Garante que os metadados sejam um dicionário
        meta_dict = {}
        if isinstance(metadata, str):
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                print(f"ERRO: Metadados para o lore '{doc_id}' não é um JSON válido. Abortando adição.")
                return False
        elif isinstance(metadata, dict):
            meta_dict = metadata
        else:
            print(f"AVISO: Tipo de metadados inesperado ({type(metadata)}) para o lore '{doc_id}'.")

        embedding = await self._get_embedding(text_content)
        
        if embedding:
            try:
                # O método 'upsert' é mais explícito para adicionar ou atualizar.
                self.collection.upsert(
                    embeddings=[embedding],
                    documents=[text_content],
                    metadatas=[meta_dict],
                    ids=[doc_id]
                )
                print(f"INFO: Lore '{doc_id}' adicionado/atualizado no ChromaDB.")
                return True
            except Exception as e:
                print(f"ERRO ao adicionar/atualizar lore '{doc_id}' no ChromaDB: {e}")
                return False
        else:
            print(f"AVISO: Não foi possível gerar embedding para '{doc_id}'. Lore não adicionado.")
            return False


    async def find_relevant_lore(self, query_text, n_results=5):
        """
        Searches for relevant lore in ChromaDB based on a text query.
        """
        print(f"INFO: Searching for relevant lore for query: '{query_text[:50]}...'")
        query_embedding = await self._get_embedding(query_text)

        if not query_embedding:
            print("WARNING: Could not generate embedding for the query. Returning empty.")
            return []

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            print(f"INFO: Found {len(results['documents'][0])} lore results.")
            
            formatted_results = []
            if results and results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i]
                    })
            return formatted_results
        except Exception as e:
            print(f"ERROR searching for lore in ChromaDB: {e}")
            return []

# --- Main Entry Point for Direct Testing (Optional) ---
async def main_test():
    """Asynchronous main function to test ChromaDBManager directly."""
    print("--- Testing ChromaDBManager ---")
    chroma_manager = ChromaDBManager()

    print("\nStarting ChromaDB collection population from SQLite (for direct testing)...")
    # For this test, we will simulate some data for build_collection_from_data
    # In a real scenario, you would call DataManager().get_all_entities_from_table()
    mock_sqlite_data = {
        'locais': [{
            'id': 1,
            'id_canonico': 'estacao_base_alfa',
            'nome': 'Estação Base Alfa',
            'tipo': 'Estação Espacial', # 'tipo' is now a direct string
            'parent_id': None,
            'perfil_json': '{"funcao": "Hub de pesquisa e comércio.", "populacao": 500, "descricao": "Uma estação espacial movimentada."}'
        }],
        # 'tipos_entidades' no longer directly used in this manager for entity types
        # 'tipos_entidades': [], 
        'jogador': [{
            'id': 1,
            'id_canonico': 'pj_gabriel_oliveira',
            'nome': 'Gabriel Oliveira',
            'local_atual_id': 1,
            'perfil_completo_json': '{"raca": "Humano", "ocupacao": "Explorador", "personalidade": "Curioso"}'
        }],
        'jogador_posses': [],
        'elementos_universais': [],
        'personagens': [],
        'faccoes': [],
        'jogador_habilidades': [],
        'jogador_conhecimentos': [],
        'jogador_status_fisico_emocional': [],
        'jogador_logs_memoria': [],
        'local_elementos': [],
        'locais_acessos_diretos': [],
        'relacoes_entidades': []
    }
    await chroma_manager.build_collection_from_data(mock_sqlite_data)

    print("\n--- Testing relevant lore search ---")
    query1 = "I want to know about the station's laboratories."
    results1 = await chroma_manager.find_relevant_lore(query1)
    for r in results1:
        print(f"  Document: {r['document'][:100]}...")
        print(f"  Metadata: {r['metadata']}")
        print(f"  Distance: {r['distance']}\n")

    query2 = "Who is Gabriel?"
    results2 = await chroma_manager.find_relevant_lore(query2, n_results=2)
    for r in results2:
        print(f"  Document: {r['document'][:100]}...")
        print(f"  Metadata: {r['metadata']}")
        print(f"  Distance: {r['distance']}\n")

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_test())
