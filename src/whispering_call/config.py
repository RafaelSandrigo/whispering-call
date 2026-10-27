"""Leitura e validação do ``config.toml``.

Todo valor lido do TOML passa por ``_TomlSection`` para que um erro de
configuração aponte a chave, o valor recebido e o formato esperado.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whispering_call.errors import ConfigError

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".m4a",
    ".mp3",
    ".wav",
)
COMMAND_PLACEHOLDER = "{command}"
CWD_PLACEHOLDER = "{cwd}"
# Leve o bastante para rodar em CPU; GPU NVIDIA aguenta "large-v3" (config.example.toml).
DEFAULT_MODEL = "small"
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")


class LaunchMode(Enum):
    SAME_TERMINAL = "same_terminal"
    NEW_WINDOW = "new_window"


@dataclass(frozen=True)
class RecordingsSettings:
    folder: Path
    extensions: tuple[str, ...]
    recursive: bool


@dataclass(frozen=True)
class OutputSettings:
    folder: Path


@dataclass(frozen=True)
class TranscriptionSettings:
    model: str
    language: str
    device: str
    compute_type: str
    beam_size: int
    vad_filter: bool


@dataclass(frozen=True)
class ClaudeSettings:
    executable: str
    prompt_file: Path
    launch_mode: LaunchMode
    extra_args: tuple[str, ...]
    new_window_command: tuple[str, ...]


@dataclass(frozen=True)
class LoggingSettings:
    level: str


@dataclass(frozen=True)
class AppConfig:
    recordings: RecordingsSettings
    output: OutputSettings
    transcription: TranscriptionSettings
    claude: ClaudeSettings
    logging: LoggingSettings


class _TomlSection:
    """Acesso tipado a uma tabela TOML, com mensagens de erro acionáveis."""

    def __init__(self, name: str, table: dict[str, object], base_folder: Path) -> None:
        self._name = name
        self._table = table
        self._base_folder = base_folder

    def text(self, key: str, default: str) -> str:
        value = self._table.get(key, default)
        if isinstance(value, str) and value:
            return value
        raise ConfigError(self._describe(key, value, "um texto não vazio"))

    def flag(self, key: str, default: bool) -> bool:
        value = self._table.get(key, default)
        if isinstance(value, bool):
            return value
        raise ConfigError(self._describe(key, value, "true ou false"))

    def positive_integer(self, key: str, default: int) -> int:
        value = self._table.get(key, default)
        # bool é subclasse de int em Python; `beam_size = true` não deve passar.
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise ConfigError(self._describe(key, value, "um inteiro maior que zero"))

    def text_list(self, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = self._table.get(key, list(default))
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
        raise ConfigError(
            self._describe(key, value, 'uma lista de textos, ex.: ["a", "b"]')
        )

    def path(self, key: str, default: str) -> Path:
        raw = Path(self.text(key, default)).expanduser()
        return raw if raw.is_absolute() else (self._base_folder / raw).resolve()

    def choice(self, key: str, default: str, allowed: tuple[str, ...]) -> str:
        value = self.text(key, default)
        if value in allowed:
            return value
        raise ConfigError(self._describe(key, value, f"um de {list(allowed)}"))

    def _describe(self, key: str, value: object, expected: str) -> str:
        return f"[{self._name}].{key} deve ser {expected}; recebido {value!r}"


def load_config(config_file: Path, platform: str) -> AppConfig:
    """Lê ``config_file`` e devolve a configuração validada.

    Caminhos relativos são resolvidos a partir da pasta do arquivo de config,
    para que o resultado não dependa do diretório de onde a CLI foi chamada.

    Exemplo::

        config = load_config(Path("config.toml"), sys.platform)
        config.recordings.folder  # Path absoluto
    """
    root = _read_toml(config_file)
    base_folder = config_file.resolve().parent
    sections = {name: _open_section(root, name, base_folder) for name in _SECTION_NAMES}
    return AppConfig(
        recordings=_parse_recordings(sections["recordings"]),
        output=OutputSettings(folder=sections["output"].path("folder", "output")),
        transcription=_parse_transcription(sections["transcription"]),
        claude=_parse_claude(sections["claude"], platform),
        logging=LoggingSettings(
            level=sections["logging"].choice("level", "INFO", LOG_LEVELS)
        ),
    )


def default_new_window_command(platform: str) -> tuple[str, ...]:
    """Template de "nova janela" usado quando ``new_window_command`` está vazio.

    Exemplo::

        default_new_window_command("linux")  # ("konsole", "--workdir", "{cwd}", "-e", "{command}")
    """
    if platform == "win32":
        # `start` trata o primeiro argumento *entre aspas* como título da janela.
        # O título tem espaço de propósito: assim o subprocess o coloca entre
        # aspas e o `start` não o confunde com o programa a executar.
        return (
            "cmd",
            "/c",
            "start",
            "whispering call",
            "/D",
            CWD_PLACEHOLDER,
            COMMAND_PLACEHOLDER,
        )
    return ("konsole", "--workdir", CWD_PLACEHOLDER, "-e", COMMAND_PLACEHOLDER)


_SECTION_NAMES: tuple[str, ...] = (
    "recordings",
    "output",
    "transcription",
    "claude",
    "logging",
)


def _read_toml(config_file: Path) -> dict[str, object]:
    if not config_file.is_file():
        raise ConfigError(
            f"Arquivo de configuração não encontrado: {config_file} "
            "(esperado um arquivo TOML; copie config.example.toml para config.toml)"
        )
    try:
        with config_file.open("rb") as toml_stream:
            return tomllib.load(toml_stream)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"TOML inválido em {config_file}: {error}") from error


def _open_section(
    root: dict[str, object], name: str, base_folder: Path
) -> _TomlSection:
    table = root.get(name, {})
    if not isinstance(table, dict):
        raise ConfigError(f"[{name}] deve ser uma tabela TOML; recebido {table!r}")
    return _TomlSection(name, table, base_folder)


def _parse_recordings(section: _TomlSection) -> RecordingsSettings:
    return RecordingsSettings(
        folder=section.path("folder", "recordings"),
        extensions=_normalize_extensions(
            section.text_list("extensions", DEFAULT_EXTENSIONS)
        ),
        recursive=section.flag("recursive", False),
    )


def _normalize_extensions(extensions: tuple[str, ...]) -> tuple[str, ...]:
    invalid = [extension for extension in extensions if not extension.startswith(".")]
    if invalid:
        raise ConfigError(
            f'[recordings].extensions devem começar com ponto, ex.: ".mp4"; recebido {invalid!r}'
        )
    return tuple(extension.lower() for extension in extensions)


def _parse_transcription(section: _TomlSection) -> TranscriptionSettings:
    return TranscriptionSettings(
        model=section.text("model", DEFAULT_MODEL),
        language=section.text("language", "pt"),
        device=section.choice("device", "auto", ("auto", "cuda", "cpu")),
        compute_type=section.text("compute_type", "auto"),
        beam_size=section.positive_integer("beam_size", 5),
        vad_filter=section.flag("vad_filter", True),
    )


def _parse_claude(section: _TomlSection, platform: str) -> ClaudeSettings:
    launch_mode = section.choice(
        "launch_mode", "same_terminal", tuple(m.value for m in LaunchMode)
    )
    return ClaudeSettings(
        executable=section.text("executable", "claude"),
        prompt_file=section.path("prompt_file", "prompts/doc_prompt.md"),
        launch_mode=LaunchMode(launch_mode),
        extra_args=section.text_list("extra_args", ()),
        new_window_command=_parse_window_command(section, platform),
    )


def _parse_window_command(section: _TomlSection, platform: str) -> tuple[str, ...]:
    template = section.text_list(
        "new_window_command", ()
    ) or default_new_window_command(platform)
    if COMMAND_PLACEHOLDER not in template:
        raise ConfigError(
            f"[claude].new_window_command precisa conter o item {COMMAND_PLACEHOLDER!r} "
            f'(ex.: ["kitty", "{COMMAND_PLACEHOLDER}"]); recebido {list(template)!r}'
        )
    return template
