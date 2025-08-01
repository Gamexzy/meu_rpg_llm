import os
import sys
import asyncio
import shutil
from src import config 
from src.database.sqlite_manager import SqliteManager
from src.database.chromadb_manager import ChromaDBManager
from src.database.neo4j_manager import Neo4jManager


class DatabaseSynchronizer:
    """
    Orquestrador para a sincronização em lote de todos os pilares de dados.
    Versão: 1.2.0 - Corrigida a inicialização do ChromaDBManager.
    """
    def __init__(self):
        """
        Inicializa o sincronizador. Os managers são inicializados como None
        e serão criados sob demanda.
        """
        print("--- Inicializando Sincronizador de Bases de Dados (v1.2.0) ---")
        self.data_manager = None
        self.chroma_manager = None
        self.neo4j_manager = None

    def _initialize_managers(self):
        """Inicializa os gestores de banco de dados quando necessário."""
        if self.data_manager is None:
            self.data_manager = SqliteManager()
        if self.chroma_manager is None:
            # A inicialização do ChromaDB agora é silenciosa por padrão
            self.chroma_manager = ChromaDBManager() # CORREÇÃO: Removido o argumento 'verbose'
        if self.neo4j_manager is None:
            self.neo4j_manager = Neo4jManager()
        print("INFO: Gestores de pilares inicializados para sincronização.")

    async def _get_all_data_from_sqlite(self):
        """Lê e retorna todos os dados relevantes do SQLite."""
        print("INFO: A recolher todos os dados canónicos do SQLite...")
        
        all_data = {}
        tables_to_export = [
            'locais', 'elementos_universais', 'personagens', 'faccoes',
            'jogador', 'jogador_habilidades', 'jogador_conhecimentos', 
            'jogador_posses', 'jogador_status_fisico_emocional', 'jogador_logs_memoria',
            'local_elementos', 'locais_acessos_diretos', 'relacoes_entidades'
        ]

        for table_name in tables_to_export:
            all_data[table_name] = self.data_manager.get_all_entities_from_table(table_name)

        print("INFO: Dados recolhidos do SQLite. Total de tabelas")
        return all_data

    async def sync_all_databases(self):
        """Executa o processo completo de sincronização."""
        print("\n--- Iniciando Sincronização COMPLETA dos Pilares de Dados ---")
        self._initialize_managers()
        
        all_sqlite_data = await self._get_all_data_from_sqlite()

        print("\n--- Construindo o Neo4j (Pilar C) ---")
        await self.neo4j_manager.build_graph_from_data(all_sqlite_data)

        print("\n--- Construindo o ChromaDB (Pilar A) ---")
        await self.chroma_manager.build_collection_from_data(all_sqlite_data)

        print("\n--- Sincronização COMPLETA dos Pilares de Dados CONCLUÍDA ---")

    async def reset_all_databases(self):
        """Executa um reset completo de todos os bancos de dados."""
        print("\n!!! ATENÇÃO: INICIANDO RESET COMPLETO DE TODOS OS BANCOS DE DADOS !!!")
        # Remove todos os arquivos .db do diretório de produção, exceto o central.db
        for filename in os.listdir(config.PROD_DATA_DIR):
            if filename.endswith(".db") and filename != "central.db":
                file_path = os.path.join(config.PROD_DATA_DIR, filename)
                os.remove(file_path)
                print(f"INFO: Arquivo de sessão '{filename}' deletado.")

        if os.path.exists(config.CHROMA_PATH):
            shutil.rmtree(config.CHROMA_PATH)
            print("INFO: Diretório ChromaDB deletado.")

        print("INFO: Limpando banco de dados Neo4j...")
        try:
            if self.neo4j_manager is None:
                self.neo4j_manager = Neo4jManager()
            with self.neo4j_manager.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            print("INFO: Neo4j limpo com sucesso.")
        except Exception as e:
            print(f"AVISO: Falha ao limpar Neo4j (pode não estar a correr): {e}")

        print("\nINFO: Recriando o esquema do DB...")
        build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py')
        os.system(f'python "{build_script_path}" --target central') # Recria apenas o DB central por enquanto
        
        print("\n--- RESET COMPLETO DE BANCOS DE DADOS CONCLUÍDO ---")

async def main():
    """Função principal para executar o sincronizador ou resetar os bancos de dados."""
    synchronizer = DatabaseSynchronizer()
    
    if "--reset" in sys.argv:
        await synchronizer.reset_all_databases()
    else:
        await synchronizer.sync_all_databases()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
