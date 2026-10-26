import pytest

from whispering_call.transcript_markdown import (
    format_timestamp,
    render_transcript_markdown,
)
from whispering_call.transcription import TranscriptSegment


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "00:00:00"),
        (59.9, "00:00:59"),
        (3725.4, "01:02:05"),
        (36000.0, "10:00:00"),
    ],
)
def test_format_timestamp(seconds: float, expected: str) -> None:
    assert format_timestamp(seconds) == expected


def test_render_has_title_and_one_line_per_non_empty_segment() -> None:
    segments = [
        TranscriptSegment(0.0, 2.0, "Bom dia."),
        TranscriptSegment(2.0, 3.0, ""),
        TranscriptSegment(65.0, 70.0, "Vamos começar."),
    ]

    markdown = render_transcript_markdown("kickoff.mp4", segments)

    assert markdown == (
        "# Transcrição: kickoff.mp4\n\n- [00:00:00] Bom dia.\n- [00:01:05] Vamos começar.\n"
    )
