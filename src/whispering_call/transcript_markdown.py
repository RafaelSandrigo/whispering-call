"""Renderiza segmentos de transcrição como Markdown com timestamps."""

from __future__ import annotations

from collections.abc import Sequence

from whispering_call.transcription import TranscriptSegment


def format_timestamp(seconds: float) -> str:
    """Formata segundos como ``HH:MM:SS`` (horas sempre presentes).

    Exemplo::

        format_timestamp(3725.4)  # "01:02:05"
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"


def render_transcript_markdown(
    recording_key: str, segments: Sequence[TranscriptSegment]
) -> str:
    """Uma linha por segmento, ``- [HH:MM:SS] texto``; segmentos vazios são omitidos.

    Os timestamps permitem que a doc gerada cite trechos da reunião.

    Exemplo::

        render_transcript_markdown("kickoff.mp4", [TranscriptSegment(0.0, 2.0, "Olá")])
    """
    lines = [f"# Transcrição: {recording_key}", ""]
    lines += [
        f"- [{format_timestamp(s.start_seconds)}] {s.text}" for s in segments if s.text
    ]
    return "\n".join(lines) + "\n"
