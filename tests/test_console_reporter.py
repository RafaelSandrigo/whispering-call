import io

from whispering_call.console_reporter import ConsoleReporter, format_run_summary
from whispering_call.pipeline import RunSummary


def test_progress_prints_only_on_step_change_and_info_closes_line() -> None:
    stream = io.StringIO()
    reporter = ConsoleReporter(stream)

    reporter.progress("a.mp4", 0.41)
    reporter.progress("a.mp4", 0.43)
    reporter.progress("a.mp4", 0.46)
    reporter.info("pronto")

    assert stream.getvalue() == "\r  a.mp4: 40%\r  a.mp4: 45%\npronto\n"


def test_info_without_progress_prints_single_line() -> None:
    stream = io.StringIO()

    ConsoleReporter(stream).info("olá")

    assert stream.getvalue() == "olá\n"


def test_summary_lists_only_non_empty_groups() -> None:
    summary = RunSummary(transcribed=["a.mp4"], failed=["b.mp4", "c.mp4"])

    assert format_run_summary(summary) == (
        "Transcritas: a.mp4\nCom falha (veja o log): b.mp4, c.mp4"
    )


def test_summary_without_recordings() -> None:
    assert format_run_summary(RunSummary()) == "Nenhuma gravação encontrada."
