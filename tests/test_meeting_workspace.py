from pathlib import Path

import pytest

from whispering_call.meeting_workspace import (
    MeetingWorkspace,
    folder_name_for,
    workspace_for,
)
from whispering_call.recordings import Recording


@pytest.mark.parametrize(
    ("recording_key", "expected"),
    [
        ("kickoff.mp4", "kickoff_mp4"),
        ("2026/kick off.mp4", "2026__kick off_mp4"),
        ('a:b|c?"d".webm', "a_b_c__d__webm"),
        ("sem-extensao", "sem-extensao"),
        ("...", "recording"),
    ],
)
def test_folder_name_is_valid_on_windows_and_linux(
    recording_key: str, expected: str
) -> None:
    assert folder_name_for(recording_key) == expected


def test_same_stem_different_extension_do_not_collide() -> None:
    assert folder_name_for("a.mp4") != folder_name_for("a.mkv")


def test_workspace_for_places_folder_under_output_root(tmp_path: Path) -> None:
    recording = Recording(media_file=tmp_path / "r" / "a.mp4", key="a.mp4")

    workspace = workspace_for(recording, tmp_path / "out")

    assert workspace.folder == tmp_path / "out" / "a_mp4"
    assert workspace.transcript_file.name == "transcript.md"
    assert workspace.doc_file.name == "doc.md"


def test_save_transcript_creates_folder_and_leaves_no_partial(tmp_path: Path) -> None:
    workspace = MeetingWorkspace(folder=tmp_path / "a_mp4")

    workspace.save_transcript("# Transcrição\n- [00:00:00] Olá, ação\n")

    assert workspace.has_transcript()
    assert workspace.transcript_file.read_text(encoding="utf-8").endswith("Olá, ação\n")
    assert [p.name for p in workspace.folder.iterdir()] == ["transcript.md"]


def test_save_prompt_copy_returns_path_inside_workspace(tmp_path: Path) -> None:
    workspace = MeetingWorkspace(folder=tmp_path / "a_mp4")

    prompt_copy = workspace.save_prompt_copy("Gere a ata")

    assert prompt_copy.parent == workspace.folder
    assert prompt_copy.read_text(encoding="utf-8") == "Gere a ata"


def test_has_doc_reflects_file_presence(tmp_path: Path) -> None:
    workspace = MeetingWorkspace(folder=tmp_path)
    assert not workspace.has_doc()

    workspace.doc_file.write_text("# Doc", encoding="utf-8")

    assert workspace.has_doc()
