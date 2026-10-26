"""Execução de processos externos atrás de uma interface própria (testável)."""

from __future__ import annotations

import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import Protocol

from whispering_call.errors import ClaudeLaunchError


class ProcessRunner(Protocol):
    def run_and_wait(self, command: Sequence[str], cwd: Path) -> int: ...

    def start_detached(self, command: Sequence[str], cwd: Path) -> None: ...


class SubprocessRunner:
    """``ProcessRunner`` real sobre ``subprocess``; funciona em Windows e Linux.

    Exemplo::

        exit_code = SubprocessRunner().run_and_wait(["claude", "oi"], Path("."))
    """

    def run_and_wait(self, command: Sequence[str], cwd: Path) -> int:
        # Ctrl+C no terminal chega a todo o grupo de processos. O Claude usa
        # Ctrl+C para cancelar uma resposta; sem isto o Python morreria com
        # KeyboardInterrupt e derrubaria a sessão junto. Usa um handler no-op
        # (e não SIG_IGN) porque SIG_IGN seria herdado pelo filho no exec.
        previous_handler = signal.signal(signal.SIGINT, _ignore_interrupt)
        try:
            return self._run(command, cwd)
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    def start_detached(self, command: Sequence[str], cwd: Path) -> None:
        try:
            # start_new_session: a janela sobrevive se o terminal do whispering-call fechar.
            subprocess.Popen(list(command), cwd=cwd, start_new_session=True)
        except OSError as error:
            raise _launch_error(command, error) from error

    def _run(self, command: Sequence[str], cwd: Path) -> int:
        try:
            return subprocess.run(list(command), cwd=cwd, check=False).returncode
        except OSError as error:
            raise _launch_error(command, error) from error


def _ignore_interrupt(_signal_number: int, _frame: FrameType | None) -> None:
    return None


def _launch_error(command: Sequence[str], error: OSError) -> ClaudeLaunchError:
    return ClaudeLaunchError(
        f"Não foi possível executar {list(command)!r}: {error} "
        "(esperado um programa instalado e no PATH)"
    )
