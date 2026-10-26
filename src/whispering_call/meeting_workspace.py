"""Pasta de saída de uma reunião: transcrição, cópia do prompt e doc final.

O estado "já processado" é derivado destes arquivos (não há banco/JSON de
estado): sem ``transcript.md`` → transcrever; sem ``doc.md`` → abrir o Claude.
Isso torna a execução idempotente e retomável após falhas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from whispering_call.recordings import Recording

TRANSCRIPT_FILE_NAME = "transcript.md"
DOC_FILE_NAME = "doc.md"
PROMPT_COPY_FILE_NAME = "doc_prompt.md"

# Caracteres proibidos em nomes de arquivo no Windows; aplicado em todo SO para
# que a mesma pasta de saída funcione nos dois (ex.: output/ dentro do Drive).
_WINDOWS_FORBIDDEN_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class MeetingWorkspace:
    folder: Path

    @property
    def transcript_file(self) -> Path:
        return self.folder / TRANSCRIPT_FILE_NAME

    @property
    def doc_file(self) -> Path:
        return self.folder / DOC_FILE_NAME

    @property
    def prompt_copy_file(self) -> Path:
        return self.folder / PROMPT_COPY_FILE_NAME

    def has_transcript(self) -> bool:
        return self.transcript_file.is_file()

    def has_doc(self) -> bool:
        return self.doc_file.is_file()

    def save_transcript(self, markdown: str) -> None:
        """Grava a transcrição de forma atômica.

        Um ``transcript.md`` pela metade (queda no meio da escrita) seria lido
        como "já transcrito" na próxima execução; por isso escreve num arquivo
        temporário e renomeia.

        Exemplo::

            workspace.save_transcript("# Transcrição\\n- [00:00:01] Olá\\n")
        """
        partial_file = self.folder / f"{TRANSCRIPT_FILE_NAME}.partial"
        _write_utf8(partial_file, markdown)
        partial_file.replace(self.transcript_file)

    def save_prompt_copy(self, prompt_text: str) -> Path:
        """Copia o prompt da doc para dentro da pasta da reunião.

        O Claude roda com esta pasta como diretório de trabalho, então todos os
        arquivos que ele precisa ler ficam acessíveis sem ``--add-dir`` (que é
        variádico e engoliria o prompt posicional). Também registra qual versão
        do prompt gerou a doc.

        Exemplo::

            prompt_path = workspace.save_prompt_copy("Gere uma ata...")
        """
        _write_utf8(self.prompt_copy_file, prompt_text)
        return self.prompt_copy_file


def workspace_for(recording: Recording, output_root: Path) -> MeetingWorkspace:
    """Pasta de saída da gravação, ex.: ``output/2026__kickoff_mp4``.

    Exemplo::

        workspace_for(Recording(Path("r/a.mp4"), "a.mp4"), Path("output")).folder
    """
    return MeetingWorkspace(folder=output_root / folder_name_for(recording.key))


def folder_name_for(recording_key: str) -> str:
    """Nome de pasta único e válido em Windows/Linux para uma ``Recording.key``.

    A extensão entra no nome para que ``a.mp4`` e ``a.mkv`` não colidam.

    Exemplo::

        folder_name_for("2026/kick off.mp4")  # "2026__kick off_mp4"
    """
    key_path = PurePosixPath(recording_key)
    extension = key_path.suffix.lstrip(".")
    stem_path = key_path.with_suffix("").as_posix().replace("/", "__")
    name = f"{stem_path}_{extension}" if extension else stem_path
    # Windows não aceita nomes terminados em ponto ou espaço.
    return _WINDOWS_FORBIDDEN_CHARACTERS.sub("_", name).rstrip(". ") or "recording"


def _write_utf8(target_file: Path, text: str) -> None:
    # encoding explícito: o padrão no Windows é cp1252 e corromperia acentos.
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(text, encoding="utf-8", newline="\n")
