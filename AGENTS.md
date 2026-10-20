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
| Codebase exploration & impact analysis | `graft ask "<query>" --source` / `graft skeleton <file>` (see the Graft section) |
| Automated unit & E2E testing | `docs/agents/testing.md` |
| Engineering workflow & skills | `docs/agents/workflows.md` |
| Scoping or simplifying a change | `ponytail` skill |
| Prose & Copy (docs, README, UI text) | `humanizer` skill |

## Anti-Rationalization
| Excuse | Rule |
| --- | --- |
| "I'll grep/read the whole folder to understand the module." | Forbidden. Query `graft ask "<query>" --source` or `graft callers <symbol>` first to save context tokens. |
| "Unit tests pass, so the feature works." | Insufficient. Unit tests do not verify wiring or rendering. Exercise the feature end to end (integration or smoke run) before marking complete. |
<!-- aginit:end -->

## Bootstrap & First Session
When the user asks to "bootstrap this project" or kicks off a new initiative:
1. Understand product intent and ask 2-3 essential questions to resolve ambiguity.
2. Draft or refine canonical context in `PRODUCT.md` and `DESIGN.md` (or `docs/adr/`).
3. Plan in small verifiable increments and implement test-first using installed skills.

<!-- graft:start -->
## Graft — repo context graph

This repo is indexed in `graft/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `graft map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `graft ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `graft grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `graft skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `graft callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `graft/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `graft ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `graft build` (deterministic,
no API key, $0).
<!-- graft:end -->
