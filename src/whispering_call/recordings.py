"""Fontes de gravações de reunião.

Hoje só existe a pasta local (ex.: Drive sincronizado no disco). Uma fonte
Google Drive via API entra implementando ``RecordingSource`` — ver
docs/roadmap.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from whispering_call.errors import RecordingFolderError


@dataclass(frozen=True)
class Recording:
    """Uma gravação disponível para processamento.

    ``key`` é o caminho relativo à pasta de gravações em formato POSIX
    (``"2026/kickoff.mp4"``), estável entre Windows e Linux.
    """

    media_file: Path
    key: str


class RecordingSource(Protocol):
    def list_recordings(self) -> list[Recording]: ...


def _newest_first(media_file: Path) -> tuple[int, str]:
    # mtime_ns negado inverte a ordem sem inverter o desempate pelo caminho.
    return (-media_file.stat().st_mtime_ns, media_file.as_posix())


class LocalFolderRecordingSource:
    """Lista arquivos de áudio/vídeo de uma pasta local, do mais novo ao mais antigo.

    A ordem é a da data de modificação do arquivo (empate: ordem do caminho). Assim
    ``--limit N`` pega as gravações mais recentes.

    Exemplo::

        source = LocalFolderRecordingSource(Path("recordings"), (".mp4",), recursive=False)
        for recording in source.list_recordings():
            print(recording.key)
    """

    def __init__(
        self, folder: Path, extensions: tuple[str, ...], recursive: bool
    ) -> None:
        self._folder = folder
        self._extensions = frozenset(extension.lower() for extension in extensions)
        self._recursive = recursive

    def list_recordings(self) -> list[Recording]:
        if not self._folder.is_dir():
            raise RecordingFolderError(
                f"Pasta de gravações não encontrada: {self._folder} "
                "(esperado um diretório existente; ajuste [recordings].folder)"
            )
        candidates = (
            self._folder.rglob("*") if self._recursive else self._folder.glob("*")
        )
        media_files = sorted(
            (path for path in candidates if self._is_media_file(path)),
            key=_newest_first,
        )
        return [self._to_recording(media_file) for media_file in media_files]

    def _is_media_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in self._extensions

    def _to_recording(self, media_file: Path) -> Recording:
        return Recording(
            media_file=media_file, key=media_file.relative_to(self._folder).as_posix()
        )
