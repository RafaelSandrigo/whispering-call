"""Erros esperados do whispering-call.

Tudo que herda de ``WhisperingCallError`` é um problema que o usuário consegue
corrigir (config, pasta, executável); a CLI mostra a mensagem sem traceback.
"""


class WhisperingCallError(Exception):
    """Base dos erros acionáveis pelo usuário."""


class ConfigError(WhisperingCallError):
    """``config.toml`` ausente, malformado ou com valor inválido."""


class RecordingFolderError(WhisperingCallError):
    """A pasta de gravações configurada não existe."""


class PromptFileError(WhisperingCallError):
    """O arquivo de prompt de geração da doc não existe ou está vazio."""


class ClaudeLaunchError(WhisperingCallError):
    """O Claude Code (ou o terminal que o hospeda) não pôde ser iniciado."""
