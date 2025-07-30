# src/utils/logging_config.py
import logging
import os
import sys
import json
from datetime import datetime
from src import config
import colorlog
from colorlog.escape_codes import escape_codes
from flask import g, has_request_context

# --- Cache para loggers de usuário ---
_user_loggers = {}
LOGS_DIR = os.path.join(config.BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

class JsonFormatter(logging.Formatter):
    """
    Formata os registros de log como uma string JSON.
    Se estiver em um contexto de requisição Flask, adiciona o user_id.
    """
    def format(self, record):
        log_object = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "line": record.lineno,
            "message": record.getMessage()
        }
        
        # Adiciona user_id se estiver disponível no contexto da requisição
        if has_request_context() and hasattr(g, 'user_id') and g.user_id:
            log_object['user_id'] = g.user_id

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
        if isinstance(record.msg, dict) and record.msg.get("type") == "HTTP_REQUEST":
            req = record.msg
            status_code = req.get('status_code', '-')
            
            if status_code and isinstance(status_code, int):
                if 200 <= status_code < 300:
                    status_color = 'green'
                elif 300 <= status_code < 400:
                    status_color = 'yellow'
                elif 400 <= status_code < 600:
                    status_color = 'red'
                else:
                    status_color = 'white'
                
                color_code = self.log_colors.get(status_color.upper(), '')
                if not color_code: # Fallback para códigos de escape se não estiver em log_colors
                    color_code = escape_codes.get(status_color, '')

                reset_code = self.reset
                status_colored = f"{color_code}{status_code}{reset_code}"
            else:
                status_colored = str(status_code)

            log_message = (
                f"{req.get('method', '-'):<7} "
                f"{req.get('endpoint', '-'):<30} "
                f"Status: {status_colored}"
            )
            record.log_color = self.log_colors.get('WHITE', '')
        else:
            log_message = super().format(record)

        return log_message

def get_user_logger(user_id):
    """
    Obtém (ou cria) um logger para um usuário específico.
    Este logger escreve para um arquivo de log dedicado.
    """
    # Garante que o user_id seja seguro para usar como nome de diretório
    safe_user_id = str(user_id).replace('/', '_').replace('\\', '_').replace('..', '')
    
    if safe_user_id in _user_loggers:
        return _user_loggers[safe_user_id]

    # Cria um novo logger para este usuário
    logger = logging.getLogger(f"user.{safe_user_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Impede que os logs cheguem ao logger raiz

    # Cria o diretório de log do usuário, se não existir
    user_log_dir = os.path.join(LOGS_DIR, safe_user_id)
    os.makedirs(user_log_dir, exist_ok=True)
    log_file_path = os.path.join(user_log_dir, 'activity.log')

    # Cria o handler e o formatador
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_formatter = JsonFormatter()
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)
    
    # Adiciona o novo logger ao cache
    _user_loggers[safe_user_id] = logger
    
    return logger

def setup_logging():
    """
    Configura o logging raiz para o sistema (console e arquivo system.log).
    Loggers de usuário são criados dinamicamente via get_user_logger.
    Versão: 2.0.0 - Adiciona loggers dinâmicos por usuário.
    """
    log_file_path = os.path.join(LOGS_DIR, 'system.log')

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
            'WHITE':    'white'
        }
    )
    
    file_formatter = JsonFormatter()

    # --- HANDLERS ---
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    system_file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    system_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(system_file_handler)

    # --- SILENCIAR BIBLIOTECAS ---
    libraries_to_silence = [
        "werkzeug", "urllib3", "h11", "httpcore", "httpx", "openai",
        "chromadb.telemetry.posthog", "neo4j"
    ]
    for lib_name in libraries_to_silence:
        logging.getLogger(lib_name).setLevel(logging.WARNING)
