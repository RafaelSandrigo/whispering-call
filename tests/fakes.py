"""Fakes nomeados para I/O externo (processos, Whisper, libs nativas, fonte de gravações)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from whispering_call.claude_launcher import ClaudeSession
from whispering_call.cuda_runtime import CudaStatus
from whispering_call.errors import ClaudeLaunchError
from whispering_call.recordings import Recording
from whispering_call.transcription import ProgressCallback, TranscriptSegment


@dataclass(frozen=True)
class ProcessCall:
    command: tuple[str, ...]
    cwd: Path


class FakeProcessRunner:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.waited_calls: list[ProcessCall] = []
        self.detached_calls: list[ProcessCall] = []

    def run_and_wait(self, command: Sequence[str], cwd: Path) -> int:
        self.waited_calls.append(ProcessCall(tuple(command), cwd))
        return self.exit_code

    def start_detached(self, command: Sequence[str], cwd: Path) -> None:
        self.detached_calls.append(ProcessCall(tuple(command), cwd))


class FakeRecordingSource:
    def __init__(self, recordings: Sequence[Recording]) -> None:
        self._recordings = list(recordings)

    def list_recordings(self) -> list[Recording]:
        return list(self._recordings)


class FakeTranscriber:
    """Devolve segmentos fixos; falha para os arquivos em ``failing_files``."""

    def __init__(
        self,
        segments: Sequence[TranscriptSegment],
        failing_files: frozenset[Path] = frozenset(),
    ) -> None:
        self._segments = list(segments)
        self._failing_files = failing_files
        self.transcribed_files: list[Path] = []

    def transcribe(
        self, media_file: Path, on_progress: ProgressCallback
    ) -> list[TranscriptSegment]:
        if media_file in self._failing_files:
            raise RuntimeError(f"arquivo corrompido: {media_file}")
        self.transcribed_files.append(media_file)
        on_progress(1.0)
        return list(self._segments)


class FakeClaudeLauncher:
    """Registra sessões; opcionalmente escreve ``doc.md`` como o Claude faria."""

    def __init__(self, writes_doc: bool = False, fails: bool = False) -> None:
        self._writes_doc = writes_doc
        self._fails = fails
        self.sessions: list[ClaudeSession] = []

    def launch(self, session: ClaudeSession) -> None:
        if self._fails:
            raise ClaudeLaunchError(f"falha simulada em {session.working_folder}")
        self.sessions.append(session)
        if self._writes_doc:
            (session.working_folder / "doc.md").write_text("# Doc\n", encoding="utf-8")


@dataclass
class RecordingReporter:
    messages: list[str] = field(default_factory=list)
    progress_updates: list[tuple[str, float]] = field(default_factory=list)

    def info(self, message: str) -> None:
        self.messages.append(message)

    def progress(self, recording_key: str, fraction: float) -> None:
        self.progress_updates.append((recording_key, fraction))


@dataclass(frozen=True)
class FakeWhisperSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class FakeWhisperInfo:
    duration: float


@dataclass(frozen=True)
class WhisperCall:
    audio: str
    language: str
    beam_size: int
    vad_filter: bool


class FakeWhisperModel:
    def __init__(self, segments: Sequence[FakeWhisperSegment], duration: float) -> None:
        self._segments = list(segments)
        self._duration = duration
        self.calls: list[WhisperCall] = []

    def transcribe(
        self, audio: str, *, language: str, beam_size: int, vad_filter: bool
    ) -> tuple[Iterable[FakeWhisperSegment], FakeWhisperInfo]:
        self.calls.append(WhisperCall(audio, language, beam_size, vad_filter))
        return iter(self._segments), FakeWhisperInfo(self._duration)


class FakeNativeLibraryLoader:
    """Simula libs nativas; ``requires`` mapeia nome → dependência que precisa vir antes."""

    def __init__(
        self,
        package_folders: dict[str, list[Path]],
        requires: dict[str, str] | None = None,
        broken: frozenset[str] = frozenset(),
    ) -> None:
        self._package_folders = package_folders
        self._requires = requires or {}
        self._broken = broken
        self.loaded: list[str] = []
        self.dll_folders: list[Path] = []

    def find_package_folders(self, package: str) -> list[Path]:
        return self._package_folders.get(package, [])

    def load_shared_object(self, library_file: Path) -> bool:
        dependency = self._requires.get(library_file.name)
        if library_file.name in self._broken or (
            dependency and dependency not in self.loaded
        ):
            return False
        self.loaded.append(library_file.name)
        return True

    def add_dll_folder(self, folder: Path) -> None:
        self.dll_folders.append(folder)


class FakeCudaProbe:
    """Simula a sondagem de GPU: NVIDIA presente ou ausente (Intel/AMD)."""

    def __init__(self, available: bool, reason: str = "RTX falsa") -> None:
        self._status = CudaStatus(available, reason)
        self.calls = 0

    def status(self) -> CudaStatus:
        self.calls += 1
        return self._status


class ScriptedAnswers:
    """Simula o teclado: devolve as respostas em ordem e registra as perguntas.

    Sem respostas sobrando, levanta ``EOFError`` como o ``input`` com stdin fechado.
    """

    def __init__(self, *answers: str) -> None:
        self._answers = list(answers)
        self.questions: list[str] = []

    def __call__(self, question: str) -> str:
        self.questions.append(question)
        if not self._answers:
            raise EOFError
        return self._answers.pop(0)
