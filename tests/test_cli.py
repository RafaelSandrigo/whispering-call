import io
from pathlib import Path

import pytest

from whispering_call.cli import build_argument_parser, choose_limit_policy, main
from whispering_call.console_reporter import ConsoleReporter
from whispering_call.run_limit import AllPending, AskUserLimit, FixedLimit


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


def test_limit_and_all_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        build_argument_parser().parse_args(["run", "--limit", "2", "--all"])


@pytest.mark.parametrize("value", ["0", "-3", "dois"])
def test_limit_must_be_a_positive_integer(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        build_argument_parser().parse_args(["run", "--limit", value])

    assert repr(value) in capsys.readouterr().err


def test_limit_short_flag() -> None:
    assert build_argument_parser().parse_args(["run", "-n", "3"]).limit == 3


@pytest.mark.parametrize(
    ("limit", "process_all", "interactive", "expected"),
    [
        (2, False, True, FixedLimit),
        (None, True, True, AllPending),
        (None, False, False, AllPending),
        (None, False, True, AskUserLimit),
    ],
)
def test_choose_limit_policy(
    limit: int | None,
    process_all: bool,
    interactive: bool,
    expected: type,
) -> None:
    reporter = ConsoleReporter(io.StringIO())

    policy = choose_limit_policy(limit, process_all, interactive, reporter)

    assert isinstance(policy, expected)
