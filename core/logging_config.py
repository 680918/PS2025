import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import LOG_MAX_BYTES, LOG_BACKUP_COUNT


def configure_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
        force=True,
    )
