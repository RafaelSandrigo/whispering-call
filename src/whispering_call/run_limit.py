"""Quantas gravações pendentes processar em uma execução.

O pipeline pergunta a uma ``RunLimitPolicy`` depois de listar as pendentes. A
política fixa vem de ``--limit``, a "todas" de ``--all`` (ou de ambientes sem
terminal) e a interativa pergunta ao usuário no começo da execução.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from whispering_call.errors import WhisperingCallError

ALL_ANSWERS: frozenset[str] = frozenset({"", "t", "todas", "todos", "a", "all"})


class RunLimitPolicy(Protocol):
    def choose(self, pending_keys: Sequence[str]) -> int | None:
        """Quantas pendentes processar; ``None`` = todas."""
        ...


class AllPending:
    """Processa tudo (comportamento anterior; padrão sem terminal interativo)."""

    def choose(self, pending_keys: Sequence[str]) -> int | None:
        return None


class FixedLimit:
    """Limite vindo de ``--limit N``.

    Exemplo::

        FixedLimit(2).choose(["a.mp4", "b.mp4", "c.mp4"])  # 2
    """

    def __init__(self, count: int) -> None:
        if count < 1:
            raise ValueError(
                f"limite deve ser um inteiro maior que zero; recebido {count!r}"
            )
        self._count = count

    def choose(self, pending_keys: Sequence[str]) -> int | None:
        return self._count


class AskUserLimit:
    """Lista as pendentes e pergunta quantas processar (Enter = todas).

    ``ask`` e ``tell`` são injetados (``input`` e ``reporter.info`` na CLI).

    Exemplo::

        AskUserLimit(input, print).choose(["a.mp4", "b.mp4"])
    """

    def __init__(self, ask: Callable[[str], str], tell: Callable[[str], None]) -> None:
        self._ask = ask
        self._tell = tell

    def choose(self, pending_keys: Sequence[str]) -> int | None:
        # Com uma só pendente não há o que escolher.
        if len(pending_keys) < 2:
            return None
        self._tell(f"{len(pending_keys)} gravações pendentes:")
        for key in pending_keys:
            self._tell(f"  - {key}")
        return self._ask_until_valid(len(pending_keys))

    def _ask_until_valid(self, pending_count: int) -> int | None:
        question = (
            f"Quantas processar nesta execução? [1-{pending_count}, Enter = todas]: "
        )
        while True:
            try:
                return parse_limit_answer(self._read_answer(question))
            except ValueError as error:
                self._tell(str(error))

    def _read_answer(self, question: str) -> str:
        try:
            return self._ask(question)
        except EOFError as error:
            raise WhisperingCallError(
                "Entrada encerrada antes de escolher quantas gravações processar "
                "(use --limit N ou --all para não perguntar)"
            ) from error


def parse_limit_answer(answer: str) -> int | None:
    """Converte a resposta digitada; ``None`` = todas. Levanta ``ValueError`` se inválida.

    Exemplo::

        parse_limit_answer("3")  # 3
        parse_limit_answer("")   # None
    """
    text = answer.strip().lower()
    if text in ALL_ANSWERS:
        return None
    if text.isdigit() and int(text) >= 1:
        return int(text)
    raise ValueError(
        f"Valor inválido {answer!r}: digite um inteiro maior que zero ou Enter para todas"
    )
