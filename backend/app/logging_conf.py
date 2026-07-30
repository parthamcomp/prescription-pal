"""JSON structured logging so logs can be aggregated by tools like
Datadog, CloudWatch, or Loki instead of grepped as plain text.
"""
import json
import logging
import sys
import time


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            log.update(extra_fields)
        return json.dumps(log)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("prescription_assistant")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger


logger = setup_logging()
