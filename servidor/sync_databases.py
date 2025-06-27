import os
import sys
import asyncio
# import shutil # Não precisamos mais de shutil se não vamos excluir o diretório

# Adiciona o diretório da raiz do projeto ao sys.path para que os módulos possam ser importados
# Assumindo que o script sync_databases.py está em meu_rpg_llm/servidor/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, 'config'))   # Para importar config
sys.path.append(os.path.join(PROJECT_ROOT, 'servidor')) # Para importar data_manager, chromadb_manager, neo4j_manager

# Importar as configurações globais
import config as config 

# Importar os gestores dos pilares
from data_manager import DataManager
from chromadb_manager import ChromaDBManager
from neo4j_manager import Neo4jManager

class DatabaseSynchronizer:
    """
    Orquestrador para a sincronização em lote de todos os pilares de dados (SQLite, Neo4j, ChromaDB).
    Responsabilidade: Ler todos os dados do SQLite e usá-los para construir/reconstruir
    os outros pilares, garantindo a consistência inicial.
    Versão: 1.0.3 - Removida exclusão forçada de bancos de dados. Agora persiste dados.
    """
    def __init__(self):
        print("--- Inicializando Sincronizador de Bases de Dados (v1.0.3) ---")
        self.data_manager = DataManager() 
        self.chroma_manager = ChromaDBManager()
        self.neo4j_manager = Neo4jManager()
        print("INFO: Gestores de pilares inicializados.")

    async def _get_all_data_from_sqlite(self):
        """
        Lê e retorna todos os dados relevantes do SQLite em um formato estruturado (dicionário de listas).
        Utiliza o DataManager para essa leitura.
        """
        print("INFO: A recolher todos os dados canónicos do SQLite (Pilar B) através do DataManager...")
        
        all_data = {}
        
        tables_to_export = [
            'locais', 
            'elementos_universais', 
            'personagens', 
            'faccoes', 
            'jogador', 
            'jogador_habilidades', 
            'jogador_conhecimentos', 
            'jogador_posses',
            'jogador_status_fisico_emocional', 
            'jogador_logs_memoria',
            'local_elementos', 
            'locais_acessos_diretos', 
            'relacoes_entidades', 
            'tipos_entidades'
        ]

        for table_name in tables_to_export:
            all_data[table_name] = self.data_manager.get_all_entities_from_table(table_name)
        
        print(f"INFO: Dados recolhidos do SQLite. Total de entidades por tabela:")
        for table, records in all_data.items():
            print(f"  - {table}: {len(records)} registros")
        
        return all_data


    async def sync_all_databases(self):
        """
        Executa o processo completo de sincronização:
        1. Lê todos os dados do SQLite (sem recriar o esquema ou limpar).
        2. Constrói o Neo4j a partir desses dados.
        3. Constrói o ChromaDB a partir desses dados.
        """
        print("\n--- Iniciando Sincronização COMPLETA dos Pilares de Dados ---")
        
        # REMOVIDO: os.system(f'python "{build_world_script_path}"')
        # REMOVIDO: Lógica de exclusão física do diretório do ChromaDB.
        
        print("INFO: O esquema do SQLite e o diretório do ChromaDB não serão recriados ou limpos automaticamente por este script.")
        print("AVISO: Certifique-se de que o 'build_world.py' foi executado pelo menos uma vez para criar o esquema inicial.")
        print("AVISO: A população inicial do SQLite com dados de campanha (jogador, locais, etc.)")
        print("AVISO: é feita pelo 'main.py' (com '_setup_initial_campaign') ou por métodos diretos do DataManager.")
        
        # Passo 1: Ler todos os dados do SQLite usando o DataManager
        all_sqlite_data = await self._get_all_data_from_sqlite()

        # Passo 2: Constrói o Neo4j a partir dos dados do DataManager
        print("\n--- Construindo o Neo4j (Pilar C) ---")
        # O build_graph_from_data já limpa e recria o grafo Neo4j internamente,
        # então os dados existentes serão substituídos pelos dados do SQLite.
        await self.neo4j_manager.build_graph_from_data(all_sqlite_data)
        print("SUCESSO: Neo4j sincronizado.")
        self.neo4j_manager.close()

        # Passo 3: Constrói o ChromaDB a partir dos dados do DataManager
        print("\n--- Construindo o ChromaDB (Pilar A) ---")
        # O build_collection_from_data já deleta e recria a coleção ChromaDB internamente,
        # garantindo que ela seja populada com a dimensão correta.
        await self.chroma_manager.build_collection_from_data(all_sqlite_data)
        print("SUCESSO: ChromaDB sincronizado.")

        print("\n--- Sincronização COMPLETA dos Pilares de Dados CONCLUÍDA ---")

async def main():
    """Função principal assíncrona para executar o sincronizador."""
    synchronizer = DatabaseSynchronizer()
    await synchronizer.sync_all_databases()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
