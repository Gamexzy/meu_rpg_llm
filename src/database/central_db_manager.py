# src/database/central_db_manager.py
import logging
import sqlite3
from typing import Any, Dict, List, Optional
import bcrypt
from src import config

logger = logging.getLogger(__name__)

class CentralDbManager:
    """
    Gerencia o DB central (usuários, universos, personagens, aventuras).
    Versão: 2.1.0 - Adicionados métodos de gerenciamento de Personagens.
    """

    def __init__(self, db_path: str = config.DB_PATH_CENTRAL):
        self.db_path = db_path
        logger.info(f"Gestor de DB Central inicializado para: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna uma nova conexão com o banco de dados central."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # --- Métodos de Usuário ---
    def register_user(self, username: str, password: str) -> int:
        """Registra um novo usuário. Retorna o ID do novo usuário."""
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
                logger.info(f"Usuário '{username}' registrado com sucesso.")
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Tentativa de registrar usuário já existente: '{username}'")
            raise
        finally:
            conn.close()

    def authenticate_user(self, username: str, password: str) -> Optional[int]:
        """Verifica as credenciais. Retorna o ID do usuário se bem-sucedido."""
        conn = self._get_connection()
        try:
            user_row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
            if user_row and bcrypt.checkpw(password.encode("utf-8"), user_row["password_hash"].encode("utf-8")):
                logger.info(f"Usuário '{username}' autenticado com sucesso.")
                return user_row["id"]
            logger.warning(f"Tentativa de login falhou para o usuário '{username}'.")
            return None
        finally:
            conn.close()

    # --- Métodos de Universo ---
    def create_universe(self, user_id: int, name: str, description: str, db_path: str) -> int:
        """Cria um novo universo. Retorna o ID do novo universo."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO universes (user_id, name, description, db_path) VALUES (?, ?, ?, ?)",
                    (user_id, name, description, db_path)
                )
                logger.info(f"Universo '{name}' (ID: {cursor.lastrowid}) criado para o usuário {user_id}.")
                return cursor.lastrowid
        finally:
            conn.close()

    def get_user_universes(self, user_id: int) -> List[Dict[str, Any]]:
        """Retorna uma lista de todos os universos de um usuário."""
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT id, name, description FROM universes WHERE user_id = ?", (user_id,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def update_universe_db_path(self, universe_id: int, db_path: str):
        """Atualiza o caminho do banco de dados de um universo."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("UPDATE universes SET db_path = ? WHERE id = ?", (db_path, universe_id))
            logger.info(f"Caminho do DB para o universo {universe_id} atualizado.")
        finally:
            conn.close()

    # --- MÉTODOS DE PERSONAGEM ---
    def create_character(self, user_id: int, name: str, background: str, is_traveler: bool) -> int:
        """Cria um novo personagem. Retorna o ID do novo personagem."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO characters (user_id, name, background, is_traveler) VALUES (?, ?, ?, ?)",
                    (user_id, name, background, is_traveler)
                )
                char_id = cursor.lastrowid
                logger.info(f"Personagem '{name}' (ID: {char_id}) criado para o usuário {user_id}. Viajante: {is_traveler}")
                return char_id
        finally:
            conn.close()

    def get_user_characters(self, user_id: int) -> List[Dict[str, Any]]:
        """Retorna uma lista de todos os personagens de um usuário."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT id, name, background, is_traveler, current_adventure_id FROM characters WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
