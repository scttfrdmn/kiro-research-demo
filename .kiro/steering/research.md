---
inclusion: always
---

# Research code rules for this lab

These rules apply to every change in this repository.

## Correctness
- Every test asserts a value that is known exactly or analytically. Do not write tests that only compare two outputs of our own code to each other: both can share the same mistake.
- Build identity checks so they are exact or wrong, not approximately right. If quantities should sum to a known total, construct them so they sum to it to floating-point rounding, and assert that.
- State the tolerance of every numerical assertion and why that tolerance is justified.

## Reproducibility
- Pin random seeds and package versions. Record the data source and its checksum for any input file.
- Never edit a reported or expected number without re-running the computation that produces it.
- Run all Python through `uv run` (`uv run pytest ...`, `uv run python ...`). Never call `python`, `python3` or `.venv/bin/python` directly.

## Scope
- Make the smallest change that satisfies the approved requirements. Do not add frameworks, configuration systems, or abstractions the requirements do not ask for.
- A task is done when its acceptance check passes, not when the code is written.

## Reporting
- Never state a number you did not compute in this session. Quote results from the actual output.
- Prices, quotas, capacity and runtimes come only from a tool result in this session. If no tool returned the number, say it is unknown; do not supply one from memory or the web.
