# whispering-call

Pipeline em Python: gravação (pasta local) → faster-whisper → Claude Code gera a doc.
Visão geral em README.md; arquitetura e decisões em docs/architecture.md; melhorias em docs/roadmap.md.

## Comandos

- Testes: `uv run pytest`
- Tipos: `uv run mypy` (strict)
- Formatação: `uv run black src tests`
- Executar: `uv run whispering-call run`

## Restrições do projeto

- Deve funcionar em **Windows e Linux**: `encoding="utf-8"` explícito em todo I/O de texto,
  nada de `os.exec*`, comandos de terminal configuráveis, nomes de arquivo válidos no Windows.
- Python 3.12 (o CTranslate2 ainda não suporta o 3.14).
- Mantenha README.md e docs/ atualizados a cada mudança de comportamento ou config.
- Em caso de ambiguidade, pergunte ao usuário em vez de supor.

## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
  Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Tests

- Tests run with a single command: `uv run pytest`.
- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes,
  not inline stubs. Fakes live in `tests/fakes.py`.
- Tests must be F.I.R.S.T: fast, independent, repeatable,
  self-validating, timely.

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.
  Composition root: `cli.build_pipeline`.

## Formatting

- Use `black`. Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability (`json_logging.py`,
  campos extras via `extra={"fields": {...}}`).
- Plain text only for user-facing CLI output (`console_reporter.py`).
