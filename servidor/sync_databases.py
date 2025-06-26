import os
import sys
import asyncio
import shutil # Importar shutil para exclusão de diretórios

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
    Versão: 1.0.2 - Adicionada limpeza forçada do diretório do ChromaDB.
    """
    def __init__(self):
        print("--- Inicializando Sincronizador de Bases de Dados (v1.0.2) ---")
        # O DataManager não recebe chroma_manager aqui, conforme a nova arquitetura
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
        
        # Lista de todas as tabelas das quais queremos exportar os dados
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
            'tipos_entidades' # Necessário para o mapeamento de tipos nos outros pilares
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
        1. Limpa e recria o esquema do SQLite (via build_world.py externo).
        2. Limpa fisicamente o diretório do ChromaDB.
        3. Lê todos os dados do SQLite.
        4. Constrói o Neo4j a partir desses dados.
        5. Constrói o ChromaDB a partir desses dados.
        """
        print("\n--- Iniciando Sincronização COMPLETA dos Pilares de Dados ---")
        
        # Passo 1: Garantir que o esquema do SQLite esteja limpo e pronto (chamando build_world.py)
        print("INFO: A executar build_world.py para criar/limpar o esquema do SQLite...")
        build_world_script_path = os.path.join(PROJECT_ROOT, 'scripts', 'build_world.py')
        os.system(f'python "{build_world_script_path}"')
        print("INFO: Esquema do SQLite criado/limpo.")

        # NOVO: Passo 2: Excluir fisicamente o diretório do ChromaDB para garantir uma recriação limpa
        chroma_db_path = config.CHROMA_PATH
        if os.path.exists(chroma_db_path):
            print(f"INFO: Excluindo diretório existente do ChromaDB em '{chroma_db_path}' para garantir uma recriação limpa...")
            try:
                shutil.rmtree(chroma_db_path)
                print("INFO: Diretório do ChromaDB excluído com sucesso.")
            except Exception as e:
                print(f"ERRO: Falha ao excluir o diretório do ChromaDB: {e}. Por favor, exclua manualmente se o problema persistir.")
                # Se não puder excluir, não podemos garantir a dimensão correta.
                # Continuamos, mas o erro pode persistir.
        else:
            print(f"INFO: Diretório do ChromaDB '{chroma_db_path}' não encontrado. Criará um novo.")


        # Passo 3: População inicial do SQLite.
        # Este script assume que o main.py (ou setup_initial_campaign)
        # foi executado PELO MENOS UMA VEZ para popular o SQLite com os dados INICIAIS de campanha.
        # Ele não fará a população do SQLite por si só.
        print("\nAVISO: A população inicial do SQLite com dados de campanha (jogador, locais, etc.)")
        print("AVISO: não é feita por este script. Certifique-se de que o 'main.py' (com '_setup_initial_campaign')")
        print("AVISO: foi executado pelo menos uma vez para popular o SQLite antes de rodar este sincronizador,")
        print("AVISO: ou o Neo4j e ChromaDB estarão vazios.")
        
        # Passo 4: Ler todos os dados do SQLite usando o DataManager
        all_sqlite_data = await self._get_all_data_from_sqlite()

        # Passo 5: Constrói o Neo4j a partir dos dados do DataManager
        print("\n--- Construindo o Neo4j (Pilar C) ---")
        await self.neo4j_manager.build_graph_from_data(all_sqlite_data) # AGORA PASSA OS DADOS
        print("SUCESSO: Neo4j sincronizado.")
        self.neo4j_manager.close() # Fechar a conexão do Neo4j após a construção

        # Passo 6: Constrói o ChromaDB a partir dos dados do DataManager
        print("\n--- Construindo o ChromaDB (Pilar A) ---")
        await self.chroma_manager.build_collection_from_data(all_sqlite_data) # AGORA PASSA OS DADOS
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

