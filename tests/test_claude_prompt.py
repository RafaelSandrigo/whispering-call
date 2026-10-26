from pathlib import Path

from whispering_call.claude_prompt import build_initial_prompt


def test_prompt_mentions_all_three_paths_on_a_single_line() -> None:
    prompt = build_initial_prompt(
        Path("/out/a/doc_prompt.md"),
        Path("/out/a/transcript.md"),
        Path("/out/a/doc.md"),
    )

    assert str(Path("/out/a/doc_prompt.md")) in prompt
    assert str(Path("/out/a/transcript.md")) in prompt
    assert str(Path("/out/a/doc.md")) in prompt
    assert "\n" not in prompt
    assert '"' not in prompt
