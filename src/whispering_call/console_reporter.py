"""Saída de texto simples para o usuário da CLI."""

from __future__ import annotations

from typing import TextIO

from whispering_call.pipeline import RunSummary

# Reimprimir a cada segmento poluiria terminais que não tratam "\r" (ex.: logs do CI).
_PROGRESS_STEP_PERCENT = 5


class ConsoleReporter:
    """Imprime mensagens e o progresso da transcrição numa única linha.

    Exemplo::

        reporter = ConsoleReporter(sys.stdout)
        reporter.progress("kickoff.mp4", 0.42)  # "  kickoff.mp4: 40%"
    """

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._last_percent: int | None = None

    def info(self, message: str) -> None:
        self._close_progress_line()
        print(message, file=self._stream, flush=True)

    def progress(self, recording_key: str, fraction: float) -> None:
        percent = int(fraction * 100) // _PROGRESS_STEP_PERCENT * _PROGRESS_STEP_PERCENT
        if percent == self._last_percent:
            return
        self._last_percent = percent
        print(f"\r  {recording_key}: {percent}%", end="", file=self._stream, flush=True)

    def _close_progress_line(self) -> None:
        if self._last_percent is not None:
            print(file=self._stream)
            self._last_percent = None


def format_run_summary(summary: RunSummary) -> str:
    """Resumo final da execução em texto simples.

    Exemplo::

        format_run_summary(RunSummary(transcribed=["a.mp4"]))
    """
    sections = (
        ("Transcritas", summary.transcribed),
        ("Claude aberto para", summary.launched),
        ("Já documentadas", summary.already_documented),
        ("Pendentes (ficaram para a próxima execução)", summary.deferred),
        ("Com falha (veja o log)", summary.failed),
    )
    lines = [f"{title}: {', '.join(keys)}" for title, keys in sections if keys]
    return "\n".join(lines) if lines else "Nenhuma gravação encontrada."
