from pathlib import Path

import pytest

from whispering_call.errors import RecordingFolderError
from whispering_call.recordings import LocalFolderRecordingSource


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_lists_only_matching_extensions_sorted(tmp_path: Path) -> None:
    touch(tmp_path / "b.MP4")
    touch(tmp_path / "a.mkv")
    touch(tmp_path / "notes.txt")
    (tmp_path / "pasta.mp4").mkdir()

    source = LocalFolderRecordingSource(tmp_path, (".mp4", ".mkv"), recursive=False)

    assert [r.key for r in source.list_recordings()] == ["a.mkv", "b.MP4"]


def test_non_recursive_ignores_subfolders(tmp_path: Path) -> None:
    touch(tmp_path / "2026" / "kickoff.mp4")

    source = LocalFolderRecordingSource(tmp_path, (".mp4",), recursive=False)

    assert source.list_recordings() == []


def test_recursive_uses_posix_relative_key(tmp_path: Path) -> None:
    media_file = touch(tmp_path / "2026" / "kickoff.mp4")

    source = LocalFolderRecordingSource(tmp_path, (".mp4",), recursive=True)

    [recording] = source.list_recordings()
    assert recording.key == "2026/kickoff.mp4"
    assert recording.media_file == media_file


def test_missing_folder_raises_with_path(tmp_path: Path) -> None:
    missing = tmp_path / "nao-existe"

    with pytest.raises(RecordingFolderError, match="nao-existe"):
        LocalFolderRecordingSource(
            missing, (".mp4",), recursive=False
        ).list_recordings()
