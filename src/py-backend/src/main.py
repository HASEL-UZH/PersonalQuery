import os
import sys
import signal
import logging
import logging.config

import psutil
from uvicorn import Config, Server
from server_rest import app

IS_PACKAGED = hasattr(sys, "_MEIPASS")

log_path = None
if IS_PACKAGED:
    if sys.platform == "win32":
        appdata_dir = os.getenv("APPDATA", os.getcwd())
    elif sys.platform == "darwin":
        appdata_dir = os.path.join(
            os.path.expanduser("~"), "Library", "Application Support"
        )
    else:
        appdata_dir = os.getenv(
            "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
        )

log_handlers = ["default"]
if log_path:
    log_handlers.append("file")

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": log_path if log_path else "backend.log",
            "level": "DEBUG",
            "formatter": "default",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": log_handlers, "level": "INFO"},
        "uvicorn.error": {"handlers": log_handlers, "level": "INFO"},
        "uvicorn.access": {"handlers": log_handlers, "level": "INFO"},
    },
    "root": {
        "handlers": log_handlers,
        "level": "DEBUG"
    }
}

logging.config.dictConfig(logging_config)


def handle_exception(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


def kill_child_processes(parent_pid):
    try:
        for child in psutil.Process(parent_pid).children(recursive=True):
            logging.info(f"Killing child PID {child.pid}")
            child.kill()
    except Exception as e:
        logging.error(f"Error killing child processes: {e}")


def handle_exit(signum, frame):
    logging.info(f"Received exit signal ({signum})")
    kill_child_processes(os.getpid())
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

logging.info(f"main.py executing in PID: {os.getpid()}")

if __name__ == "__main__":
    logging.info("Uvicorn starting...")
    config = Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        loop="asyncio",
        lifespan="on",
        log_config=logging_config,
    )
    Server(config).run()
