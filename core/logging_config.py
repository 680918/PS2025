import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import LOG_MAX_BYTES, LOG_BACKUP_COUNT
from core.logging_context import RunIdFilter

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s run_id=%(run_id)s %(message)s"


def configure_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    run_id_filter = RunIdFilter()

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.addFilter(run_id_filter)

    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(run_id_filter)

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            file_handler,
            stream_handler,
        ],
        force=True,
    )
