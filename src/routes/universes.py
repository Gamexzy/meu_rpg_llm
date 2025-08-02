# src/routes/universes.py
import logging
import sqlite3
from flask import Blueprint, request, jsonify, g
from src.database.central_db_manager import CentralDbManager
from src.database.chromadb_manager import ChromaDBManager
from src.utils.auth import token_required
from src import config
from scripts import build_world

universes_bp = Blueprint('universes_bp', __name__)
central_db_manager = CentralDbManager()
chromadb_manager = ChromaDBManager()

@universes_bp.route('/universes/create', methods=['POST'])
@token_required
def create_universe():
    """
    Cria um novo universo completo (registro central, DB de universo, coleção de lore).
    Requer no corpo do JSON: name (str), description (str)
    """
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    user_id = g.current_user_id

    if not name:
        return jsonify({"error": "O nome do universo é obrigatório"}), 400

    universe_id = None
    try:
        # 1. Criar o registro no banco de dados central para obter um ID
        # Passamos um caminho temporário que será atualizado se a criação for bem-sucedida
        temp_db_path = "pending"
        universe_id = central_db_manager.create_universe(user_id, name, description, temp_db_path)

        # 2. Construir o banco de dados SQLite específico do universo
        universe_db_path = config.DB_PATH_UNIVERSE_TEMPLATE.format(universe_id=universe_id)
        conn = sqlite3.connect(universe_db_path)
        build_world.setup_universe_database(conn.cursor())
        conn.commit()
        conn.close()

        # 3. Atualizar o caminho do DB no registro central
        central_db_manager.update_universe_db_path(universe_id, universe_db_path)

        # 4. Garantir que a coleção de lore no ChromaDB seja criada
        chromadb_manager.get_or_create_universe_collection(universe_id)

        logging.info(f"Universo {universe_id} ('{name}') provisionado com sucesso para o usuário {user_id}.")

        return jsonify({
            "message": "Universo criado com sucesso!",
            "universe": {"id": universe_id, "name": name, "description": description}
        }), 201

    except Exception as e:
        logging.error(f"Falha crítica ao criar universo para o usuário {user_id}: {e}", exc_info=True)
        # Lógica de rollback: se algo deu errado, apagar o que foi criado
        if universe_id:
            # Implementar funções de limpeza em seus gerenciadores
            # central_db_manager.delete_universe(universe_id)
            # chromadb_manager.delete_universe_collection(universe_id)
            # os.remove(config.DB_PATH_UNIVERSE_TEMPLATE.format(universe_id=universe_id))
            pass
        return jsonify({"error": "Falha ao criar o universo."}), 500


@universes_bp.route('/universes', methods=['GET'])
@token_required
def get_universes():
    """Retorna a lista de universos do usuário logado."""
    user_id = g.current_user_id
    try:
        universes = central_db_manager.get_user_universes(user_id)
        return jsonify(universes), 200
    except Exception as e:
        logging.error(f"Erro ao listar universos para o usuário {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao buscar universos."}), 500
