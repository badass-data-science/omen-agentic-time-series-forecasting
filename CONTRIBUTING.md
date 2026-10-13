# Contributing to Omen

Thanks for your interest in Omen. Bug reports, questions, documentation
fixes, and code contributions are all welcome.

## Reporting bugs and asking questions

Open a [GitHub issue](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues).
For bug reports, please include:

- the Omen version (`pip show omen-agentic-forecasting`) and Python version,
- the tool you called (e.g. `ts-forecaster__fit_sarima`) and its arguments,
- the full error or the unexpected output, and what you expected instead,
- if possible, a small CSV (or `ts-analyst__generate_synthetic_data`
  settings) that reproduces the problem.

If the problem only shows up when an agent drives the tools, say which
MCP client and model you were using. Some bugs (for example, a client
sending a list argument as a JSON string) depend on the client, not on
Omen.

## Proposing changes

For anything beyond a small fix, please open an issue first so we can
agree on the approach before you write code. Some design choices in this
project are deliberate even when they look like oversights. For example,
decision tools are rule-based rather than LLM judgment calls, and some
helpers are intentionally duplicated across layers. `AGENTS.md` documents
these choices and the reasons for them.

## Development setup

```bash
git clone https://github.com/badass-data-science/omen-agentic-time-series-forecasting.git
cd omen-agentic-time-series-forecasting
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

Before opening a pull request, run the same checks CI runs:

```bash
pytest          # test suite (CI runs it on Python 3.10, 3.11, and 3.12)
ruff check .    # lint (ruff is pinned to an exact version in pyproject.toml)
mypy            # type-check src/omen
```

## Pull request guidelines

- Branch from `main` and keep each PR focused on one change.
- Add or update tests in `tests/` for any behavior change. Tests import
  the tool modules directly, not through `server.py`, so no MCP server
  is needed to run them.
- Follow the existing layout: tool logic lives in plain functions that
  take a DataFrame (`*_tools.py`), and `server.py` wraps them as
  `@mcp.tool()` and handles CSV loading.
- If you add or rename a tool, update the matching `SKILL.md` in
  `src/omen/skills/`, using the MCP-qualified name
  (e.g. `ts-analyst__basic_stats`). New tools keep the `ts-*` naming.
- Any MCP tool parameter that is a list must be parameterized
  (`list[float]`, not a bare `list`). Avoid `Optional` list/dict
  parameters unless `None` has a distinct meaning. `AGENTS.md` explains
  why.
- Any tool with randomness must pass its `seed` through to the random
  source. Verify this by calling the tool twice with the same inputs and
  comparing the outputs.
- Note user-visible changes under an `## [Unreleased]` heading at the top
  of `CHANGELOG.md` (add the heading if it isn't there yet).

PRs are squash-merged once CI passes and the change has been reviewed.

## Use of AI tools

Omen itself was developed with substantial help from AI coding
assistants, and AI-assisted contributions are welcome. You are
responsible for what you submit: please review and test AI-generated code
as carefully as your own, and mention in the PR description if a
substantial part of the change was AI-generated.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md),
version 2.1. By participating, you agree to uphold it. Report
unacceptable behavior to the contact listed there.

## License

By contributing, you agree that your contributions will be licensed under
the project's [MIT License](LICENSE).
