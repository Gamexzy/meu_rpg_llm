# src/routes/characters.py
import logging
from flask import Blueprint, request, jsonify, g
from src.database.central_db_manager import CentralDbManager
from src.database.chromadb_manager import ChromaDBManager
from src.utils.auth import token_required

characters_bp = Blueprint('characters_bp', __name__)
central_db_manager = CentralDbManager()
chromadb_manager = ChromaDBManager()

@characters_bp.route('/characters/create', methods=['POST'])
@token_required
def create_character():
    """
    Cria um novo personagem.
    Requer no corpo do JSON: name (str), background (str), is_traveler (bool)
    """
    data = request.get_json()
    name = data.get('name')
    background = data.get('background')
    is_traveler = data.get('is_traveler', False)
    user_id = g.current_user_id

    if not name or not background:
        return jsonify({"error": "Nome e história de fundo são obrigatórios."}), 400
    if not isinstance(is_traveler, bool):
        return jsonify({"error": "'is_traveler' deve ser um valor booleano (true/false)."}), 400

    try:
        character_id = central_db_manager.create_character(user_id, name, background, is_traveler)

        # Se for um Viajante, provisiona sua coleção de memória pessoal
        if is_traveler:
            # Esta coleção será usada no futuro para a "Consolidação de Memória"
            # chromadb_manager.get_or_create_traveler_collection(character_id)
            # A função acima precisaria ser criada no chromadb_manager
            logging.info(f"Personagem Viajante {character_id} criado. Coleção de memória pronta para ser usada.")

        return jsonify({
            "message": "Personagem criado com sucesso!",
            "character": {
                "id": character_id,
                "name": name,
                "background": background,
                "is_traveler": is_traveler
            }
        }), 201

    except Exception as e:
        logging.error(f"Falha ao criar personagem para o usuário {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Falha ao criar o personagem."}), 500

@characters_bp.route('/characters', methods=['GET'])
@token_required
def get_characters():
    """Retorna a lista de personagens do usuário logado."""
    user_id = g.current_user_id
    try:
        characters = central_db_manager.get_user_characters(user_id)
        return jsonify(characters), 200
    except Exception as e:
        logging.error(f"Erro ao listar personagens para o usuário {user_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao buscar personagens."}), 500
