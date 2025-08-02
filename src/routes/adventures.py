# src/routes/adventures.py
import logging
import os
from flask import Blueprint, request, jsonify, g
from src.database.central_db_manager import CentralDbManager
from src.utils.auth import token_required
from src import config

adventures_bp = Blueprint('adventures_bp', __name__)
central_db_manager = CentralDbManager()

@adventures_bp.route('/adventures/start', methods=['POST'])
@token_required
def start_adventure():
    """
    Inicia uma nova aventura, conectando personagens a um universo.
    Requer no corpo do JSON:
    - name (str): O nome da aventura.
    - universe_id (int): O ID do universo onde a aventura acontece.
    - character_ids (list[int]): Uma lista com os IDs dos personagens participantes.
    """
    data = request.get_json()
    adventure_name = data.get('name')
    universe_id = data.get('universe_id')
    character_ids = data.get('character_ids')
    user_id = g.current_user_id

    # --- Validações Iniciais ---
    if not all([adventure_name, universe_id, character_ids]):
        return jsonify({"error": "Nome da aventura, ID do universo e lista de IDs de personagens são obrigatórios."}), 400
    if not isinstance(character_ids, list) or not character_ids:
        return jsonify({"error": "'character_ids' deve ser uma lista não vazia de IDs."}), 400

    adventure_id = None
    try:
        # --- Verificar Propriedade e Disponibilidade dos Personagens ---
        characters_to_add = []
        for char_id in character_ids:
            char_details = central_db_manager.get_character_details(char_id, user_id)
            if not char_details:
                return jsonify({"error": f"Personagem com ID {char_id} não encontrado ou não pertence a você."}), 404
            
            if char_details['is_traveler'] and char_details['current_adventure_id'] is not None:
                return jsonify({"error": f"O personagem Viajante '{char_details['name']}' já está em uma aventura ativa."}), 409
            
            characters_to_add.append(char_details)

        # --- Orquestração da Criação da Aventura ---
        # 1. Criar o registro da aventura no DB central para obter um ID
        temp_db_path = "pending_creation"
        adventure_id = central_db_manager.create_adventure(adventure_name, universe_id, temp_db_path)

        # 2. Construir o banco de dados SQLite específico da aventura
        adventure_db_path = config.DB_PATH_ADVENTURE_TEMPLATE.format(adventure_id=adventure_id)
        os.system(f'python "{os.path.join("scripts", "build_world.py")}" --target adventure --id {adventure_id}')

        # 3. ATUALIZAR o caminho no DB central com o caminho real
        central_db_manager.update_adventure_db_path(adventure_id, adventure_db_path)

        # 4. Adicionar os participantes e travar os viajantes
        for char in characters_to_add:
            central_db_manager.add_character_to_adventure(adventure_id, char['id'], user_id)
            if char['is_traveler']:
                central_db_manager.lock_traveler_character(char['id'], adventure_id)

        logging.info(f"Aventura '{adventure_name}' (ID: {adventure_id}) iniciada com sucesso.")

        return jsonify({
            "message": "Aventura iniciada com sucesso!",
            "adventure_id": adventure_id
        }), 201

    except Exception as e:
        logging.error(f"Falha crítica ao iniciar aventura para o usuário {user_id}: {e}", exc_info=True)
        # Adicionar lógica de rollback aqui se necessário (apagar o registro da aventura, etc.)
        return jsonify({"error": "Falha ao iniciar a aventura."}), 500
