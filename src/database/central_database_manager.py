# src/database/central_database_manager.py
import logging
import sqlite3
from typing import Any, Dict, List, Optional
import bcrypt
from src import config



logger = logging.getLogger(__name__)


class CentralDatabaseManager:
    """
    Gerencia todas as interações com a base de dados central (usuarios, sagas).
    Versão: 1.0.0 - Criação inicial do gestor de DB central.
    """

    def __init__(self, db_path: str = config.DB_PATH_CENTRAL):
        self.db_path = db_path
        logger.info(f"Gestor de DB Central inicializado para o caminho: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna uma nova conexão com a base de dados central."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def register_user(self, username: str, password: str) -> None:
        """
        Registra um novo usuário na base de dados.
        Lança uma exceção sqlite3.IntegrityError se o usuário já existir.
        """
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
            logger.info(f"Usuário '{username}' registrado com sucesso.")
        except sqlite3.IntegrityError:
            logger.warning(f"Tentativa de registrar usuário já existente: '{username}'")
            raise
        finally:
            conn.close()

    def authenticate_user(self, username: str, password: str) -> Optional[int]:
        """
        Verifica as credenciais do usuário.
        Retorna o ID do usuário se a autenticação for bem-sucedida, caso contrário, None.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password_hash FROM usuarios WHERE username = ?", (username,)
            )
            user_row = cursor.fetchone()

            if not user_row:
                return None

            stored_hash_bytes = user_row["password_hash"].encode("utf-8")
            password_bytes = password.encode("utf-8")

            if bcrypt.checkpw(password_bytes, stored_hash_bytes):
                logger.info(f"Usuário '{username}' autenticado com sucesso.")
                return user_row["id"]
            else:
                logger.warning(
                    f"Tentativa de login falhou para o usuário '{username}'."
                )
                return None
        finally:
            conn.close()

    def get_user_sagas(self, user_id: int) -> List[Dict[str, Any]]:
        """Retorna uma lista de todas as sagas pertencentes a um usuário."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_name, player_name, world_concept, summary FROM sagas WHERE usuario_id = ?",
                (user_id,),
            )
            sagas = [dict(row) for row in cursor.fetchall()]
            return sagas
        finally:
            conn.close()

    def create_saga(
        self, user_id: int, session_name: str, player_name: str, world_concept: str
    ) -> None:
        """Cria um novo registro de saga para um usuário."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO sagas (usuario_id, session_name, player_name, world_concept) VALUES (?, ?, ?, ?)",
                    (user_id, session_name, player_name, world_concept),
                )
            logger.info(f"Saga '{session_name}' criada para o usuário ID {user_id}.")
        finally:
            conn.close()

    def delete_saga(self, user_id: int, session_name: str) -> int:
        """
        Apaga uma saga pertencente a um usuário.
        Retorna o número de linhas apagadas.
        """
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM sagas WHERE session_name = ? AND usuario_id = ?",
                    (session_name, user_id),
                )
                return cursor.rowcount
        finally:
            conn.close()

    def check_saga_ownership(self, user_id: int, session_name: str) -> bool:
        """Verifica se um usuário é o dono de uma saga específica."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM sagas WHERE session_name = ? AND usuario_id = ?",
                (session_name, user_id),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_world_concept(self, user_id: int, session_name: str) -> Optional[str]:
        """Obtém o world_concept de uma saga específica."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT world_concept FROM sagas WHERE session_name = ? AND usuario_id = ?",
                (session_name, user_id),
            )
            row = cursor.fetchone()
            return row["world_concept"] if row else None
        finally:
            conn.close()
