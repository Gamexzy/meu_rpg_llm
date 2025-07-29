# servidor/utils/request_logger.py
import logging
import json
from flask import request

request_logger = logging.getLogger(__name__)

def log_request(response):
    """
    Cria um dicionário com os detalhes da requisição/resposta e o envia
    para o sistema de logging central.
    Versão: 3.0.0 - Passa um dicionário em vez de string JSON.
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

    # Este é o dicionário que será enviado para o logger
    log_entry = {
        "type": "HTTP_REQUEST",
        "remote_addr": request.remote_addr,
        "method": request.method,
        "endpoint": request.path,
        "request_body": request_data,
        "status_code": response.status_code,
        "response_body": response_data,
    }

    # Passamos o dicionário diretamente. O JsonFormatter saberá como lidar com ele.
    request_logger.info(log_entry)

    return response
