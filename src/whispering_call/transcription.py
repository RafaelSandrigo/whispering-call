"""Contrato de transcrição, independente do motor (faster-whisper, API, ...)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# Recebe a fração concluída, de 0.0 a 1.0.
ProgressCallback = Callable[[float], None]


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str


class Transcriber(Protocol):
    def transcribe(
        self, media_file: Path, on_progress: ProgressCallback
    ) -> list[TranscriptSegment]: ...
