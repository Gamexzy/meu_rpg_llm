# servidor/utils/logging_config.py
import logging
import os
import sys
import json
from datetime import datetime
from src import config
import colorlog
from colorlog.escape_codes import escape_codes # Importa os códigos de cor

class JsonFormatter(logging.Formatter):
    """
    Formata os registros de log como uma string JSON, ideal para análise por LLMs.
    """
    def format(self, record):
        log_object = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "line": record.lineno,
            "message": record.getMessage()
        }
        if isinstance(log_object['message'], dict):
            log_type = log_object['message'].pop('type', 'GENERIC')
            log_object['type'] = log_type
            log_object.update(log_object.pop('message'))
        return json.dumps(log_object, ensure_ascii=False)

class ConsoleFormatter(colorlog.ColoredFormatter):
    """
    Formata logs para o console. Se o log for uma requisição HTTP,
    usa um formato minimalista. Caso contrário, usa um formato padrão limpo.
    """
    def format(self, record):
        # Verifica se a mensagem é um dicionário e do tipo HTTP_REQUEST
        if isinstance(record.msg, dict) and record.msg.get("type") == "HTTP_REQUEST":
            log_data = record.msg
            status_code = log_data.get('status_code', '???')
            
            # Define a cor baseada no status code
            if 200 <= status_code < 300:
                color = 'green'
            elif 400 <= status_code < 500:
                color = 'yellow'
            elif status_code >= 500:
                color = 'red'
            else:
                color = 'white'
            
            # CORREÇÃO: Pega os códigos de cor diretamente do `escape_codes`
            color_code = escape_codes.get(color, '')
            reset_code = escape_codes.get('reset', '')
            
            status_str = f"{color_code}{status_code}{reset_code}"
            
            # Monta a string minimalista final
            return f"{log_data.get('remote_addr', '-')} - \"{log_data.get('method', '???')} {log_data.get('endpoint', '/???')}\" {status_str}"
        
        # Se não for uma requisição HTTP, usa o formatador padrão da biblioteca
        return super().format(record)

def setup_logging():
    """
    Configura um logger central com duas saídas:
    1. Console: Minimalista para requisições HTTP, limpo para o resto.
    2. Arquivo: Estruturado em JSON para análise detalhada por LLMs.
    Versão: 5.0.1 - Corrigido AttributeError no ConsoleFormatter.
    """
    LOGS_DIR = os.path.join(config.BASE_DIR, 'logs')
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file_path = os.path.join(LOGS_DIR, 'server_activity.log')

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- FORMATADORES ---
    console_formatter = ConsoleFormatter(
        '%(log_color)s%(levelname)-8s: %(message)s',
        log_colors={
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    )
    
    file_formatter = JsonFormatter()

    # --- HANDLERS ---
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # --- SILENCIAR BIBLIOTECAS ---
    libraries_to_silence = [
        "werkzeug", "urllib3", "neo4j", "chromadb", 
        "sentence_transformers", "httpx", "PIL"
    ]
    for lib_name in libraries_to_silence:
        logging.getLogger(lib_name).setLevel(logging.ERROR)

    logging.info("=" * 60)
    logging.info("Sistema de Logging (v5.0.1) Inicializado.")
    logging.info(f"Console: Minimalista. Arquivo: JSON.")
    logging.info("=" * 60)
