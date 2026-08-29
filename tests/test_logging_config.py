import logging
from core.logging_config import configure_logging
from logging.handlers import RotatingFileHandler


def test_configure_logging_creates_log_file(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    configure_logging()

    logger = logging.getLogger("test_logger")
    logger.warning("test log message")

    for handler in logging.getLogger().handlers:
        handler.flush()

    log_file = tmp_path / "logs" / "app.log"

    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8")

    assert "test log message" in content


def test_configure_logging_uses_expected_format(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    configure_logging()

    logger = logging.getLogger("test.module")
    logger.warning("format check")

    for handler in logging.getLogger().handlers:
        handler.flush()

    log_file = tmp_path / "logs" / "app.log"

    content = log_file.read_text(encoding="utf-8")

    assert "WARNING" in content
    assert "test.module" in content
    assert "format check" in content


def test_configure_logging_uses_rotating_file_handler(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    configure_logging()

    handlers = logging.getLogger().handlers

    rotating_handlers = [
        handler for handler in handlers if isinstance(handler, RotatingFileHandler)
    ]

    assert len(rotating_handlers) == 1

    handler = rotating_handlers[0]

    assert handler.maxBytes == 1_000_000
    assert handler.backupCount == 3


def test_configure_logging_uses_configured_rotation_values(
    tmp_path,
    monkeypatch,
):

    import core.logging_config as logging_config

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        logging_config,
        "LOG_MAX_BYTES",
        12345,
    )
    monkeypatch.setattr(
        logging_config,
        "LOG_BACKUP_COUNT",
        7,
    )

    logging_config.configure_logging()

    handlers = logging.getLogger().handlers

    rotating_handlers = [
        handler for handler in handlers if isinstance(handler, RotatingFileHandler)
    ]

    assert len(rotating_handlers) == 1

    handler = rotating_handlers[0]

    assert handler.maxBytes == 12345
    assert handler.backupCount == 7
