import logging


def get_trace_logger(logger, run_id=None):
    return logging.LoggerAdapter(
        logger,
        {
            "run_id": run_id,
        },
    )


def ensure_run_id(record):
    if not hasattr(record, "run_id"):
        record.run_id = "-"

    return True


class RunIdFilter(logging.Filter):
    def filter(self, record):
        return ensure_run_id(record)
