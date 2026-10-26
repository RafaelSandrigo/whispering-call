from pathlib import Path

import pytest

from fakes import FakeProcessRunner, ProcessCall
from whispering_call.claude_launcher import (
    ClaudeSession,
    NewWindowClaudeLauncher,
    SameTerminalClaudeLauncher,
    build_claude_command,
    build_claude_launcher,
    ensure_safe_for_cmd,
    expand_window_template,
    resolve_executable,
)
from whispering_call.config import ClaudeSettings, LaunchMode
from whispering_call.errors import ClaudeLaunchError

SESSION = ClaudeSession(
    working_folder=Path("/out/a_mp4"), initial_prompt="Leia o prompt"
)


def claude_settings(launch_mode: LaunchMode) -> ClaudeSettings:
    return ClaudeSettings(
        executable="claude",
        prompt_file=Path("prompts/doc_prompt.md"),
        launch_mode=launch_mode,
        extra_args=("--model", "opus"),
        new_window_command=("kitty", "{command}"),
    )


def test_command_puts_prompt_right_after_executable() -> None:
    # Regressão: opções variádicas como --add-dir engoliriam um prompt no fim.
    command = build_claude_command("claude", ["--add-dir", "/x"], SESSION)

    assert command == ["claude", "Leia o prompt", "--add-dir", "/x"]


def test_same_terminal_waits_in_meeting_folder() -> None:
    runner = FakeProcessRunner(exit_code=0)

    SameTerminalClaudeLauncher("claude", (), runner).launch(SESSION)

    assert runner.waited_calls == [
        ProcessCall(("claude", "Leia o prompt"), SESSION.working_folder)
    ]


def test_same_terminal_nonzero_exit_raises_with_code() -> None:
    launcher = SameTerminalClaudeLauncher("claude", (), FakeProcessRunner(exit_code=3))

    with pytest.raises(ClaudeLaunchError, match="código 3"):
        launcher.launch(SESSION)


def test_new_window_starts_detached_with_expanded_template() -> None:
    runner = FakeProcessRunner()
    template = ("konsole", "--workdir", "{cwd}", "-e", "{command}")

    NewWindowClaudeLauncher("claude", ("-c",), template, runner, "linux").launch(
        SESSION
    )

    expected = (
        "konsole",
        "--workdir",
        str(SESSION.working_folder),
        "-e",
        "claude",
        "Leia o prompt",
        "-c",
    )
    assert runner.detached_calls == [ProcessCall(expected, SESSION.working_folder)]
    assert runner.waited_calls == []


def test_new_window_on_windows_rejects_cmd_metacharacters() -> None:
    session = ClaudeSession(Path("C:/out/a&b"), "Leia o prompt")
    launcher = NewWindowClaudeLauncher(
        "claude",
        (),
        ("cmd", "/c", "start", "t t", "/D", "{cwd}", "{command}"),
        FakeProcessRunner(),
        "win32",
    )

    with pytest.raises(ClaudeLaunchError, match="a&b"):
        launcher.launch(session)


def test_expand_window_template_replaces_cwd_inside_tokens() -> None:
    expanded = expand_window_template(
        ["term", "--dir={cwd}", "{command}"], ["claude"], Path("/w")
    )

    assert expanded == ["term", f"--dir={Path('/w')}", "claude"]


def test_ensure_safe_for_cmd_accepts_plain_arguments() -> None:
    ensure_safe_for_cmd(["cmd", "/c", "start", "whispering call", "C:\\out\\a_mp4"])


def test_resolve_executable_returns_found_path() -> None:
    assert resolve_executable("claude", lambda _: "/bin/claude") == "/bin/claude"


def test_resolve_executable_missing_names_the_value() -> None:
    with pytest.raises(ClaudeLaunchError, match="'claude-x'"):
        resolve_executable("claude-x", lambda _: None)


@pytest.mark.parametrize(
    ("launch_mode", "expected_type"),
    [
        (LaunchMode.SAME_TERMINAL, SameTerminalClaudeLauncher),
        (LaunchMode.NEW_WINDOW, NewWindowClaudeLauncher),
    ],
)
def test_build_claude_launcher_follows_launch_mode(
    launch_mode: LaunchMode, expected_type: type
) -> None:
    launcher = build_claude_launcher(
        claude_settings(launch_mode),
        FakeProcessRunner(),
        "linux",
        lambda _: "/bin/claude",
    )

    assert isinstance(launcher, expected_type)
