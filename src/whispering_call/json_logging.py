"""Logs estruturados em JSON (um objeto por linha) para depuração.

Campos extras vão em ``extra={"fields": {...}}``:

    logger.info("transcription_done", extra={"fields": {"recording": key}})
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT_LOGGER_NAME = "whispering_call"


class JsonLogFormatter(logging.Formatter):
    """Exemplo de linha: ``{"timestamp": "...", "level": "INFO", "event": "x"}``."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(fields)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_json_logging(level: str, log_file: Path) -> logging.Handler:
    """Envia os logs do pacote para ``log_file`` em JSON; o terminal fica limpo.

    Exemplo::

        configure_json_logging("INFO", Path("output/whispering-call.log"))
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(JsonLogFormatter())
    package_logger = logging.getLogger(ROOT_LOGGER_NAME)
    package_logger.setLevel(level)
    package_logger.addHandler(handler)
    return handler
