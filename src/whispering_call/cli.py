"""Ponto de entrada da CLI e composição das dependências reais."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from whispering_call.claude_launcher import build_claude_launcher
from whispering_call.config import AppConfig, load_config
from whispering_call.console_reporter import ConsoleReporter, format_run_summary
from whispering_call.errors import WhisperingCallError
from whispering_call.faster_whisper_transcriber import FasterWhisperTranscriber
from whispering_call.json_logging import configure_json_logging
from whispering_call.pipeline import MeetingDocPipeline, RunReporter
from whispering_call.process_runner import SubprocessRunner
from whispering_call.recordings import LocalFolderRecordingSource

LOG_FILE_NAME = "whispering-call.log"


def main(argv: Sequence[str] | None = None) -> int:
    """Executa a CLI e devolve o código de saída.

    Exemplo::

        main(["run", "--config", "config.toml"])
    """
    arguments = build_argument_parser().parse_args(argv)
    reporter = ConsoleReporter(sys.stdout)
    try:
        return run_command(Path(arguments.config), reporter)
    except WhisperingCallError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whispering-call",
        description="Transcreve gravações de reunião e abre o Claude Code para gerar a doc.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser(
        "run", help="processa as gravações que ainda não têm doc"
    )
    run_parser.add_argument(
        "--config", default="config.toml", help="padrão: ./config.toml"
    )
    return parser


def run_command(config_file: Path, reporter: ConsoleReporter) -> int:
    config = load_config(config_file, sys.platform)
    configure_json_logging(config.logging.level, config.output.folder / LOG_FILE_NAME)
    summary = build_pipeline(config, reporter).run()
    reporter.info(format_run_summary(summary))
    return 1 if summary.failed else 0


def build_pipeline(config: AppConfig, reporter: RunReporter) -> MeetingDocPipeline:
    """Raiz de composição: único lugar que instancia as implementações reais.

    Exemplo::

        build_pipeline(load_config(Path("config.toml"), sys.platform), reporter).run()
    """
    recordings = config.recordings
    return MeetingDocPipeline(
        source=LocalFolderRecordingSource(
            recordings.folder, recordings.extensions, recordings.recursive
        ),
        transcriber=FasterWhisperTranscriber(config.transcription),
        launcher=build_claude_launcher(config.claude, SubprocessRunner(), sys.platform),
        output_root=config.output.folder,
        prompt_file=config.claude.prompt_file,
        reporter=reporter,
    )
