"""Prompt inicial passado ao Claude Code ao abrir a sessão de uma reunião."""

from __future__ import annotations

from pathlib import Path


def build_initial_prompt(
    prompt_file: Path, transcript_file: Path, doc_file: Path
) -> str:
    """Instrução curta que aponta para os arquivos; o conteúdo fica nos arquivos.

    Linha única, sem aspas nem metacaracteres de shell: no modo "nova janela"
    do Windows o texto atravessa o ``cmd /c start``, que quebraria em quebras
    de linha e reinterpretaria aspas.

    Exemplo::

        build_initial_prompt(Path("doc_prompt.md"), Path("transcript.md"), Path("doc.md"))
    """
    return (
        f"Leia as instruções de geração de documento em {prompt_file} e siga-as. "
        f"A transcrição da reunião está em {transcript_file}. "
        f"Gere o documento a partir da transcrição e salve-o em {doc_file}."
    )
