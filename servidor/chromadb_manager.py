import os
import sys
import sqlite3
import json
import asyncio
import aiohttp
import chromadb
from chromadb.utils import embedding_functions

# Importar a biblioteca oficial google-generativeai.
# Ainda manteremos este import para outras funcionalidades do Gemini, se necessário,
# mas para embeddings, usaremos um modelo local.
import google.generativeai as genai

# Importar a biblioteca SentenceTransformer para modelos de embedding locais
from sentence_transformers import SentenceTransformer

# Importar as configurações globais
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
import config as config

class ChromaDBManager:
    """
    API dedicada para interagir com o Pilar A (Base de Dados Vetorial - ChromaDB).
    Responsável por armazenar e buscar embeddings para a lore do jogo.
    Versão: 1.3.8 - Alterado para usar modelo de embedding local (SentenceTransformer).
    """
    def __init__(self, chroma_path=config.CHROMA_PATH):
        """Inicializa o gestor e a conexão com o ChromaDB."""
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # Opcional: Ainda verificar a API Key do Gemini se você planeja usar outros recursos do Gemini
        # (além de embeddings, como geração de texto).
        if not config.GEMINI_API_KEY:
            print("AVISO: GEMINI_API_KEY não definida em config.py ou nas variáveis de ambiente. Chamadas para a API de geração de texto do Gemini podem falhar.")
            self.genai_initialized = False # Indica que a API remota do Gemini pode não funcionar
        else:
            self.genai_initialized = True
            print("INFO: Módulo google.generativeai inicializado (para LLM principal, API Key via variável de ambiente).")


        # Carregar um modelo de embedding local.
        # 'all-MiniLM-L6-v2' é um bom modelo leve e eficiente para começar (dimensão 384).
        # Você pode experimentar outros modelos maiores se precisar de mais precisão.
        print(f"INFO: Carregando modelo de embedding local: {config.EMBEDDING_MODEL}")
        try:
            # Note que EMBEDDING_MODEL agora será o nome de um modelo Sentence-Transformer
            self.local_embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
            # A dimensão do embedding será a do modelo carregado (ex: 384 para all-MiniLM-L6-v2)
            self.embedding_dimension = self.local_embedding_model.get_sentence_embedding_dimension()
            print(f"INFO: Modelo de embedding local '{config.EMBEDDING_MODEL}' carregado. Dimensão: {self.embedding_dimension}")
        except Exception as e:
            print(f"ERRO CRÍTICO: Falha ao carregar modelo de embedding local '{config.EMBEDDING_MODEL}': {e}")
            self.local_embedding_model = None
            self.embedding_dimension = 768 # Fallback, mas o ideal é que o modelo seja carregado
            
        # A coleção será obtida ou criada, e a dimensão será inferida do primeiro embedding adicionado.
        # Não especificamos embedding_function aqui para permitir a inferência.
        self.collection = self.chroma_client.get_or_create_collection(
            name="rpg_lore_collection"
        )
        print(f"INFO: ChromaDBManager conectado com sucesso ao Pilar A em: {chroma_path}")

    async def _get_embedding(self, text):
        """
        Gera um embedding para o texto fornecido usando o modelo de embedding local.
        """
        if not text:
            return []
        if not self.local_embedding_model: 
            print("ERRO: Modelo de embedding local não carregado. Não é possível gerar embeddings.")
            return []

        try:
            # Gerar embedding usando o modelo local
            embedding = self.local_embedding_model.encode(text).tolist()
            return embedding
        except Exception as e:
            print(f"ERRO ao gerar embedding com modelo local: {e}. Texto: {text[:50]}...")
            return [0.0] * self.embedding_dimension # Retorna um embedding vazio com a dimensão correta


    async def build_collection_from_data(self, all_sqlite_data):
        """
        Lê dados textuais de um dicionário 'all_sqlite_data' (que vem do DataManager),
        gera embeddings e os popula no ChromaDB. Força a limpeza e reconstrução da coleção.
        """
        print("\n--- A construir o Pilar A (ChromaDB) a partir de dados fornecidos ---")
        
        try:
            # Tenta deletar a coleção existente para garantir uma reconstrução limpa.
            # Ignora erros se a coleção não existir.
            try:
                self.chroma_client.delete_collection(name="rpg_lore_collection")
                print("INFO: Coleção ChromaDB 'rpg_lore_collection' existente deletada para reconstrução.")
            except Exception as e:
                # Pode falhar se a coleção não existir, o que é aceitável.
                print(f"AVISO: Não foi possível deletar a coleção ChromaDB (pode não existir): {e}")

            # Agora, obtém ou cria a coleção. A dimensão será inferida do primeiro embedding adicionado.
            self.collection = self.chroma_client.get_or_create_collection(
                name="rpg_lore_collection"
            )
            print("INFO: Coleção ChromaDB 'rpg_lore_collection' pronta para ser populada.")

        except Exception as e:
            print(f"AVISO: Erro ao configurar ou limpar a coleção ChromaDB: {e}")
            if not self.local_embedding_model: # Verifica se o modelo local foi inicializado
                print("ERRO: Modelo de embedding local não está inicializado, a população do ChromaDB falhará.")
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
        tipos_entidades_data = all_sqlite_data.get('tipos_entidades', [])

        tipos_map_locais = {row['id']: row['nome_tipo'] for row in tipos_entidades_data if row['nome_tabela'] == 'locais'}
        tipos_map_elementos = {row['id']: row['nome_tipo'] for row in tipos_entidades_data if row['nome_tabela'] == 'elementos_universais'}
        tipos_map_personagens = {row['id']: row['nome_tipo'] for row in tipos_entidades_data if row['nome_tabela'] == 'personagens'}
        tipos_map_faccoes = {row['id']: row['nome_tipo'] for row in tipos_entidades_data if row['nome_tabela'] == 'faccoes'}

        for row in locais_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo_nome = tipos_map_locais.get(row['tipo_id'], 'Desconhecido')
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Local: {nome}. Tipo: {tipo_nome}. Descrição: {perfil_json.get('descricao', 'N/A')}. Propriedades: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "local", "nome": nome, "subtipo": tipo_nome})
            all_ids.append(f"local_{id_canonico}")

        for row in elementos_universais_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo_nome = tipos_map_elementos.get(row['tipo_id'], 'Desconhecido')
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Elemento Universal ({tipo_nome}): {nome}. Detalhes: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "elemento_universal", "nome": nome, "subtipo": tipo_nome})
            all_ids.append(f"elemento_{id_canonico}")

        for row in personagens_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo_nome = tipos_map_personagens.get(row['tipo_id'], 'Desconhecido')
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Personagem ({tipo_nome}): {nome}. Descrição: {perfil_json.get('personalidade', 'N/A')}. Histórico: {perfil_json.get('historico', 'N/A')}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "personagem", "nome": nome, "subtipo": tipo_nome})
            all_ids.append(f"personagem_{id_canonico}")

        for row in faccoes_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            tipo_nome = tipos_map_faccoes.get(row['tipo_id'], 'Desconhecido')
            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Facção ({tipo_nome}): {nome}. Ideologia: {perfil_json.get('ideologia', 'N/A')}. Influência: {perfil_json.get('influencia', 'N/A')}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "faccao", "nome": nome, "subtipo": tipo_nome})
            all_ids.append(f"faccao_{id_canonico}")

        for row in jogador_data:
            id_canonico = row['id_canonico']
            nome = row['nome']
            perfil_completo_json = json.loads(row['perfil_completo_json']) if row['perfil_completo_json'] else {}
            text_content = f"O Jogador principal: {nome} (ID: {id_canonico}). Raça: {perfil_completo_json.get('raca', 'N/A')}. Ocupação: {perfil_completo_json.get('ocupacao', 'N/A')}. Personalidade: {perfil_completo_json.get('personalidade', 'N/A')}."
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": id_canonico, "tipo": "jogador", "nome": nome})
            all_ids.append(f"jogador_{id_canonico}")

        jogador_data_map = {j['id']: j['id_canonico'] for j in jogador_data}

        for row in jogador_posses_data:
            posse_id_canonico = row['id_canonico'] 
            item_nome = row['item_nome']
            jogador_id_db = row['jogador_id']
            jogador_id_canonico = jogador_data_map.get(jogador_id_db, "unknown_player")

            perfil_json = json.loads(row['perfil_json']) if row['perfil_json'] else {}
            text_content = f"Posse: {item_nome} (ID: {posse_id_canonico}) de {jogador_id_canonico}. Detalhes: {json.dumps(perfil_json, ensure_ascii=False)}"
            
            all_documents.append(text_content)
            all_metadatas.append({"id_canonico": posse_id_canonico, "tipo": "posse", "nome": item_nome, "jogador": jogador_id_canonico})
            all_ids.append(posse_id_canonico)

        print(f"INFO: Total de {len(all_documents)} documentos coletados para embedding.")
        
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
                        # Usar a dimensão inferida do modelo local ou um fallback seguro
                        embeddings_batch.append([0.0] * self.embedding_dimension) 

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
        doc_id = f"{metadata.get('tipo', 'unknown')}_{id_canonico_principal}"
        
        print(f"INFO: Adicionando/Atualizando lore no ChromaDB para '{doc_id}'...")
        embedding = await self._get_embedding(text_content)
        
        if embedding:
            try:
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

    print("\nIniciando população da coleção ChromaDB a partir do SQLite (para teste direto)...")
    mock_sqlite_data = {
        'locais': [{
            'id': 1,
            'id_canonico': 'estacao_base_alfa',
            'nome': 'Estação Base Alfa',
            'tipo_id': 3,
            'parent_id': None,
            'perfil_json': '{"funcao": "Hub de pesquisa e comércio.", "populacao": 500, "descricao": "Uma estação espacial movimentada."}'
        }],
        'tipos_entidades': [
            {'id': 1, 'nome_tabela': 'locais', 'nome_tipo': 'Planeta'},
            {'id': 2, 'nome_tabela': 'locais', 'nome_tipo': 'Cidade'},
            {'id': 3, 'nome_tabela': 'locais', 'nome_tipo': 'Estação Espacial'},
        ],
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
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_test())
