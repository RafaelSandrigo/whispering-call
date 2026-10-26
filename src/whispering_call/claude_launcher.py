"""Abre o Claude Code no mesmo terminal ou numa nova janela (configurável).

Comando gerado: ``claude <prompt-inicial> <extra_args...>``. O prompt vem logo
após o executável porque opções variádicas do Claude (ex.: ``--add-dir``)
engoliriam um posicional colocado depois delas.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from whispering_call.config import (
    COMMAND_PLACEHOLDER,
    CWD_PLACEHOLDER,
    ClaudeSettings,
    LaunchMode,
)
from whispering_call.errors import ClaudeLaunchError
from whispering_call.process_runner import ProcessRunner

# Metacaracteres que o cmd.exe reinterpreta mesmo dentro de um `start`.
_CMD_METACHARACTERS = frozenset('&|<>^%"\r\n')


@dataclass(frozen=True)
class ClaudeSession:
    working_folder: Path
    initial_prompt: str


class ClaudeLauncher(Protocol):
    def launch(self, session: ClaudeSession) -> None: ...


def build_claude_command(
    executable: str, extra_args: Sequence[str], session: ClaudeSession
) -> list[str]:
    """Exemplo::

    build_claude_command("claude", ["--model", "opus"], session)
    # ["claude", "<prompt>", "--model", "opus"]
    """
    return [executable, session.initial_prompt, *extra_args]


class SameTerminalClaudeLauncher:
    """Roda o Claude interativo no terminal atual e espera ele terminar.

    Exemplo::

        SameTerminalClaudeLauncher("claude", (), SubprocessRunner()).launch(session)
    """

    def __init__(
        self, executable: str, extra_args: Sequence[str], runner: ProcessRunner
    ) -> None:
        self._executable = executable
        self._extra_args = tuple(extra_args)
        self._runner = runner

    def launch(self, session: ClaudeSession) -> None:
        command = build_claude_command(self._executable, self._extra_args, session)
        exit_code = self._runner.run_and_wait(command, session.working_folder)
        if exit_code != 0:
            raise ClaudeLaunchError(
                f"Claude Code terminou com código {exit_code} (esperado 0) em {session.working_folder}"
            )


class NewWindowClaudeLauncher:
    """Abre o Claude numa nova janela de terminal e retorna sem esperar.

    ``window_template`` vem de ``[claude].new_window_command``: o item
    ``{command}`` é substituído pelo comando do Claude e ``{cwd}`` pela pasta da
    reunião.

    Exemplo::

        launcher = NewWindowClaudeLauncher("claude", (), ("kitty", "{command}"), runner, "linux")
        launcher.launch(session)
    """

    def __init__(
        self,
        executable: str,
        extra_args: Sequence[str],
        window_template: Sequence[str],
        runner: ProcessRunner,
        platform: str,
    ) -> None:
        self._executable = executable
        self._extra_args = tuple(extra_args)
        self._window_template = tuple(window_template)
        self._runner = runner
        self._platform = platform

    def launch(self, session: ClaudeSession) -> None:
        claude_command = build_claude_command(
            self._executable, self._extra_args, session
        )
        window_command = expand_window_template(
            self._window_template, claude_command, session.working_folder
        )
        if self._platform == "win32":
            ensure_safe_for_cmd(window_command)
        self._runner.start_detached(window_command, session.working_folder)


def expand_window_template(
    template: Sequence[str], claude_command: Sequence[str], cwd: Path
) -> list[str]:
    """Exemplo::

    expand_window_template(["konsole", "--workdir", "{cwd}", "-e", "{command}"],
                           ["claude", "oi"], Path("/out/a"))
    # ["konsole", "--workdir", "/out/a", "-e", "claude", "oi"]
    """
    expanded: list[str] = []
    for token in template:
        if token == COMMAND_PLACEHOLDER:
            expanded.extend(claude_command)
            continue
        expanded.append(token.replace(CWD_PLACEHOLDER, str(cwd)))
    return expanded


def ensure_safe_for_cmd(command: Sequence[str]) -> None:
    """Recusa argumentos que o ``cmd.exe`` reinterpretaria (ex.: ``&`` num caminho).

    Exemplo::

        ensure_safe_for_cmd(["cmd", "/c", "start", "claude", "oi"])  # ok
    """
    unsafe = [argument for argument in command if _CMD_METACHARACTERS & set(argument)]
    if unsafe:
        raise ClaudeLaunchError(
            f"Argumentos com caracteres especiais do cmd.exe {sorted(_CMD_METACHARACTERS)!r} "
            f"não são suportados no modo new_window do Windows; recebido {unsafe!r}. "
            'Renomeie a pasta/gravação ou use launch_mode = "same_terminal".'
        )


def build_claude_launcher(
    settings: ClaudeSettings,
    runner: ProcessRunner,
    platform: str,
    find_executable: Callable[[str], str | None] = shutil.which,
) -> ClaudeLauncher:
    """Escolhe o launcher conforme ``[claude].launch_mode``.

    Exemplo::

        launcher = build_claude_launcher(config.claude, SubprocessRunner(), sys.platform)
    """
    executable = resolve_executable(settings.executable, find_executable)
    if settings.launch_mode is LaunchMode.NEW_WINDOW:
        return NewWindowClaudeLauncher(
            executable,
            settings.extra_args,
            settings.new_window_command,
            runner,
            platform,
        )
    return SameTerminalClaudeLauncher(executable, settings.extra_args, runner)


def resolve_executable(name: str, find_executable: Callable[[str], str | None]) -> str:
    """Caminho absoluto do executável; no Windows resolve ``claude`` → ``claude.exe``.

    Exemplo::

        resolve_executable("claude", shutil.which)  # "/home/user/.local/bin/claude"
    """
    resolved = find_executable(name)
    if resolved is None:
        raise ClaudeLaunchError(
            f"Executável do Claude Code não encontrado: {name!r} "
            "(esperado um comando no PATH ou caminho absoluto; ajuste [claude].executable)"
        )
    return resolved
