"""Adaptador do faster-whisper para o contrato ``Transcriber``.

O faster-whisper decodifica o arquivo via PyAV (FFmpeg embutido no wheel), então
aceita o vídeo diretamente: não há etapa separada de extração de áudio nem
dependência de um ``ffmpeg`` instalado no sistema.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from whispering_call.config import TranscriptionSettings
from whispering_call.cuda_runtime import (
    SystemNativeLibraryLoader,
    register_nvidia_libraries,
)
from whispering_call.transcription import ProgressCallback, TranscriptSegment


class WhisperSegmentLike(Protocol):
    @property
    def start(self) -> float: ...

    @property
    def end(self) -> float: ...

    @property
    def text(self) -> str: ...


class WhisperInfoLike(Protocol):
    @property
    def duration(self) -> float: ...


class WhisperModelLike(Protocol):
    def transcribe(
        self, audio: str, *, language: str, beam_size: int, vad_filter: bool
    ) -> tuple[Iterable[WhisperSegmentLike], WhisperInfoLike]: ...


WhisperModelFactory = Callable[[TranscriptionSettings], WhisperModelLike]


def load_faster_whisper_model(settings: TranscriptionSettings) -> WhisperModelLike:
    """Cria o ``WhisperModel`` real (baixa o modelo no primeiro uso, ~3 GB p/ large-v3).

    A importação é tardia: ela carrega CTranslate2/CUDA e custaria segundos
    mesmo em execuções sem gravações novas.

    Exemplo::

        model = load_faster_whisper_model(config.transcription)
    """
    if settings.device != "cpu":
        register_nvidia_libraries(SystemNativeLibraryLoader(), sys.platform)
    from faster_whisper import WhisperModel

    model: WhisperModelLike = WhisperModel(
        settings.model, device=settings.device, compute_type=settings.compute_type
    )
    return model


class FasterWhisperTranscriber:
    """Transcreve áudio/vídeo com faster-whisper; o modelo é carregado uma vez só.

    Exemplo::

        transcriber = FasterWhisperTranscriber(config.transcription)
        segments = transcriber.transcribe(Path("reuniao.mp4"), on_progress=print)
    """

    def __init__(
        self,
        settings: TranscriptionSettings,
        model_factory: WhisperModelFactory = load_faster_whisper_model,
    ) -> None:
        self._settings = settings
        self._model_factory = model_factory
        self._model: WhisperModelLike | None = None

    def transcribe(
        self, media_file: Path, on_progress: ProgressCallback
    ) -> list[TranscriptSegment]:
        segments, info = self._loaded_model().transcribe(
            str(media_file),
            language=self._settings.language,
            beam_size=self._settings.beam_size,
            vad_filter=self._settings.vad_filter,
        )
        collected: list[TranscriptSegment] = []
        # `segments` é um gerador: a transcrição de fato acontece nesta iteração.
        for segment in segments:
            collected.append(
                TranscriptSegment(segment.start, segment.end, segment.text.strip())
            )
            on_progress(completed_fraction(segment.end, info.duration))
        return collected

    def _loaded_model(self) -> WhisperModelLike:
        if self._model is None:
            self._model = self._model_factory(self._settings)
        return self._model


def completed_fraction(done_seconds: float, total_seconds: float) -> float:
    """Fração concluída limitada a [0, 1]; duração desconhecida conta como 1.

    Exemplo::

        completed_fraction(30.0, 120.0)  # 0.25
    """
    if total_seconds <= 0:
        return 1.0
    return min(max(done_seconds / total_seconds, 0.0), 1.0)
