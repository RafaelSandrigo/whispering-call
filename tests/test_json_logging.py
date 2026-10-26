import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from whispering_call.json_logging import (
    ROOT_LOGGER_NAME,
    JsonLogFormatter,
    configure_json_logging,
)


@pytest.fixture
def isolated_package_logger() -> Iterator[logging.Logger]:
    package_logger = logging.getLogger(ROOT_LOGGER_NAME)
    original_handlers = list(package_logger.handlers)
    yield package_logger
    for handler in package_logger.handlers[len(original_handlers) :]:
        handler.close()
    package_logger.handlers = original_handlers


def make_record(
    message: str, fields: dict[str, object] | None = None
) -> logging.LogRecord:
    record = logging.LogRecord(
        "whispering_call.x", logging.INFO, __file__, 1, message, None, None
    )
    if fields is not None:
        record.fields = fields
    return record


def test_formatter_emits_json_with_extra_fields() -> None:
    line = JsonLogFormatter().format(
        make_record("transcription_done", {"recording": "a.mp4"})
    )

    entry = json.loads(line)
    assert entry["event"] == "transcription_done"
    assert entry["level"] == "INFO"
    assert entry["recording"] == "a.mp4"


def test_formatter_includes_exception_text() -> None:
    record = make_record("falhou")
    try:
        raise ValueError("valor ruim")
    except ValueError:
        record.exc_info = sys.exc_info()

    assert "valor ruim" in json.loads(JsonLogFormatter().format(record))["exception"]


def test_configure_writes_json_lines_to_file(
    tmp_path: Path, isolated_package_logger: logging.Logger
) -> None:
    log_file = tmp_path / "logs" / "app.log"

    handler = configure_json_logging("INFO", log_file)
    logging.getLogger(f"{ROOT_LOGGER_NAME}.pipeline").info(
        "ação", extra={"fields": {"n": 1}}
    )
    handler.flush()

    entry = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert entry == entry | {"event": "ação", "n": 1}
