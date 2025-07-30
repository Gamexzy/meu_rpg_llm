# src/utils/request_logger.py
import logging
from flask import request, g
from src.utils.logging_config import get_user_logger

# O logger raiz será usado se não houver um user_id
system_logger = logging.getLogger('api_requests')

def log_request(response):
    """
    Cria um dicionário com os detalhes da requisição/resposta e o envia
    para o logger apropriado (do usuário ou do sistema).
    Versão: 4.0.0 - Direciona logs para arquivos de usuário.
    """
    try:
        response_data = response.get_json(silent=True)
        if response_data is None:
            response_data = response.get_data(as_text=True)
    except Exception:
        response_data = "Corpo da resposta não-JSON ou erro na leitura."

    try:
        request_data = request.get_json(silent=True)
    except Exception:
        request_data = "Corpo da requisição não-JSON ou erro na leitura."

    log_entry = {
        "type": "HTTP_REQUEST",
        "remote_addr": request.remote_addr,
        "method": request.method,
        "endpoint": request.path,
        "request_body": request_data,
        "status_code": response.status_code,
        "response_body": response_data,
    }

    # Verifica se o user_id foi definido no contexto da requisição (g)
    user_id = getattr(g, 'user_id', None)

    if user_id:
        # Usa o logger específico do usuário
        user_logger = get_user_logger(user_id)
        user_logger.info(log_entry)
    else:
        # Se não houver user_id, usa o logger do sistema
        # A mensagem irá para system.log e para o console
        system_logger.info(log_entry)
    
    return response
