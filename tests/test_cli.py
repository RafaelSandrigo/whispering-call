from pathlib import Path

import pytest

from whispering_call.cli import build_argument_parser, main


def test_run_defaults_to_config_toml() -> None:
    arguments = build_argument_parser().parse_args(["run"])

    assert arguments.command == "run"
    assert arguments.config == "config.toml"


def test_command_is_required() -> None:
    with pytest.raises(SystemExit):
        build_argument_parser().parse_args([])


def test_expected_error_returns_1_and_prints_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["run", "--config", str(tmp_path / "ausente.toml")])

    assert exit_code == 1
    assert "ausente.toml" in capsys.readouterr().err
