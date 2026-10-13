# Changelog

All notable changes to the `omen-agentic-forecasting` package are documented
here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/),
and versioning follows [Semantic Versioning](https://semver.org/) (while the
major version is `0`, expect the occasional breaking change on a minor bump).

This tracks the installable **package** (`src/omen/`). The companion book,
blog posts, and other repo content change frequently and aren't versioned
here — see `git log` for that history.

## [Unreleased]

### Fixed
- ETS simulated prediction intervals (`fit_ets`, `forecast_ets`, and
  `forecast_ensemble` with ETS) passed `random_state=seed` to statsmodels'
  `simulate()`, which statsmodels 0.15 deprecates in favor of `rng`. It also
  plans to start treating an int seed as `np.random.default_rng(seed)`
  instead of `np.random.RandomState(seed)`, which would have silently
  changed every ETS interval for the same seed. These calls now pass
  `rng=np.random.RandomState(seed)`, verified to give byte-identical output
  to 0.0.4. (#30)
- `check_stationarity` read `adfuller()`'s and `kpss()`'s results as plain
  tuples (by position for ADF, by 4-way unpacking for KPSS). statsmodels
  0.15 warns that both will return result objects by default from 0.16 or
  July 2027, which would have broken or silently corrupted the ADF/KPSS
  fields. Both calls now pass `result_object=True` and read named fields,
  verified to give identical output. (#36, #37)
- `acf_pacf_summary` and `plot_acf_pacf` (via their shared helper) unpacked
  `acf()`'s result as a 2-tuple, which statsmodels 0.15 warns will become an
  `AcfResult` by default from 0.16 or July 2027. The call now passes
  `result_object=True` and reads `.acf`/`.confint`, verified to give
  identical output and identical plot images. `pacf()` is unchanged: called
  without `alpha`, it keeps returning a plain array. (#35)

### Changed
- Minimum statsmodels raised from 0.14 to 0.15 (in the `analyst`,
  `forecaster`, `deploy`, and `all` extras), since 0.14 has no `rng`
  keyword.

## [0.0.4] - 2026-10-13

### Fixed
- Omen failed to import its plot tools with current fastmcp
  (`ModuleNotFoundError: No module named 'fastmcp.tools.tool'`), because
  `ToolResult` was imported from that private module path, which fastmcp 3.2
  moved and fastmcp 4 removed. `pyproject.toml` only required `fastmcp>=2.0`,
  so any fresh install resolved to fastmcp 4.x and hit this. `ToolResult` is
  now imported from the public `fastmcp.tools` package, and the dependency
  floor is raised to `fastmcp>=3.0` (2.x doesn't export it there). Verified
  with fastmcp 3.0.0 and 4.1.0, including plot tools returning inline PNGs
  through an MCP client. (#28)
- `omen.__version__` was hardcoded to `"0.1.0"` and never matched any
  published release; it now matches the package version.

## [0.0.3] - 2026-07-26

### Fixed
- The 0.0.2 fix below turned out to be incomplete: giving `order`/`seasonal_order`/
  `params`/etc. a proper item type stopped their *arrays* from being untyped, but
  every one of them was still `Optional`/`X | None = None`, which makes FastMCP
  export an `"anyOf": [{"type": "array"/"object", ...}, {"type": "null"}]` schema
  — and that `anyOf`-with-`null` wrapper is, on its own, enough to make some MCP
  clients stringify the value even when the non-null branch is fully, correctly
  typed. Confirmed live again against `fit_sarima`'s `order`/`seasonal_order` and
  `rolling_origin_backtest`'s `params` (the latter never had an item-typing
  problem at all — a bare `dict` has always exported as `{"type": "object"}`).
  Fixed by giving these parameters (and the equivalent ones in `ts-deploy`'s
  `forecast_sarima`/`forecast_gradient_boosted_trees`/`forecast_ensemble`) a
  concrete, non-`None` default instead, removing the `anyOf`/`null` branch from
  their schemas entirely. `forecast_ensemble`'s `weights` and `plot_backtest`'s
  `lower`/`upper` are deliberately left `Optional`, since `None` carries real,
  distinct meaning for those two that can't be replaced by a fixed default.

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
