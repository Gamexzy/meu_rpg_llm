import sqlite3
import os
import json
import yaml

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PROD_DATA_DIR = os.path.join(PROJECT_ROOT, 'dados_em_producao')
DB_PATH = os.path.join(PROD_DATA_DIR, 'estado.db')

class DataManager:
    """
    API do Mundo - A única camada que interage diretamente com a base de dados.
    Abstrai as consultas SQL e fornece métodos simples para o motor do jogo
    obter e modificar o estado do universo.
    """

    def __init__(self, db_path=DB_PATH):
        """
        Inicializa o DataManager e estabelece a conexão com a base de dados.
        
        Args:
            db_path (str): O caminho para o ficheiro da base de dados SQLite.
        """
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"A base de dados não foi encontrada em '{self.db_path}'. "
                                    "Por favor, execute o script 'scripts/build_world.py' primeiro.")
        print(f"DataManager conectado com sucesso a: {self.db_path}")

    def _get_connection(self):
        """Retorna uma nova conexão com a base de dados."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_local_details(self, local_id):
        """
        Busca os detalhes completos de um local específico a partir do seu perfil YAML.
        """
        print(f"Buscando detalhes para o local ID: {local_id}...")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT perfil_yaml FROM locais WHERE id = ?", (local_id,))
                resultado = cursor.fetchone()
                if resultado and resultado['perfil_yaml']:
                    return yaml.safe_load(resultado['perfil_yaml'])
                return None
        except (sqlite3.Error, yaml.YAMLError) as e:
            print(f"Erro ao buscar ou processar detalhes do local {local_id}: {e}")
            return None
            
    def get_tecnologias_for_local(self, local_id):
        """
        NOVA FUNÇÃO: Busca todas as tecnologias para um local específico
        usando a tabela de ligação. É muito mais eficiente.
        
        Args:
            local_id (str): O ID do local.

        Returns:
            list: Uma lista de dicionários, cada um representando uma tecnologia.
                  Retorna uma lista vazia se não encontrar ou em caso de erro.
        """
        print(f"\nBuscando tecnologias para o local ID: {local_id} via JOIN...")
        query = """
            SELECT T.id, T.nome, T.perfil_yaml
            FROM tecnologias T
            JOIN local_tecnologias LT ON T.id = LT.tecnologia_id
            WHERE LT.local_id = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (local_id,))
                rows = cursor.fetchall()
                # Transforma cada linha (que é um objeto sqlite3.Row) num dicionário completo
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Erro ao buscar tecnologias para o local via JOIN: {e}")
            return []

# --- Exemplo de Uso ---
# Esta parte do código só será executada se o script for chamado diretamente.
if __name__ == '__main__':
    print("--- Testando o DataManager (v2) ---")
    
    # É uma boa prática reconstruir a DB para garantir que os testes são consistentes
    build_script_path = os.path.join(PROJECT_ROOT, 'scripts', 'build_world.py')
    if os.path.exists(build_script_path):
        print("\nExecutando 'build_world.py' para garantir uma base de dados limpa e atualizada...")
        os.system(f'python "{build_script_path}"')
    else:
        print(f"AVISO: Script de construção não encontrado em {build_script_path}")

    try:
        data_manager = DataManager()
        local_de_teste_id = "estacao_vigilancia_solaris"

        # Testar a nova função
        tecnologias = data_manager.get_tecnologias_for_local(local_de_teste_id)

        if tecnologias:
            print(f"\n[SUCESSO] Tecnologias encontradas para '{local_de_teste_id}':")
            nomes_tecs = [tec['nome'] for tec in tecnologias]
            print(json.dumps(nomes_tecs, indent=2, ensure_ascii=False))
        else:
            print(f"\n[AVISO] Nenhuma tecnologia encontrada para o local ID: {local_de_teste_id}. Verifique o YAML e o script de build.")

    except FileNotFoundError as e:
        print(f"\nERRO CRÍTICO: {e}")
    except Exception as e:
        print(f"\nOcorreu um erro inesperado durante o teste: {e}")

