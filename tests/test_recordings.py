import os
import time
from pathlib import Path

import pytest

from whispering_call.errors import RecordingFolderError
from whispering_call.recordings import LocalFolderRecordingSource


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def set_age(path: Path, seconds_ago: int) -> None:
    moment = time.time_ns() - seconds_ago * 1_000_000_000
    os.utime(path, ns=(moment, moment))


def test_lists_newest_first_regardless_of_name(tmp_path: Path) -> None:
    set_age(touch(tmp_path / "a_antiga.mp4"), seconds_ago=300)
    set_age(touch(tmp_path / "z_nova.mp4"), seconds_ago=10)
    set_age(touch(tmp_path / "m_media.mp4"), seconds_ago=100)

    source = LocalFolderRecordingSource(tmp_path, (".mp4",), recursive=False)

    assert [r.key for r in source.list_recordings()] == [
        "z_nova.mp4",
        "m_media.mp4",
        "a_antiga.mp4",
    ]


def test_same_modification_time_falls_back_to_path_order(tmp_path: Path) -> None:
    for name in ("b.mp4", "a.mp4"):
        set_age(touch(tmp_path / name), seconds_ago=50)
    same_moment = (tmp_path / "a.mp4").stat().st_mtime_ns
    os.utime(tmp_path / "b.mp4", ns=(same_moment, same_moment))

    source = LocalFolderRecordingSource(tmp_path, (".mp4",), recursive=False)

    assert [r.key for r in source.list_recordings()] == ["a.mp4", "b.mp4"]


def test_lists_only_matching_extensions(tmp_path: Path) -> None:
    touch(tmp_path / "b.MP4")
    touch(tmp_path / "a.mkv")
    touch(tmp_path / "notes.txt")
    (tmp_path / "pasta.mp4").mkdir()

    source = LocalFolderRecordingSource(tmp_path, (".mp4", ".mkv"), recursive=False)

    assert sorted(r.key for r in source.list_recordings()) == ["a.mkv", "b.MP4"]


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
