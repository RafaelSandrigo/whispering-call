from pathlib import Path

import pytest

from fakes import FakeWhisperModel, FakeWhisperSegment, WhisperCall
from whispering_call.config import TranscriptionSettings
from whispering_call.faster_whisper_transcriber import (
    FasterWhisperTranscriber,
    WhisperModelLike,
    completed_fraction,
)
from whispering_call.transcription import TranscriptSegment

SETTINGS = TranscriptionSettings(
    model="large-v3",
    language="pt",
    device="cuda",
    compute_type="int8_float16",
    beam_size=5,
    vad_filter=True,
)


class CountingModelFactory:
    def __init__(self, model: FakeWhisperModel) -> None:
        self._model = model
        self.created_with: list[TranscriptionSettings] = []

    def __call__(self, settings: TranscriptionSettings) -> WhisperModelLike:
        self.created_with.append(settings)
        return self._model


def test_transcribe_passes_settings_and_strips_text() -> None:
    model = FakeWhisperModel(
        [FakeWhisperSegment(0.0, 4.0, "  Olá a todos ")], duration=8.0
    )
    transcriber = FasterWhisperTranscriber(SETTINGS, CountingModelFactory(model))

    segments = transcriber.transcribe(Path("reuniao.mp4"), on_progress=lambda _: None)

    assert segments == [TranscriptSegment(0.0, 4.0, "Olá a todos")]
    assert model.calls == [WhisperCall(str(Path("reuniao.mp4")), "pt", 5, True)]


def test_transcribe_reports_progress_per_segment() -> None:
    model = FakeWhisperModel(
        [FakeWhisperSegment(0.0, 5.0, "a"), FakeWhisperSegment(5.0, 10.0, "b")],
        duration=10.0,
    )
    progress: list[float] = []

    FasterWhisperTranscriber(SETTINGS, CountingModelFactory(model)).transcribe(
        Path("x.mp4"), on_progress=progress.append
    )

    assert progress == [0.5, 1.0]


def test_model_is_created_once_across_transcriptions() -> None:
    factory = CountingModelFactory(FakeWhisperModel([], duration=1.0))
    transcriber = FasterWhisperTranscriber(SETTINGS, factory)

    transcriber.transcribe(Path("a.mp4"), on_progress=lambda _: None)
    transcriber.transcribe(Path("b.mp4"), on_progress=lambda _: None)

    assert factory.created_with == [SETTINGS]


@pytest.mark.parametrize(
    ("done", "total", "expected"),
    [(30.0, 120.0, 0.25), (130.0, 120.0, 1.0), (-1.0, 10.0, 0.0), (5.0, 0.0, 1.0)],
)
def test_completed_fraction_is_clamped(
    done: float, total: float, expected: float
) -> None:
    assert completed_fraction(done, total) == expected
