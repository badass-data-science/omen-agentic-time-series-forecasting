# Changelog

All notable changes to the `omen-agentic-forecasting` package are documented
here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/),
and versioning follows [Semantic Versioning](https://semver.org/) (while the
major version is `0`, expect the occasional breaking change on a minor bump).

This tracks the installable **package** (`src/omen/`). The companion book,
blog posts, and other repo content change frequently and aren't versioned
here — see `git log` for that history.

## [0.0.2] - 2026-07-25

### Fixed
- Bare `list`/`list | None` type hints on several `@mcp.tool()` parameters
  (starting with `fit_sarima`/`forecast_sarima`'s `order`/`seasonal_order`,
  found live by a user testing in Claude Desktop) produced an untyped MCP
  schema field, so some MCP clients couldn't tell the parameter should be a
  JSON array and fell back to sending it as a string, which then failed
  server-side validation. A repo-wide audit found the same mistake in 13
  total parameters across `ts-forecaster`, `ts-deploy`, and `ts-monitor`;
  all now use a proper item type (`list[int]`, `list[float]`, `list[str]`,
  or `list[dict]`, as appropriate).

### Added
- This changelog, and git tags (`v0.0.1`, `v0.0.2`, ...) marking each
  released version going forward.

### Changed
- CI now pins `ruff` to an exact version, rather than a floor, after an
  unpinned version let a routine ruff release silently expand its own
  default rule set and break CI on a PR that hadn't touched any `.py` file.

## [0.0.1] - 2026-07-22

Initial release.

### Added
- Five-layer FastMCP toolkit: `ts-analyst`, `ts-forecaster`, `ts-deploy`,
  `ts-monitor`, `ts-retrain` — each a typed-tool MCP server plus a
  companion OpenClaw skill, with 13 `plot_*` tools across the four
  analysis/forecasting/deployment/monitoring layers.
- Full test suite (161 tests) and GitHub Actions CI (ruff, mypy, pytest
  across Python 3.10-3.12).
- Companion 22-chapter e-book, *Agentic Time Series Forecasting for
  Supervillains*, plus six narrative blog posts, one per layer.
- Published to PyPI as `omen-agentic-forecasting` (the importable module
  stays plain `omen`; only the PyPI listing name differs, since plain
  `omen` was already taken).
