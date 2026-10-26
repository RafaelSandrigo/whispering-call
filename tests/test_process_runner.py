import sys
from pathlib import Path

import pytest

from whispering_call.errors import ClaudeLaunchError
from whispering_call.process_runner import SubprocessRunner


def test_run_and_wait_returns_exit_code_and_uses_cwd(tmp_path: Path) -> None:
    script = "import os, sys; open('marker', 'w').close(); sys.exit(3)"

    exit_code = SubprocessRunner().run_and_wait(
        [sys.executable, "-c", script], tmp_path
    )

    assert exit_code == 3
    assert (tmp_path / "marker").exists()


def test_missing_program_raises_launch_error_with_command(tmp_path: Path) -> None:
    with pytest.raises(ClaudeLaunchError, match="programa-inexistente-xyz"):
        SubprocessRunner().run_and_wait(["programa-inexistente-xyz"], tmp_path)


def test_start_detached_missing_program_raises_launch_error(tmp_path: Path) -> None:
    with pytest.raises(ClaudeLaunchError, match="programa-inexistente-xyz"):
        SubprocessRunner().start_detached(["programa-inexistente-xyz"], tmp_path)
