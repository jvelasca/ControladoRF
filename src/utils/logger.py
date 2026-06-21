import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

_LOGGER: Optional[logging.Logger] = None

def init_logging(log_file: str = 'logs/app.log', level: int = logging.INFO) -> None:
    global _LOGGER
    if _LOGGER is not None:
        return
    logger = logging.getLogger()
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    file_handler = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _LOGGER = logger

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def log_info(msg: str) -> None:
    logging.getLogger().info(msg)

def log_error(msg: str, exc: Exception = None) -> None:
    if exc:
        logging.getLogger().error(f"{msg}: {exc}")
    else:
        logging.getLogger().error(msg)

def log_debug(msg: str) -> None:
    logging.getLogger().debug(msg)
