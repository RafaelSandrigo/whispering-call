from pathlib import Path

import pytest

from fakes import (
    FakeClaudeLauncher,
    FakeRecordingSource,
    FakeTranscriber,
    RecordingReporter,
)
from whispering_call.errors import PromptFileError
from whispering_call.meeting_workspace import MeetingWorkspace
from whispering_call.pipeline import MeetingDocPipeline, read_prompt_template
from whispering_call.recordings import Recording
from whispering_call.transcription import TranscriptSegment

SEGMENTS = [TranscriptSegment(0.0, 3.0, "Decidimos lançar sexta.")]


def make_recording(tmp_path: Path, key: str) -> Recording:
    return Recording(media_file=tmp_path / "recordings" / key, key=key)


def make_prompt(tmp_path: Path, text: str = "Gere uma ata.") -> Path:
    prompt_file = tmp_path / "doc_prompt.md"
    prompt_file.write_text(text, encoding="utf-8")
    return prompt_file


def make_pipeline(
    tmp_path: Path,
    recordings: list[Recording],
    transcriber: FakeTranscriber,
    launcher: FakeClaudeLauncher,
) -> MeetingDocPipeline:
    return MeetingDocPipeline(
        source=FakeRecordingSource(recordings),
        transcriber=transcriber,
        launcher=launcher,
        output_root=tmp_path / "output",
        prompt_file=make_prompt(tmp_path),
        reporter=RecordingReporter(),
    )


def test_new_recording_is_transcribed_and_claude_is_launched(tmp_path: Path) -> None:
    recording = make_recording(tmp_path, "kickoff.mp4")
    launcher = FakeClaudeLauncher()

    summary = make_pipeline(
        tmp_path, [recording], FakeTranscriber(SEGMENTS), launcher
    ).run()

    workspace = MeetingWorkspace(tmp_path / "output" / "kickoff_mp4")
    assert "Decidimos lançar sexta." in workspace.transcript_file.read_text(
        encoding="utf-8"
    )
    assert workspace.prompt_copy_file.read_text(encoding="utf-8") == "Gere uma ata."
    [session] = launcher.sessions
    assert session.working_folder == workspace.folder
    assert str(workspace.doc_file) in session.initial_prompt
    assert summary.transcribed == ["kickoff.mp4"]
    assert summary.launched == ["kickoff.mp4"]


def test_recording_with_doc_is_skipped(tmp_path: Path) -> None:
    recording = make_recording(tmp_path, "kickoff.mp4")
    workspace = MeetingWorkspace(tmp_path / "output" / "kickoff_mp4")
    workspace.folder.mkdir(parents=True)
    workspace.doc_file.write_text("# Doc", encoding="utf-8")
    transcriber, launcher = FakeTranscriber(SEGMENTS), FakeClaudeLauncher()

    summary = make_pipeline(tmp_path, [recording], transcriber, launcher).run()

    assert transcriber.transcribed_files == []
    assert launcher.sessions == []
    assert summary.already_documented == ["kickoff.mp4"]


def test_existing_transcript_is_reused_without_retranscribing(tmp_path: Path) -> None:
    recording = make_recording(tmp_path, "kickoff.mp4")
    MeetingWorkspace(tmp_path / "output" / "kickoff_mp4").save_transcript(
        "# já existe\n"
    )
    transcriber, launcher = FakeTranscriber(SEGMENTS), FakeClaudeLauncher()

    summary = make_pipeline(tmp_path, [recording], transcriber, launcher).run()

    assert transcriber.transcribed_files == []
    assert len(launcher.sessions) == 1
    assert summary.transcribed == []


def test_all_transcriptions_happen_before_any_claude_session(tmp_path: Path) -> None:
    recordings = [make_recording(tmp_path, "a.mp4"), make_recording(tmp_path, "b.mp4")]
    transcriber = FakeTranscriber(SEGMENTS)
    launcher = FakeClaudeLauncher(writes_doc=True)

    summary = make_pipeline(tmp_path, recordings, transcriber, launcher).run()

    assert len(transcriber.transcribed_files) == 2
    assert summary.launched == ["a.mp4", "b.mp4"]
    assert MeetingWorkspace(tmp_path / "output" / "a_mp4").has_doc()


def test_transcription_failure_does_not_stop_other_recordings(tmp_path: Path) -> None:
    broken, healthy = make_recording(tmp_path, "a.mp4"), make_recording(
        tmp_path, "b.mp4"
    )
    transcriber = FakeTranscriber(
        SEGMENTS, failing_files=frozenset({broken.media_file})
    )
    launcher = FakeClaudeLauncher()

    summary = make_pipeline(tmp_path, [broken, healthy], transcriber, launcher).run()

    assert summary.failed == ["a.mp4"]
    assert summary.launched == ["b.mp4"]
    assert not MeetingWorkspace(tmp_path / "output" / "a_mp4").has_transcript()


def test_claude_failure_is_recorded_and_transcript_kept(tmp_path: Path) -> None:
    recording = make_recording(tmp_path, "a.mp4")

    summary = make_pipeline(
        tmp_path, [recording], FakeTranscriber(SEGMENTS), FakeClaudeLauncher(fails=True)
    ).run()

    assert summary.failed == ["a.mp4"]
    assert MeetingWorkspace(tmp_path / "output" / "a_mp4").has_transcript()


def test_progress_is_forwarded_to_reporter(tmp_path: Path) -> None:
    reporter = RecordingReporter()
    pipeline = MeetingDocPipeline(
        FakeRecordingSource([make_recording(tmp_path, "a.mp4")]),
        FakeTranscriber(SEGMENTS),
        FakeClaudeLauncher(),
        tmp_path / "output",
        make_prompt(tmp_path),
        reporter,
    )

    pipeline.run()

    assert reporter.progress_updates == [("a.mp4", 1.0)]


def test_read_prompt_template_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PromptFileError, match="nao-existe.md"):
        read_prompt_template(tmp_path / "nao-existe.md")


def test_read_prompt_template_empty_file(tmp_path: Path) -> None:
    with pytest.raises(PromptFileError, match="vazio"):
        read_prompt_template(make_prompt(tmp_path, "   \n"))
