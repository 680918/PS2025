import logging

from core.logging_context import get_trace_logger


def test_get_trace_logger_includes_run_id():
    logger = logging.getLogger("test")

    trace_logger = get_trace_logger(
        logger,
        run_id="run-123",
    )

    assert isinstance(trace_logger, logging.LoggerAdapter)
    assert trace_logger.extra["run_id"] == "run-123"


def test_trace_logger_outputs_run_id():
    import io

    logger = logging.getLogger("test_trace_output")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    stream = io.StringIO()

    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter("%(levelname)s run_id=%(run_id)s %(message)s")
    )

    logger.addHandler(handler)

    trace_logger = get_trace_logger(
        logger,
        run_id="run-123",
    )

    trace_logger.info("hello")

    output = stream.getvalue()

    assert "run_id=run-123" in output
    assert "hello" in output


def test_logging_format_includes_run_id():
    import core.logging_config as logging_config_module

    assert "run_id" in logging_config_module.LOG_FORMAT


def test_plain_logger_has_default_run_id():
    import logging

    from core.logging_context import ensure_run_id

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    ensure_run_id(record)

    assert record.run_id == "-"


def test_run_id_filter_adds_default_run_id():
    import logging

    from core.logging_context import RunIdFilter

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    run_id_filter = RunIdFilter()

    result = run_id_filter.filter(record)

    assert result is True
    assert record.run_id == "-"


def test_configured_logging_outputs_default_and_trace_run_id(tmp_path, monkeypatch):
    import logging

    import core.logging_config as logging_config_module

    log_dir = tmp_path / "logs"

    monkeypatch.chdir(tmp_path)

    logging_config_module.configure_logging()

    plain_logger = logging.getLogger("plain_test")
    trace_logger = get_trace_logger(
        logging.getLogger("trace_test"),
        run_id="run-123",
    )

    plain_logger.info("plain message")
    trace_logger.info("trace message")

    for handler in logging.getLogger().handlers:
        handler.flush()

    log_file = log_dir / "app.log"
    output = log_file.read_text(encoding="utf-8")

    assert "run_id=-" in output
    assert "plain message" in output

    assert "run_id=run-123" in output
    assert "trace message" in output
