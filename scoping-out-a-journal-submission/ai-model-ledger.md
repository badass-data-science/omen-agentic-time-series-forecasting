# AI model ledger

*Started 2026-10-15.* A running record of **every AI model used on this
project, with exact identifiers**, so that papers (the JOSS paper, the
evaluation preprint) can report them correctly. JOSS requires an AI usage
disclosure naming the tools and models, **with versions**, and where each
was used; an incomplete or inaccurate disclosure is treated as an ethical
breach. Most journals now ask for the same.

Two different roles are tracked separately, because papers report them
differently:

- **Part A, models under evaluation:** the LLMs that are *subjects* of the
  evaluation study. These go in the preprint's Methods section.
- **Part B, AI assistance:** models that helped *build* Omen, the
  evaluation, the book, or the papers. These go in each paper's AI usage
  disclosure.

**Rules**
- Record the **exact model ID** as the provider identifies it (for
  Anthropic models, the API ID such as `claude-opus-5-5`), never only a
  marketing name or an alias. Where only a display name is known, say so
  and mark it *to confirm*.
- Record the **tool and its version** used to access the model (e.g. Claude
  Code 2.1.301), the **dates**, and **what the model did**.
- Add a Part B row for every working session, before or alongside its
  commits. Commit trailers (`Co-Authored-By: <model>`) are a useful audit
  trail but are not a substitute: they give display names only, and
  untrailered commits can still be AI-assisted.
- For evaluation runs, the per-run source of truth is the harness's
  trajectory log (Eval 03, #45), which records the model ID **returned by
  the API** for every run. Part A summarizes it.

## Part A: models under evaluation

Selected at Eval 01 (#43); see `evaluation/records/eval-01-scope-decisions.md`.

| Model | Exact ID | Provider / access route | Training cutoff | Role | Status |
|---|---|---|---|---|---|
| GLM-5.2 | *to confirm at Eval 02/03* | Ollama Cloud | *to confirm (Eval 02, #44)* | Pilot model (Eval 07) and main study | Selected |
| One Claude model | *chosen at Eval 08 (#50)*, e.g. `claude-sonnet-5-5` or `claude-haiku-5-5` | Anthropic API | June 2026 (Claude 5 generation) | Main study | Pending |

Sampling settings, endpoints, and run dates are recorded per run in the
harness logs and summarized in the Eval 07/09/13/15 records.

## Part B: AI assistance in development and writing

| Dates | Tool (version) | Model (exact ID) | What it did | Human role | Evidence |
|---|---|---|---|---|---|
| 2026-07-20 – 2026-07-28 | Claude Code (*version to confirm*) | Claude Sonnet 5 (*exact API ID to confirm*) | Omen code, tests, and docs during the initial development and repo extraction | Design decisions, review, merging | 89 commits with `Co-Authored-By: Claude Sonnet 5` |
| Development period (dates to confirm) | OpenClaw + Ollama Cloud | GLM-5.2 (*exact ID to confirm*) | The agent driving Omen's tools while the skills were developed and tested (per `AGENTS.md`); not a code author | Prompting, evaluation of agent behavior | `AGENTS.md`, `SKILL.md` playbooks |
| *to confirm* | *to confirm* | *to confirm* | Companion book drafting and its cover image (per `book/ai_use_statement.md`) | Authorship, editing | `book/ai_use_statement.md` |
| 2026-10-13 – 2026-10-15 | Claude Code 2.1.301 | Claude Opus 5.5 (`claude-opus-5-5`) | fastmcp ≥3.2 compatibility fix (#29) and 0.0.4/0.0.5 release prep; statsmodels 0.15 deprecation fixes (#34, #38, #39, #40) and the test fix (#41); CONTRIBUTING/SUPPORT/Code of Conduct (#27); JOSS publication assessment and evaluation plan; evaluation-plan issues #43–#59; Eval 01 record (#60); this ledger | Scope and design decisions, review, merges, PyPI publishing | 11+ commits with `Co-Authored-By: Claude Opus 5.5`; PRs #27–#60 |

## Gaps to close before writing a disclosure

- Exact API IDs for Claude Sonnet 5 (July 2026) and GLM-5.2, and the Claude
  Code version used in July.
- Whether the book text and cover image involved models not listed above.
- `book/ai_use_statement.md` is informal and does not name tools,
  versions, or scope. It would not satisfy JOSS's requirement on its own;
  the JOSS paper needs a disclosure built from this ledger.
