import pytest

from fakes import ScriptedAnswers
from whispering_call.errors import WhisperingCallError
from whispering_call.run_limit import (
    AllPending,
    AskUserLimit,
    FixedLimit,
    parse_limit_answer,
)

PENDING = ["a.mp4", "b.mp4", "c.mp4"]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("2", 2), (" 10 ", 10), ("", None), ("todas", None), ("ALL", None)],
)
def test_parse_limit_answer_accepts_numbers_and_all(
    answer: str, expected: int | None
) -> None:
    assert parse_limit_answer(answer) == expected


@pytest.mark.parametrize("answer", ["0", "-1", "dois", "1.5"])
def test_parse_limit_answer_rejects_invalid_with_the_value(answer: str) -> None:
    with pytest.raises(ValueError, match=repr(answer)):
        parse_limit_answer(answer)


def test_all_pending_and_fixed_limit() -> None:
    assert AllPending().choose(PENDING) is None
    assert FixedLimit(2).choose(PENDING) == 2


def test_fixed_limit_rejects_zero() -> None:
    with pytest.raises(ValueError, match="0"):
        FixedLimit(0)


def test_ask_user_lists_pending_and_returns_answer() -> None:
    told: list[str] = []
    answers = ScriptedAnswers("2")

    limit = AskUserLimit(answers, told.append).choose(PENDING)

    assert limit == 2
    assert told[0] == "3 gravações pendentes:"
    assert "  - b.mp4" in told
    assert "1-3" in answers.questions[0]


def test_ask_user_repeats_the_question_after_invalid_answer() -> None:
    told: list[str] = []
    answers = ScriptedAnswers("abc", "1")

    limit = AskUserLimit(answers, told.append).choose(PENDING)

    assert limit == 1
    assert len(answers.questions) == 2
    assert any("'abc'" in message for message in told)


def test_ask_user_does_not_ask_with_a_single_pending_recording() -> None:
    answers = ScriptedAnswers()

    assert AskUserLimit(answers, print).choose(["a.mp4"]) is None
    assert answers.questions == []


def test_closed_input_fails_with_actionable_message() -> None:
    with pytest.raises(WhisperingCallError, match="--limit"):
        AskUserLimit(ScriptedAnswers(), print).choose(PENDING)
