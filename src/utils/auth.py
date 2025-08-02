# src/utils/auth.py
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g
from src import config

def generate_token(user_id: int) -> str:
    """
    Gera um token JWT para um ID de usuário específico.
    """
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),  # Token válido por 7 dias
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")
    return token

def set_user_id_from_token():
    """
    Middleware para ser chamado antes de cada requisição.
    Verifica o token no header e define g.current_user_id se o token for válido.
    """
    g.current_user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
            g.current_user_id = data.get("user_id")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            # Token é inválido ou expirou, g.current_user_id permanece None
            pass

def token_required(f):
    """
    Decorador para proteger rotas que exigem autenticação.
    Verifica se g.current_user_id foi definido pelo middleware.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.current_user_id is None:
            return jsonify({"error": "Token de autenticação ausente ou inválido."}), 401
        return f(*args, **kwargs)
    return decorated_function
