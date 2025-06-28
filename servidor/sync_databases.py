import os
import sys
import asyncio
import shutil # Importado para remoção de diretórios

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
    Versão: 1.0.4 - Adicionada funcionalidade para resetar todos os bancos de dados.
    """
    def __init__(self):
        print("--- Inicializando Sincronizador de Bases de Dados (v1.0.4) ---")
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
        
        # A lista de tabelas não inclui 'tipos_entidades' após a remoção dessa funcionalidade
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
            'relacoes_entidades'
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
        
        print("INFO: O esquema do SQLite e o diretório do ChromaDB não serão recriados ou limpos automaticamente por este script na sincronização.")
        print("AVISO: Certifique-se de que o 'build_world.py' foi executado pelo menos uma vez para criar o esquema inicial.")
        print("AVISO: A população inicial do SQLite com dados de campanha (jogador, locais, etc.)")
        print("AVISO: é feita pelo 'main.py' (com lógica de criação inicial) ou por métodos diretos do DataManager.")
        
        # Passo 1: Ler todos os dados do SQLite usando o DataManager
        all_sqlite_data = await self._get_all_data_from_sqlite()

        # Passo 2: Constrói o Neo4j a partir dos dados do DataManager
        print("\n--- Construindo o Neo4j (Pilar C) ---")
        # O build_graph_from_data já limpa e recria o grafo Neo4j internamente,
        # então os dados existentes serão substituídos pelos dados do SQLite.
        await self.neo4j_manager.build_graph_from_data(all_sqlite_data)
        print("SUCESSO: Neo4j sincronizado.")
        # self.neo4j_manager.close() # A conexão é fechada pelo próprio manager em cada sessão

        # Passo 3: Constrói o ChromaDB a partir dos dados do DataManager
        print("\n--- Construindo o ChromaDB (Pilar A) ---")
        # O build_collection_from_data já deleta e recria a coleção ChromaDB internamente,
        # garantindo que ela seja populada com a dimensão correta.
        await self.chroma_manager.build_collection_from_data(all_sqlite_data)
        print("SUCESSO: ChromaDB sincronizado.")

        print("\n--- Sincronização COMPLETA dos Pilares de Dados CONCLUÍDA ---")

    async def reset_all_databases(self):
        """
        Executa um reset completo de todos os bancos de dados:
        1. Deleta o arquivo SQLite.
        2. Deleta o diretório do ChromaDB.
        3. Limpa o Neo4j (detaching e deletando todos os nós e relações).
        4. Re-executa build_world.py para recriar o esquema SQLite vazio.
        """
        print("\n!!! ATENÇÃO: INICIANDO RESET COMPLETO DE TODOS OS BANCOS DE DADOS !!!")
        print("!!! TODOS OS DADOS PERSISTIDOS SERÃO APAGADOS IRREVERSIVELMENTE !!!\n")
        
        # 1. Deletar SQLite
        if os.path.exists(config.DB_PATH_SQLITE):
            os.remove(config.DB_PATH_SQLITE)
            print(f"INFO: Arquivo SQLite deletado: {config.DB_PATH_SQLITE}")
        else:
            print(f"INFO: Arquivo SQLite não encontrado, nada para deletar: {config.DB_PATH_SQLITE}")

        # 2. Deletar ChromaDB
        if os.path.exists(config.CHROMA_PATH):
            try:
                shutil.rmtree(config.CHROMA_PATH)
                print(f"INFO: Diretório ChromaDB deletado: {config.CHROMA_PATH}")
            except OSError as e:
                print(f"ERRO: Falha ao deletar diretório ChromaDB {config.CHROMA_PATH}: {e}")
        else:
            print(f"INFO: Diretório ChromaDB não encontrado, nada para deletar: {config.CHROMA_PATH}")

        # 3. Limpar Neo4j
        print("INFO: Limpando banco de dados Neo4j...")
        try:
            with self.neo4j_manager.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            print("INFO: Neo4j limpo com sucesso.")
        except Exception as e:
            print(f"ERRO: Falha ao limpar Neo4j: {e}")
            # Se o Neo4j não estiver rodando ou houver erro de conexão, a limpeza pode falhar.
            # No entanto, vamos prosseguir com a recriação do esquema SQLite.

        # 4. Re-executar build_world.py para recriar o esquema SQLite vazio
        build_script_path = os.path.join(config.BASE_DIR, 'scripts', 'build_world.py')
        if os.path.exists(build_script_path):
            print(f"\nINFO: Re-executando '{build_script_path}' para recriar o esquema do DB...")
            os.system(f'python "{build_script_path}"')
            print("INFO: Esquema SQLite recriado com sucesso.")
        else:
            print(f"ERRO: Script 'build_world.py' não encontrado em '{build_script_path}'. Não foi possível recriar o esquema SQLite.")
            sys.exit(1)

        print("\n--- RESET COMPLETO DE BANCOS DE DADOS CONCLUÍDO ---")
        print("O sistema está agora em um estado de 'folha em branco'.")


async def main():
    """
    Função principal assíncrona para executar o sincronizador ou resetar os bancos de dados.
    Uso: python sync_databases.py [--reset]
    """
    synchronizer = DatabaseSynchronizer()
    
    if "--reset" in sys.argv:
        await synchronizer.reset_all_databases()
    else:
        await synchronizer.sync_all_databases()

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
