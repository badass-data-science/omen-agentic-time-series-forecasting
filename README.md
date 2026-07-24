# Omen — An Agentic Time Series Forecasting Platform

<img src="https://raw.githubusercontent.com/badass-data-science/omen-agentic-time-series-forecasting/main/book/title-page-image.png" width="400" alt="Omen title page illustration" />

**Omen gives an AI agent a tested, statistically rigorous toolkit for time
series forecasting, instead of letting it improvise the statistics
itself.** Five FastMCP servers, one per stage of a forecast's real
lifecycle, installable as a single `pip install`.

```bash
pip install "omen-agentic-forecasting[all]"
```

*Status: Alpha, published on PyPI. 161 real tests, and every worked
example in the companion book was run against live tool output, not
hand-typed. CI (GitHub Actions) runs the full suite plus ruff linting and
mypy type-checking on every push and PR.*

## Why This Exists

Time series forecasting is a well-studied statistical discipline, but
it's easy to get wrong in ways that look fine until they aren't: skipping
a stationarity check, never comparing against a naive baseline, reporting
a point forecast with no confidence interval attached. Ask a
general-purpose AI model to "forecast this series" and it will typically
write plausible-looking `pandas`/`statsmodels` code from memory that
skips exactly those checks — not because the statistics are hard to
name, but because getting them right, correctly, inside freshly
improvised code, every single time, is a much harder ask of an LLM than
it looks.

Omen's answer is to stop asking an agent to improvise the statistics at
all. Every operation here — checking stationarity, backtesting a model
against a real holdout, computing a confidence interval, deciding whether
a retrained candidate is actually worth redeploying — is a pre-built,
tested, typed tool, exposed over the Model Context Protocol (MCP) as a
FastMCP server with a companion OpenClaw skill (the reasoning workflow
around those tools). An AI agent's job becomes choosing which tool to
call next and reasoning about the structured result that comes back, not
writing statistics code from scratch. Consequential actions, like
redeploying a live model, are gated behind an explicit, code-checked
confirmation rather than left to an agent's judgment call; open-ended
reasoning, like which model family fits a series' shape, is left to the
agent, where it belongs.

## The Five Layers

That split shows up as five layers, each covering one stage of a
forecast's real lifecycle, from first looking at the data through
deciding whether to retrain months later:

- **Layer 1 — `ts-analyst`**: explore a series — stationarity,
  seasonality, anomalies, structural breaks — and recommend a
  forecasting approach with reasoning attached.
- **Layer 2 — `ts-forecaster`**: fit candidate models against a common
  held-out window, backtest them (optionally across multiple rolling
  origins), compare them statistically, and recommend one grounded in
  real error metrics and residual diagnostics.
- **Layer 3 — `ts-deploy`**: retrain the chosen model on the full series
  and produce a real forecast beyond the end of the data, with
  prediction intervals wherever a model can honestly support one
  (including gradient-boosted trees, via quantile regression), an
  automated plausibility check against the series' own history, and an
  optional weighted ensemble across multiple candidates.
- **Layer 4 — `ts-monitor`**: once real observations exist, check
  whether the deployed forecast is still tracking reality (with a
  bootstrap confidence interval on its error metrics), detect data drift
  (with an effect size, not just a bare p-value), and recommend whether
  to retrain — flagging when that recommendation is itself close to the
  threshold rather than clear-cut.
- **Layer 5 — `ts-retrain`**: when `ts-monitor` says `retrain_now`,
  re-run Layers 1–2 on the updated series and deterministically decide
  whether the freshly backtested candidate beats what's currently
  deployed by enough to be worth redeploying, confidence-interval-aware
  on both sides of that comparison. Never redeploys without an explicit
  `confirmed=True` — by default that means stopping for human
  confirmation, and the optional autonomous-mode alternative is backed
  by a real, code-checked authorization record, not just a prose
  contract.

Layers 1–4 also expose 13 `plot_*` tools between them (Layer 5
deliberately has none — a redeploy verdict has no natural chart) that
render a matplotlib figure and return it as an inline image in the same
turn, with an optional `out_path` to also save a PNG to disk. These are
strictly supplementary: every plot re-derives its picture from the exact
same computation its JSON counterpart already returns, so a chart can
never silently disagree with the numbers behind it.

## Quick Start

```bash
pip install "omen-agentic-forecasting[all]"
```

That installs every layer's dependencies and five console scripts
(`ts-analyst-server`, `ts-forecaster-server`, `ts-deploy-server`,
`ts-monitor-server`, `ts-retrain-server`), each a FastMCP server ready to
register with any MCP-speaking agent client — OpenClaw, Claude Code,
Claude Desktop, or similar. A ready-to-merge OpenClaw config snippet,
`openclaw.config.snippet.jsonc`, lives at the repo root. Only need a
subset of layers? Per-layer extras exist too: `[analyst]`,
`[forecaster]`, `[deploy]`, `[monitor]`, `[retrain]`.

**For the full platform-by-platform setup walkthrough** — OpenClaw,
Claude Code, generic MCP clients, and the single most common
installation gotcha (narrated as it actually happened) — see
`book/chapter-02-installing-omen.md`.

Once connected, a single message can drive the whole pipeline:

> Use ts-analyst to explore a synthetic time series, then use
> ts-forecaster to fit and backtest candidate models informed by what
> you found, then use ts-deploy to produce a 30-day forecast with the
> best-performing model and settings.

## Using It End to End

Once time has passed and the CSV has real new observations:

> Use ts-monitor to check whether that forecast is holding up against
> what actually happened, and tell me if I should retrain.

Right after that first real `ts-deploy` call, record what got deployed
so Layer 5 has a baseline to compare against later:

> Use ts-retrain to record that this model and its backtest metrics are
> now deployed.

If `ts-monitor` comes back with `retrain_now`:

> Use ts-retrain to re-run analyst and forecaster on the updated series
> and tell me whether the new candidate is actually worth redeploying.

That call stops at the verdict — `ts-retrain` never redeploys on its own
in the default mode. If the verdict says `should_redeploy: true` and you
want to proceed, confirm it explicitly in a follow-up message:

> Go ahead and redeploy the candidate you just recommended.

which is what actually triggers `ts-retrain__execute_redeploy(...,
confirmed=True)` and updates the manifest.

If you'd rather not be asked each time for a specific series, opt into
autonomous mode explicitly:

> For the `daily_demand.csv` series specifically, you're authorized to
> redeploy automatically whenever ts-retrain finds a candidate that
> beats the current deployment — no need to ask me first. Everything
> else still needs my confirmation as usual.

That grant is what the agent should turn into a persisted record via
`ts-retrain__authorize_autonomous_mode(csv_path="daily_demand.csv",
authorized_by="user, in conversation")` — not just remember for the rest
of the session. With that record in place, a later `retrain_now` cycle
for that series will call `execute_redeploy(confirmed=True,
autonomous=True)` itself once `should_redeploy: true` comes back (which
itself re-checks the record before acting), and report what it did
rather than pausing to ask.

## Learn More

- **`book/`** — *Agentic Time Series Forecasting for Supervillains*, a
  complete 22-chapter e-book (plus glossary, tool reference, and
  further-reading appendices) teaching time series forecasting through
  this toolkit, one concept per chapter, each worked example run for
  real against the live MCP servers rather than hand-typed. Start at
  `book/outline.md` or jump straight to `book/chapter-01-*.md`.
- **`book/appendix-b-tool-reference.md`** — a one-line-per-tool lookup
  table across all five layers, if you just want to know what a given
  tool does without reading the chapter that introduces it.
- **`AGENTS.md`** — the project's own dense, internal design log: exact
  tool mechanics, confirmed edge cases, and non-obvious conventions,
  written for whoever picks up this code next rather than for a first
  read.
- **`blog-posts/`** — shorter, punchier write-ups covering the same five
  layers, one post per layer plus an introductory overview.
- **`prompts/testing-and-learning-prompts.md`** — ready-to-use prompts
  across all five layers for hands-on practice with your own data.

## Project Layout

```
omen/
├── pyproject.toml
├── LICENSE
├── README.md
├── AGENTS.md
├── .gitignore
├── openclaw.config.snippet.jsonc
├── .github/
│   └── workflows/
│       └── ci.yml              # ruff + mypy + pytest (3.10/3.11/3.12) on every push/PR
├── graphify-out/                # knowledge graph of this repo (code + docs + book + images)
│   ├── graph.json              # GraphRAG-ready nodes/edges
│   ├── graph.html              # interactive visualization
│   ├── GRAPH_REPORT.md         # plain-language summary
│   ├── manifest.json
│   └── .graphify_labels.json
├── src/
│   └── omen/
│       ├── __init__.py            # version + skills_dir() helper
│       ├── data_prep.py           # shared: synthetic data + CSV loader (used by all 5 layers)
│       ├── plotting.py            # shared: render_plot() -- inline Image + optional PNG, used by all plot_* tools
│       ├── analyst/
│       │   ├── __init__.py
│       │   ├── analysis_tools.py  # Layer 1 diagnostic functions
│       │   ├── plot_tools.py      # Layer 1 plotting functions (6 tools)
│       │   └── server.py          # FastMCP server: ts-analyst
│       ├── forecaster/
│       │   ├── __init__.py
│       │   ├── model_tools.py     # Layer 2 fit/backtest functions
│       │   ├── plot_tools.py      # Layer 2 plotting functions (3 tools)
│       │   └── server.py          # FastMCP server: ts-forecaster
│       ├── deploy/
│       │   ├── __init__.py
│       │   ├── forecast_tools.py  # Layer 3 retrain/forecast functions
│       │   ├── plot_tools.py      # Layer 3 plotting functions (1 tool)
│       │   └── server.py          # FastMCP server: ts-deploy
│       ├── monitor/
│       │   ├── __init__.py
│       │   ├── monitor_tools.py   # Layer 4 comparison/drift/retrain-decision functions
│       │   ├── plot_tools.py      # Layer 4 plotting functions (3 tools)
│       │   └── server.py          # FastMCP server: ts-monitor
│       ├── retrain/
│       │   ├── __init__.py
│       │   ├── retrain_tools.py   # Layer 5 deployment-manifest + redeploy-decision functions
│       │   └── server.py          # FastMCP server: ts-retrain (no plotting tools -- see below)
│       └── skills/                # bundled as package data -- see skills_dir()
│           ├── ts-analyst/SKILL.md
│           ├── ts-forecaster/SKILL.md
│           ├── ts-deploy/SKILL.md
│           ├── ts-monitor/SKILL.md
│           └── ts-retrain/SKILL.md
├── tests/
│   ├── test_data_prep.py
│   ├── test_analyst_tools.py
│   ├── test_analyst_plot_tools.py
│   ├── test_forecaster_tools.py
│   ├── test_forecaster_plot_tools.py
│   ├── test_deploy_tools.py
│   ├── test_deploy_plot_tools.py
│   ├── test_monitor_tools.py
│   ├── test_monitor_plot_tools.py
│   └── test_retrain_tools.py
├── blog-posts/                    # draft write-ups about this project, not part of the package
│   ├── introducing-omen.md
│   ├── ts-analyst-gets-a-statistics-degree.md
│   ├── ts-forecaster-shows-its-work.md
│   ├── ts-deploy-ships-it.md
│   ├── ts-monitor-learns-to-doubt-good-news.md
│   └── ts-retrain-checks-its-papers.md
├── prompts/                       # ready-to-use prompts for testing/learning each layer
│   └── testing-and-learning-prompts.md
└── book/                          # "Agentic Time Series Forecasting for Supervillains" e-book, not part of the package
    ├── dedication.md, ai_use_statement.md, about_the_author.md
    ├── title-page-image.png       # cover image, also embedded above and on the book's title page
    ├── outline.md
    ├── chapter-01-introducing-omen-and-agentic-ai.md ... chapter-22-conclusion.md
    ├── appendix-a-glossary.md, appendix-b-tool-reference.md, appendix-c-further-reading.md
    └── examples/
        ├── README.md                  # how the dataset/plot/assembly scripts fit together
        ├── generate_book_datasets.py  # regenerates every dataset the book uses
        ├── generate_book_plots.py     # regenerates every plot image the book embeds
        ├── assemble_book.py           # concatenates the book into one Markdown file + PDF
        └── images/                    # the 32 real PNGs embedded in the book's chapters
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -e ".[all,dev]"    # editable install, every layer + test deps
pytest                          # 161 tests
ruff check .                    # lint
mypy                            # type-check
```

Sanity-check each server runs standalone (Ctrl+C to stop; no
output/crash = good):

```bash
ts-analyst-server
ts-forecaster-server
ts-deploy-server
ts-monitor-server
ts-retrain-server
```

The importable module stays plain `omen` regardless of install method —
only the PyPI *listing* name is `omen-agentic-forecasting` (plain `omen`
was already taken; see the comment above `[project.scripts]` in
`pyproject.toml`). See `AGENTS.md` for build/release commands and the
full set of non-obvious project conventions.
