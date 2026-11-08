# Notes for AI agents

## Setting it up for someone

Follow "Quick start" in README.md. Let the user run `scalebridge login` themselves:
it asks for their Garmin password and 2FA code.

## Working on the code

- Python ≥ 3.12, managed with uv: `uv sync`, `uv run pytest`,
  `uv run ruff check . && uv run ruff format .`. CI runs all three.
- The pipeline and its extension points are described under "Architecture" in README.md.
  Keep modules independent: decoders know nothing about users, sinks know nothing about BLE.
- Behaviour shared with the ESP32 firmware is specified in `spec/vectors/`. When you
  change a decoder, change the vectors first, then make both the Python decoder and
  `firmware/esp32/components/scale_decoders` pass (`tests/test_firmware_decoders.py`
  compiles the C code with the host `cc`).
- Real BLE and Garmin are never touched by the tests. Use fakes like those in
  `tests/test_app.py`.
- `scalebridge scan` needs a Bluetooth adapter.
- Don't log weights at INFO for anything but finished weigh-ins, and never log tokens.

<!-- aginit:start — managed by npx @antomanc/aginit (re-run to refresh) -->
## Bootstrap & First Session
When the user asks to "bootstrap this project" or kicks off a new initiative:
1. Understand product intent and ask 2-3 essential questions to resolve ambiguity.
2. Draft or refine canonical context in `PRODUCT.md` and `DESIGN.md` (or `docs/adr/`).
3. Plan in small verifiable increments and implement test-first using installed skills.

## Guardrails (karpathy-guidelines)
- **Think before coding**: state assumptions and trade-offs; ask instead of guessing.
- **Simplicity first**: minimum code that solves the problem; no speculative features or abstractions.
- **Surgical changes**: touch only what the task needs; no silent scope creep or drive-by refactors.
- **Goal-driven execution**: define a verifiable success check first, then loop until it passes.

## Task Routing
Load only what the task needs. Skills live in `.agents/skills/` (linked into `.claude/skills/` for Claude Code).

| Task | Read / Use |
| --- | --- |
| Product intent, scope, target users | `PRODUCT.md` |
| Automated unit & E2E testing | `docs/agents/testing.md` |
| Engineering workflow & skills | `docs/agents/workflows.md` |
| Scoping or simplifying a change | `ponytail` skill |
| Prose & Copy (docs, README, UI text) | `humanizer` skill |

## Anti-Rationalization
| Excuse | Rule |
| --- | --- |
| "Unit tests pass, so the feature works." | Insufficient. Unit tests do not verify wiring or rendering. Exercise the feature end to end (integration or smoke run) before marking complete. |
<!-- aginit:end -->
