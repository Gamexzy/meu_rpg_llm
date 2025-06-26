import os
import sys
import sqlite3
import json
import asyncio
import aiohttp # Mantido para outras operações se necessário
import chromadb
from chromadb.utils import embedding_functions

# NOVO: Importar a biblioteca oficial google-genai
from google import genai
# Não é necessário 'types' se estivermos apenas usando embed_content_async diretamente no modelo.
# from google.generativeai import types 

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH_SQLITE = os.path.join(PROD_DATA_DIR, 'estado.db')
CHROMA_PATH = os.path.join(PROD_DATA_DIR, 'chroma_db') # Caminho para persistir o ChromaDB

# --- Configuração da API Gemini (Embedding) ---
# Se estiver rodando localmente, você precisa definir a variável de ambiente GEMINI_API_KEY
# ou inserir sua chave diretamente aqui (menos seguro).
# Ex: GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "SUA_CHAVE_AQUI")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") # Busca da variável de ambiente ou vazia
# Modelo de Embedding atualizado
EMBEDDING_MODEL = "gemini-embedding-exp-03-07" # Ou "text-embedding-004" se preferir o estável

class ChromaDBManager:
    """
    API dedicada para interagir com o Pilar A (Base de Dados Vetorial - ChromaDB).
    Responsável por armazenar e buscar embeddings para a lore do jogo.
    Versão: 1.2.1 - Corrigido o erro AttributeError: module 'google.genai' has no attribute 'configure'.
    """
    def __init__(self, chroma_path=CHROMA_PATH):
        """Inicializa o gestor e a conexão com o ChromaDB."""
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # Configura o genai com a API Key (agora busca de os.environ ou fallback)
        # É importante que a API Key esteja definida no ambiente ou passada aqui.
        try:
            # CORREÇÃO AQUI: Passar api_key diretamente para genai.Client
            self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
            self.genai_model = genai.GenerativeModel(EMBEDDING_MODEL, client=self.genai_client) # Passa o cliente
            print(f"INFO: genai.GenerativeModel '{EMBEDDING_MODEL}' inicializado com API Key.")
        except Exception as e:
            print(f"ERRO: Falha ao inicializar genai.Client/GenerativeModel: {e}. Verifique sua API Key ou ambiente.")
            self.genai_client = None 
            self.genai_model = None # Define como None para evitar chamadas futuras

        # A função de embedding do ChromaDB ainda precisa de um callable, mas usaremos nossa própria
        # para a geração real. O model_name aqui é apenas um placeholder para o ChromaDB.
        self.collection = self.chroma_client.get_or_create_collection(
            name="rpg_lore_collection",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2") # Dummy
        )
        print(f"INFO: ChromaDBManager conectado com sucesso ao Pilar A em: {chroma_path}")

    async def _get_embedding(self, text):
        """
        Gera um embedding para o texto fornecido usando a biblioteca google-genai e o modelo especificado.
        """
        if not text:
            return []
        if not self.genai_model:
            print("ERRO: genai.GenerativeModel não inicializado (API Key faltando?). Não é possível gerar embeddings.")
            return []

        try:
            # Chamada correta para o método assíncrono de embedding no modelo
            result = await self.genai_model.embed_content_async(
                content=text,
                task_type="RETRIEVAL_DOCUMENT" # Recomendado especificar o tipo de tarefa
            )
            
            if result and result.embedding:
                return result.embedding.values # O atributo 'values' contém a lista de floats
            else:
                print(f"AVISO: Resposta de embedding inesperada para texto: {text[:50]}...")
                return []
        except Exception as e:
            print(f"ERRO ao chamar a API de Embedding com google-genai: {e}. Texto: {text[:50]}...")
            # Pode ser um 403 se a chave for inválida ou limite excedido
            if "403" in str(e) or "PERMISSION_DENIED" in str(e):
                print("DICA: Verifique se sua GEMINI_API_KEY está correta e tem permissões para o modelo de embedding.")
            return []

    def _get_sqlite_connection(self):
        """Retorna uma conexão com o banco de dados SQLite."""
        conn = sqlite3.connect(DB_PATH_SQLITE)
        conn.row_factory = sqlite3.Row
        return conn

    async def build_collection_from_sqlite(self):
        """
        Lê dados textuais de todas as tabelas relevantes no SQLite, gera embeddings
        e os popula no ChromaDB. Limpa a coleção existente antes de popular.
        """
        print("\n--- A construir o Pilar A (ChromaDB) a partir do Pilar B (SQLite) ---")
        
        # Garante que a coleção existe e a limpa se não estiver vazia
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name="rpg_lore_collection",
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2") # Dummy
            )
            if self.collection.count() > 0:
                self.collection.delete(where={}) # Deleta todos os documentos
                print("INFO: Coleção ChromaDB 'rpg_lore_collection' limpa para reconstrução.")
            else:
                print("INFO: Coleção ChromaDB 'rbg_lore_collection' já vazia ou recém-criada.")
        except Exception as e:
            print(f"AVISO: Erro ao configurar ou limpar a coleção ChromaDB: {e}")
            # Em caso de erro grave aqui, pode ser melhor sair ou tentar continuar com cautela
            if not self.genai_model: # Se o modelo Gemini não foi inicializado, não podemos continuar.
                print("ERRO: genai.GenerativeModel não está inicializado, a população do ChromaDB falhará.")
                return 

        all_documents = []
        all_metadatas = []
        all_ids = []
        
        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()

            # Funções auxiliares para obter nome_tipo a partir de tipo_id (replicado do DataManager para self-contained)
            def _get_name_type_map(table_name_for_types):
                cursor.execute("SELECT id, nome_tipo FROM tipos_entidades WHERE nome_tabela = ?", (table_name_for_types,))
                return {row['id']: row['nome_tipo'] for row in cursor.fetchall()}

            locais_tipos_map = _get_name_type_map('locais')
            elementos_tipos_map = _get_name_type_map('elementos_universais')
            personagens_tipos_map = _get_name_type_map('personagens')
            faccoes_tipos_map = _get_name_type_map('faccoes')


            # Processar Locais
            cursor.execute("SELECT id_canonico, nome, tipo_id, perfil_json FROM locais")
            for row in cursor.fetchall():
                id_canonico = row['id_canonico']
                nome = row['nome']
                tipo_nome = locais_tipos_map.get(row['tipo_id'], 'Desconhecido') # Usar o mapa
                perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
                text_content = f"Local: {nome}. Tipo: {tipo_nome}. Descrição: {perfil_json.get('descricao', 'N/A')}. Propriedades: {json.dumps(perfil_json)}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo": "local", "nome": nome, "subtipo": tipo_nome})
                all_ids.append(f"local_{id_canonico}")

            # Processar Elementos Universais (Tecnologias, Magias, Recursos)
            cursor.execute("SELECT id_canonico, nome, tipo_id, perfil_json FROM elementos_universais")
            for row in cursor.fetchall():
                id_canonico = row['id_canonico']
                nome = row['nome']
                tipo_nome = elementos_tipos_map.get(row['tipo_id'], 'Desconhecido')
                perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
                text_content = f"Elemento Universal ({tipo_nome}): {nome}. Detalhes: {json.dumps(perfil_json)}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo": "elemento_universal", "nome": nome, "subtipo": tipo_nome})
                all_ids.append(f"elemento_{id_canonico}")

            # Processar Personagens
            cursor.execute("SELECT id_canonico, nome, tipo_id, perfil_json FROM personagens")
            for row in cursor.fetchall():
                id_canonico = row['id_canonico']
                nome = row['nome']
                tipo_nome = personagens_tipos_map.get(row['tipo_id'], 'Desconhecido')
                perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
                text_content = f"Personagem ({tipo_nome}): {nome}. Descrição: {perfil_json.get('personalidade', 'N/A')}. Histórico: {perfil_json.get('historico', 'N/A')}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo": "personagem", "nome": nome, "subtipo": tipo_nome})
                all_ids.append(f"personagem_{id_canonico}")

            # Processar Facções
            cursor.execute("SELECT id_canonico, nome, tipo_id, perfil_json FROM faccoes")
            for row in cursor.fetchall():
                id_canonico = row['id_canonico']
                nome = row['nome']
                tipo_nome = faccoes_tipos_map.get(row['tipo_id'], 'Desconhecido')
                perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
                text_content = f"Facção ({tipo_nome}): {nome}. Ideologia: {perfil_json.get('ideologia', 'N/A')}. Influência: {perfil_json.get('influencia', 'N/A')}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo": "faccao", "nome": nome, "subtipo": tipo_nome})
                all_ids.append(f"faccao_{id_canonico}")

            # Processar Jogador (Character)
            cursor.execute("SELECT id_canonico, nome, perfil_completo_json FROM jogador")
            for row in cursor.fetchall():
                id_canonico = row['id_canonico']
                nome = row['nome']
                perfil_completo_json = json.loads(row['perfil_completo_json']) if row['perfil_completo_json'] else {}
                text_content = f"O Jogador principal: {nome} (ID: {id_canonico}). Raça: {perfil_completo_json.get('raca', 'N/A')}. Ocupação: {perfil_completo_json.get('ocupacao', 'N/A')}. Personalidade: {perfil_completo_json.get('personalidade', 'N/A')}."
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": id_canonico, "tipo": "jogador", "nome": nome})
                all_ids.append(f"jogador_{id_canonico}")

            # Processar Posses do Jogador
            cursor.execute("SELECT id_canonico, item_nome, perfil_json, jogador_id FROM jogador_posses")
            for row in cursor.fetchall():
                posse_id_canonico = row['id_canonico'] 
                item_nome = row['item_nome']
                jogador_id_db = row['jogador_id']

                cursor.execute("SELECT id_canonico FROM jogador WHERE id = ?", (jogador_id_db,))
                jogador_id_canonico_result = cursor.fetchone()
                jogador_id_canonico = jogador_id_canonico_result['id_canonico'] if jogador_id_canonico_result else "unknown_player"

                perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
                text_content = f"Posse: {item_nome} (ID: {posse_id_canonico}) de {jogador_id_canonico}. Detalhes: {json.dumps(perfil_json)}"
                
                all_documents.append(text_content)
                all_metadatas.append({"id_canonico": posse_id_canonico, "tipo": "posse", "nome": item_nome, "jogador": jogador_id_canonico})
                all_ids.append(posse_id_canonico)


        print(f"INFO: Total de {len(all_documents)} documentos coletados para embedding.")
        
        # Gerar embeddings em lotes e adicionar ao ChromaDB
        if all_documents:
            batch_size = 10 # Tamanho do lote. Ajuste conforme limites da API e desempenho.
            for i in range(0, len(all_documents), batch_size):
                documents_batch = all_documents[i:i+batch_size]
                metadatas_batch = all_metadatas[i:i+batch_size]
                ids_batch = all_ids[i:i+batch_size]

                embeddings_batch = []
                # Gerar embeddings para cada documento no lote
                for doc_text in documents_batch: 
                    embed = await self._get_embedding(doc_text)
                    if embed:
                        embeddings_batch.append(embed)
                    else:
                        # Fallback: se o embedding falhar, use um vetor de zeros
                        embeddings_batch.append([0.0] * 768) 

                # Adicionar lote ao ChromaDB SOMENTE se os embeddings foram gerados (ou tiveram fallback)
                if embeddings_batch and len(embeddings_batch) == len(ids_batch): 
                    try:
                        self.collection.add(
                            embeddings=embeddings_batch,
                            documents=documents_batch,
                            metadatas=metadatas_batch,
                            ids=ids_batch
                        )
                        print(f"INFO: Lote {i // batch_size + 1}/{ (len(all_documents) + batch_size - 1) // batch_size } de embeddings adicionado ao ChromaDB.")
                    except Exception as e:
                        print(f"ERRO ao adicionar lote ao ChromaDB: {e}")
                else:
                    print(f"AVISO: Lote de embeddings/IDs inconsistente ou vazio no lote {i // batch_size + 1}. Não adicionado.")
        else:
            print("AVISO: Nenhuns documentos para adicionar ao ChromaDB.")

        print("\nSUCESSO: Coleção ChromaDB populada com embeddings da lore.")

    async def add_or_update_lore(self, id_canonico_principal, text_content, metadata):
        """
        Adiciona ou atualiza um documento de lore no ChromaDB.
        Usado para canonização dinâmica de nova lore.
        id_canonico_principal: Um ID canônico único para a lore (geralmente o id_canonico da entidade).
        """
        # Garante que o ID para o ChromaDB seja único e representativo
        doc_id = f"{metadata.get('tipo', 'unknown')}_{id_canonico_principal}"
        
        print(f"INFO: Adicionando/Atualizando lore no ChromaDB para '{doc_id}'...")
        embedding = await self._get_embedding(text_content)
        
        if embedding:
            try:
                # O método add() do ChromaDB com um ID existente já faz o update.
                self.collection.add(
                    embeddings=[embedding],
                    documents=[text_content],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
                print(f"INFO: Lore '{doc_id}' adicionada/atualizada no ChromaDB.")
            except Exception as e:
                print(f"ERRO ao adicionar/atualizar lore '{doc_id}' no ChromaDB: {e}")
        else:
            print(f"AVISO: Não foi possível gerar embedding para '{doc_id}'. Lore não adicionada.")


    async def find_relevant_lore(self, query_text, n_results=5):
        """
        Busca lore relevante no ChromaDB com base em uma query de texto.
        """
        print(f"INFO: Buscando lore relevante para a query: '{query_text[:50]}...'")
        query_embedding = await self._get_embedding(query_text)

        if not query_embedding:
            print("AVISO: Não foi possível gerar embedding para a query. Retornando vazio.")
            return []

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            print(f"INFO: Encontrados {len(results['documents'][0])} resultados de lore.")
            
            # Formata os resultados para facilitar o consumo
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
            print(f"ERRO ao buscar lore no ChromaDB: {e}")
            return []

# --- Ponto de Entrada para Teste Direto (Opcional) ---
async def main_test():
    """Função principal assíncrona para testar o ChromaDBManager diretamente."""
    print("--- Testando ChromaDBManager ---")
    chroma_manager = ChromaDBManager()

    # Certifique-se de que o build_world.py e main.py foram executados antes
    # para popular o estado.db com dados.
    print("\nIniciando população da coleção ChromaDB a partir do SQLite...")
    await chroma_manager.build_collection_from_sqlite()

    print("\n--- Testando busca de lore relevante ---")
    query1 = "Quero saber sobre os laboratórios da estação."
    results1 = await chroma_manager.find_relevant_lore(query1)
    for r in results1:
        print(f"  Documento: {r['document'][:100]}...")
        print(f"  Metadata: {r['metadata']}")
        print(f"  Distância: {r['distance']}\n")

    query2 = "Quem é Gabriel?"
    results2 = await chroma_manager.find_relevant_lore(query2, n_results=2)
    for r in results2:
        print(f"  Documento: {r['document'][:100]}...")
        print(f"  Metadata: {r['metadata']}")
        print(f"  Distância: {r['distance']}\n")

if __name__ == '__main__':
    # Para executar este teste diretamente: python servidor/chromadb_manager.py
    # Certifique-se de que o build_world.py e main.py (com _setup_initial_campaign)
    # foram executados pelo menos uma vez antes para popular o estado.db.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_test())

