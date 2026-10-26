from pathlib import Path

import pytest

from whispering_call.config import (
    DEFAULT_EXTENSIONS,
    LaunchMode,
    default_new_window_command,
    load_config,
)
from whispering_call.errors import ConfigError


def write_config(folder: Path, content: str) -> Path:
    config_file = folder / "config.toml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def test_empty_config_uses_defaults_relative_to_config_folder(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, ""), "linux")

    assert config.recordings.folder == (tmp_path / "recordings").resolve()
    assert config.recordings.extensions == DEFAULT_EXTENSIONS
    assert config.output.folder == (tmp_path / "output").resolve()
    assert config.transcription.model == "large-v3"
    assert config.transcription.language == "pt"
    assert config.claude.launch_mode is LaunchMode.SAME_TERMINAL
    assert (
        config.claude.prompt_file == (tmp_path / "prompts" / "doc_prompt.md").resolve()
    )


# {absolute} vira um caminho absoluto real (tmp_path), válido em Windows e Linux.
EXPLICIT_CONFIG = """
[recordings]
folder = '{absolute}'
extensions = [".MP4"]
recursive = true

[transcription]
device = "cpu"
compute_type = "int8"
beam_size = 3

[claude]
launch_mode = "new_window"
extra_args = ["--model", "opus"]
new_window_command = ["kitty", "{{command}}"]
"""


def test_explicit_values_are_read(tmp_path: Path) -> None:
    absolute = tmp_path / "gravacoes"
    content = EXPLICIT_CONFIG.format(absolute=absolute)

    config = load_config(write_config(tmp_path, content), "linux")

    assert config.recordings.folder == absolute
    assert config.recordings.extensions == (".mp4",)
    assert config.recordings.recursive is True
    assert config.transcription.device == "cpu"
    assert config.transcription.beam_size == 3
    assert config.claude.launch_mode is LaunchMode.NEW_WINDOW
    assert config.claude.extra_args == ("--model", "opus")
    assert config.claude.new_window_command == ("kitty", "{command}")


def test_missing_file_points_to_example(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config.example.toml"):
        load_config(tmp_path / "nao-existe.toml", "linux")


def test_invalid_toml_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="TOML inválido"):
        load_config(write_config(tmp_path, "[recordings"), "linux")


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ('[claude]\nlaunch_mode = "popup"', r"\[claude\]\.launch_mode .*'popup'"),
        ("[transcription]\nbeam_size = true", r"\[transcription\]\.beam_size .*True"),
        ("[transcription]\nbeam_size = 0", r"inteiro maior que zero; recebido 0"),
        ("[recordings]\nrecursive = 1", r"true ou false; recebido 1"),
        ('[recordings]\nextensions = "mp4"', r"lista de textos.*'mp4'"),
        ('[recordings]\nextensions = ["mp4"]', r"começar com ponto.*\['mp4'\]"),
        ('[claude]\nexecutable = ""', r"texto não vazio; recebido ''"),
        ('[logging]\nlevel = "TRACE"', r"'TRACE'"),
        ('recordings = "x"', r"\[recordings\] deve ser uma tabela"),
    ],
)
def test_invalid_values_report_key_value_and_shape(
    tmp_path: Path, content: str, expected_message: str
) -> None:
    with pytest.raises(ConfigError, match=expected_message):
        load_config(write_config(tmp_path, content), "linux")


def test_window_command_without_placeholder_is_rejected(tmp_path: Path) -> None:
    content = '[claude]\nnew_window_command = ["kitty"]'

    with pytest.raises(ConfigError, match=r"\{command\}.*\['kitty'\]"):
        load_config(write_config(tmp_path, content), "linux")


def test_empty_window_command_falls_back_to_platform_default(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, ""), "win32")

    assert config.claude.new_window_command == default_new_window_command("win32")


def test_default_window_command_per_platform() -> None:
    assert default_new_window_command("linux")[0] == "konsole"
    windows_command = default_new_window_command("win32")
    assert windows_command[:3] == ("cmd", "/c", "start")
    # O título precisa ter espaço para virar argumento entre aspas (ver config.py).
    assert " " in windows_command[3]


def test_shipped_example_config_is_valid() -> None:
    # Regressão: o config.example.toml documentado precisa continuar carregável.
    example = Path(__file__).resolve().parent.parent / "config.example.toml"

    config = load_config(example, "linux")

    assert config.claude.launch_mode is LaunchMode.SAME_TERMINAL
    assert config.claude.prompt_file.is_file()
