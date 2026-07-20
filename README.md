# Omen

Five layers of agentic time series tooling, packaged as a normal
installable Python project. Each layer is a FastMCP server (typed tools)
plus a companion OpenClaw skill (the reasoning workflow around those
tools), bundled together so the whole thing installs and updates as one
package.

- **Layer 1 — `ts-analyst`**: explore a series (stationarity, seasonality,
  anomalies, structural breaks) and recommend a forecasting approach with
  reasoning.
- **Layer 2 — `ts-forecaster`**: fit candidate models against a common
  held-out window, backtest them (optionally across multiple rolling
  origins), compare them statistically, and recommend one with reasoning
  grounded in real error metrics and residual diagnostics.
- **Layer 3 — `ts-deploy`**: retrain the chosen model on the full series
  and produce a real forecast beyond the end of the data, with prediction
  intervals where available (now including gradient-boosted trees, via
  quantile regression), an automated plausibility check against the
  series' own history, and an optional weighted ensemble across multiple
  candidates.
- **Layer 4 — `ts-monitor`**: once real observations exist, check whether
  the deployed forecast is still tracking reality, detect data drift, and
  recommend whether to retrain.
- **Layer 5 — `ts-retrain`**: when `ts-monitor` says `retrain_now`,
  re-run Layers 1-2 on the updated series and deterministically decide
  whether the freshly backtested candidate beats what's currently
  deployed by enough to be worth redeploying. Never redeploys on its
  own -- it stops for human confirmation.

## Project layout

```
omen/
├── pyproject.toml
├── LICENSE
├── README.md
├── AGENTS.md
├── .gitignore
├── openclaw.config.snippet.jsonc
├── src/
│   └── omen/
│       ├── __init__.py            # version + skills_dir() helper
│       ├── data_prep.py           # shared: synthetic data + CSV loader (used by all 5 layers)
│       ├── analyst/
│       │   ├── __init__.py
│       │   ├── analysis_tools.py  # Layer 1 diagnostic functions
│       │   └── server.py          # FastMCP server: ts-analyst
│       ├── forecaster/
│       │   ├── __init__.py
│       │   ├── model_tools.py     # Layer 2 fit/backtest functions
│       │   └── server.py          # FastMCP server: ts-forecaster
│       ├── deploy/
│       │   ├── __init__.py
│       │   ├── forecast_tools.py  # Layer 3 retrain/forecast functions
│       │   └── server.py          # FastMCP server: ts-deploy
│       ├── monitor/
│       │   ├── __init__.py
│       │   ├── monitor_tools.py   # Layer 4 comparison/drift/retrain-decision functions
│       │   └── server.py          # FastMCP server: ts-monitor
│       ├── retrain/
│       │   ├── __init__.py
│       │   ├── retrain_tools.py   # Layer 5 deployment-manifest + redeploy-decision functions
│       │   └── server.py          # FastMCP server: ts-retrain
│       └── skills/                # bundled as package data -- see skills_dir()
│           ├── ts-analyst/SKILL.md
│           ├── ts-forecaster/SKILL.md
│           ├── ts-deploy/SKILL.md
│           ├── ts-monitor/SKILL.md
│           └── ts-retrain/SKILL.md
├── tests/
│   ├── test_data_prep.py
│   ├── test_analyst_tools.py
│   ├── test_forecaster_tools.py
│   ├── test_deploy_tools.py
│   ├── test_monitor_tools.py
│   └── test_retrain_tools.py
└── blog-posts/                    # draft write-ups about this project, not part of the package
    ├── introducing-omen.md
    ├── ts-analyst-gets-a-statistics-degree.md
    └── ts-forecaster-shows-its-work.md
```

## What changed from the earlier ad-hoc layout

- **One `data_prep.py`, not four copies.** Every layer previously had its
  own duplicate for self-containment as a standalone MCP server folder;
  now they all import `omen.data_prep`.
- **Real packaging metadata.** `pyproject.toml` declares dependencies,
  optional extras per layer, and console-script entry points
  (`ts-analyst-server`, `ts-forecaster-server`, `ts-deploy-server`,
  `ts-monitor-server`) so OpenClaw's config can reference an installed
  command instead of an absolute path to a `.py` file.
- **Skills are bundled package data.** `omen.skills_dir()`
  returns the installed path to the four `SKILL.md` files, so you can
  install this package and copy the skills into an OpenClaw workspace
  without needing the original source tree around.
- **A real test suite**, using `pytest.importorskip` for the tests that
  need `statsmodels`/`scikit-learn`, so `pip install -e .` (core deps
  only) still lets you run the tests that don't need them.

## Setup

### 1. Install
```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -e ".[all]"       # every layer's dependencies
# or install only what you need:
#   pip install -e ".[analyst]"                 # Layer 1 only
#   pip install -e ".[forecaster,deploy]"       # Layers 2+3
#   pip install -e ".[monitor]"                 # Layer 4 only
#   pip install -e ".[retrain]"                 # Layer 5 only (no extra deps beyond core)
#   pip install -e ".[dev]"                     # + pytest, for running tests
```

### 2. Run the test suite
```bash
pip install -e ".[all,dev]"
pytest
```

### 3. Sanity-check each server runs standalone
```bash
ts-analyst-server      # Ctrl+C to stop; no output/crash = good
ts-forecaster-server
ts-deploy-server
ts-monitor-server
ts-retrain-server
```

### 4. Register with OpenClaw
Merge `openclaw.config.snippet.jsonc` into `~/.openclaw/openclaw.json` --
no path editing needed if the console scripts are on `PATH` (true inside
the venv you installed into). Then:
```bash
openclaw mcp status --verbose
openclaw mcp doctor --probe
openclaw mcp tools ts-analyst
```

### 5. Install the bundled skills
```bash
mkdir -p ~/.openclaw/workspace/skills
cp -r "$(python -c 'import omen as t; print(t.skills_dir())')"/* \
    ~/.openclaw/workspace/skills/
```
Start a new OpenClaw session afterward (skills are snapshotted at session
start).

### 6. Point OpenClaw at your model of choice
This project was developed against GLM-5.2 on Ollama Cloud:
```bash
export OLLAMA_API_KEY="<your-ollama-cloud-api-key>"
openclaw models list --provider ollama-cloud
openclaw models set ollama-cloud/glm-5.2:cloud
```
Nothing about the package is tied to that specific model -- swap
`agents.defaults.model.primary` in the config for whatever you're running.

## Run it

Full pipeline, one message to your OpenClaw agent:

> Use ts-analyst to explore a synthetic time series, then use
> ts-forecaster to fit and backtest candidate models informed by what you
> found, then use ts-deploy to produce a 30-day forecast with the
> best-performing model and settings.

Once time has passed and the CSV has real new observations:

> Use ts-monitor to check whether that forecast is holding up against
> what actually happened, and tell me if I should retrain.

Right after that first real `ts-deploy` call, record what got deployed so
Layer 5 has a baseline to compare against later:

> Use ts-retrain to record that this model and its backtest metrics are
> now deployed.

If `ts-monitor` comes back with `retrain_now`:

> Use ts-retrain to re-run analyst and forecaster on the updated series
> and tell me whether the new candidate is actually worth redeploying.

That call stops at the verdict -- `ts-retrain` never redeploys on its own
in the default mode. If the verdict says `should_redeploy: true` and you
want to proceed, confirm it explicitly in a follow-up message:

> Go ahead and redeploy the candidate you just recommended.

which is what actually triggers `ts-retrain__execute_redeploy(...,
confirmed=True)` and updates the manifest.

If you'd rather not be asked each time for a specific series, opt into
autonomous mode explicitly -- e.g. as a standing instruction in this
project's own `AGENTS.md`, or stated up front in the conversation:

> For the `daily_demand.csv` series specifically, you're authorized to
> redeploy automatically whenever ts-retrain finds a candidate that beats
> the current deployment -- no need to ask me first. Everything else
> still needs my confirmation as usual.

With that authorization in place, a later `retrain_now` cycle for that
series will call `execute_redeploy(confirmed=True)` itself once
`should_redeploy: true` comes back, and report what it did rather than
pausing to ask.

## Publishing this to PyPI

This layout is ready for it as-is:
```bash
pip install build twine
python -m build                      # produces dist/*.whl and dist/*.tar.gz
twine upload --repository testpypi dist/*    # try TestPyPI first
twine upload dist/*                          # then the real thing
```
Before actually publishing, you'll want to:
- confirm `omen` is actually free on PyPI -- it's a short, generic word,
  so don't assume it isn't already claimed; PyPI names are first-come and
  effectively permanent once taken
- fill in real author info in `pyproject.toml` (still says
  `"Your Name" <you@example.com>`)
- bump `version` for each release

## Things worth knowing about specific tools (carried over from earlier layers)

- **`ts-analyst__check_stationarity` runs both ADF and KPSS and combines
  them into one joint verdict, each with its own effect size AND
  confidence interval.** ADF's null is a unit root; KPSS's null is
  stationarity -- opposite nulls, so running both and reading
  `interpretation`'s four-way readout (agree stationary / agree
  non-stationary / disagree in either direction) is standard practice,
  not redundant. `adf_p_value`/`adf_is_likely_stationary` come with a
  mean-reversion effect size (`mean_reversion_lambda`,
  `mean_reversion_half_life_periods`) and its confidence interval
  (`mean_reversion_lambda_ci_lower/upper`,
  `mean_reversion_half_life_ci_lower/upper`) -- a series can clear
  `p < 0.05` while reverting so slowly the half-life is impractically
  long for a short-horizon forecast, so check both, not just the
  p-value; the CI additionally shows how precisely that half-life is
  actually known. `mean_reversion_half_life_ci_upper` is `null`
  (unbounded) whenever lambda's own CI reaches non-negative territory --
  the data can't rule out arbitrarily slow reversion at that end. Don't
  read a small positive (or slightly negative-but-near-zero)
  `mean_reversion_lambda` as proof of "no reversion" on its own -- under a
  true unit root, this OLS estimate is known to skew slightly negative in
  finite samples; `adf_is_likely_stationary` and the half-life's magnitude
  are the more reliable signals. `kpss_p_value`/`kpss_is_likely_stationary`
  come with `kpss_effect_size` (the statistic as a multiple of its 5%
  critical value) -- KPSS's own p-value is clipped at lookup-table
  boundaries, so the effect size is what actually distinguishes a
  borderline result from a wildly non-stationary one once the p-value is
  pinned at 0.01 or 0.10. Note the field names changed from the tool's
  original single-test version (`p_value`/`is_likely_stationary` are now
  `adf_p_value`/`adf_is_likely_stationary`).
- **`ts-analyst__basic_stats` reports a confidence interval for the mean**
  (`mean_ci_lower`, `mean_ci_upper`, Student's t, default 95% via
  `confidence_level`) -- both are `null` for a constant series (zero
  variance, no interval to report).
- **`ts-analyst__acf_pacf_summary` and `ts-analyst__detect_anomalies_zscore`
  both report an effect size for anything they flag, not just a bare
  pass/fail.** `acf_pacf_summary` now uses statsmodels' Bartlett-formula
  PER-LAG confidence intervals to decide significance, not a single
  global threshold -- the correct standard error for ACF grows with lag
  (it depends on the cumulative autocorrelation of earlier lags), so a
  uniform `1.96/sqrt(n)` threshold (an earlier version of this tool) is
  only actually correct at lag 1 and understates the true threshold at
  later lags. `significant_acf_lags` is a list of
  `{lag, acf, ci_lower, ci_upper, effect_size}` entries (`effect_size` =
  ACF magnitude as a multiple of that lag's OWN interval half-width),
  sorted strongest first and capped at 10 -- on the project's synthetic
  data, this correctly ranks lag 1 as the single strongest entry (its
  Bartlett SE is the tightest, with no prior lags inflating it), where
  the old uniform-threshold version incorrectly ranked lag 7 first.
  `detect_anomalies_zscore`'s `anomalies` is a list of
  `{date, value, z_score}` entries, sorted most extreme first and capped
  at 15, plus a `max_abs_z_score` summary. Both fields changed shape from
  earlier versions -- `significant_acf_lags` was a bare list of lag
  integers (with a single `significance_threshold`, now
  `significance_alpha`), and `detect_anomalies_zscore` returned
  `anomaly_dates` (date strings only, no magnitude) instead of
  `anomalies`.
- **`ts-analyst__detect_seasonality_period` finds a candidate seasonal
  period FOR you** (via periodogram + Fisher's g-test), rather than
  requiring you to already know one before calling
  `seasonal_decomposition_summary` or `acf_pacf_summary`. The
  significance test applies to the single globally strongest frequency in
  the FULL periodogram, which can correspond to a period outside the
  reported `[min_period, max_period]` range (commonly the series' own
  trend, at a period near its full length) -- always check
  `dominant_period_in_reported_range` before treating the significance
  test as endorsing one of `top_candidate_periods` specifically. The
  p-value uses the standard conservative upper-bound approximation for
  Fisher's g-test, not the full alternating-series formula.
- **`ts-analyst__detect_anomalies_robust_zscore` exists because the
  original `detect_anomalies_zscore` has a real, confirmed weakness**:
  its rolling window's own std is inflated by the very anomaly it's
  trying to measure (a +500 spike on a ~200-scale series only scored
  z=3.44, not something far higher). The robust version uses a rolling
  median + MAD (modified z-score, Iglewicz & Hoya 1993) instead, which
  isn't self-diluted the same way -- confirmed on the same spike, it
  scores 17.26. Default `z_threshold` is 3.5, not 3.0 (the
  literature-recommended default for the modified z-score specifically).
  Neither tool replaces the other -- reach for the robust version when
  you suspect self-dilution might be masking a real anomaly.
- **`ts-analyst__detect_changepoints` flags a lasting shift in the
  series' MEAN LEVEL, not a point anomaly** -- a different job from
  either `detect_anomalies_zscore` variant above. Uses binary
  segmentation with a CUSUM statistic and a permutation test (deterministic
  given the same `seed`, default 42). Each changepoint reports Cohen's d
  as an effect size. **Known limitation, not a bug**: binary
  segmentation's per-split p-values are local tests within whatever
  segment existed at that point in the recursion -- there's no exact
  global significance guarantee for the full set of changepoints
  reported. This is a standard, accepted tradeoff for this class of
  algorithm; treat `alpha`/`max_changepoints` as tuning knobs, not as
  controlling an exact false-discovery rate.
- **Every `ts-forecaster` `fit_*` tool's `backtest_metrics` now includes a
  bootstrap confidence interval** (`mae_ci_lower/upper`, etc., percentile
  method, deterministic given `seed`, default 1000 resamples) -- a
  backtest metric computed over a modest `holdout_size` (often ~30
  points) has real sampling uncertainty of its own; two models scoring
  MAPE 4.8% and 5.0% might not be a meaningfully different result once
  you see how wide each one's own interval is. Each result also now
  includes `holdout_actuals`/`holdout_predicted` arrays, and
  `residual_diagnostics` (ETS/SARIMA) reports `ljung_box_effect_size`
  (the Q statistic as a multiple of its own critical value) alongside
  the p-value.
- **`ts-forecaster__diebold_mariano_test` gives model comparison actual
  statistical backing.** Previously "compare candidates honestly" meant
  eyeballing two error numbers with no way to tell a real difference from
  holdout noise. This runs a Diebold-Mariano-style test (1995) on two
  models' paired forecast errors from the SAME holdout (pass
  `holdout_actuals` and each model's `holdout_predicted`), using a
  Newey-West/Bartlett-kernel HAC-robust variance estimate (automatic lag
  selection by default) and a Student's t reference distribution for
  small-sample conservatism. Returns `is_significant_difference` and
  `favored_model` (`null` if not significant). Pass `n_lags=0` when
  comparing two one-step-ahead backtests specifically (e.g. two
  `fit_gradient_boosted_trees` runs) -- the default automatic lag
  selection assumes genuinely multi-step, autocorrelated forecast errors.
  This test tells you whether two models' error numbers differ
  significantly; it does NOT resolve the one-step-ahead-vs-recursive
  evaluation mismatch below when comparing across that boundary.
- **`fit_ets`/`fit_sarima` now also report `aicc`** (small-sample-corrected
  AIC, Hurvich & Tsai 1989 -- `None` when the training size is too small
  relative to the parameter count for the correction to make sense)
  **and `backtest_interval_coverage`** -- a prediction interval built
  during the backtest (simulated for ETS, analytic for SARIMA) checked
  against the REAL holdout values, using the exact same coverage-check
  shape/logic (and 15-percentage-point `well_calibrated` threshold) as
  `ts-monitor__compare_forecast_to_actuals`. This catches a badly
  calibrated interval during backtesting, before it's ever deployed,
  instead of waiting for `ts-monitor` to notice after the fact.
- **`ts-forecaster__rolling_origin_backtest` addresses a real limitation
  every other tool in this layer still has**: every `fit_*` call
  evaluates against a single, arbitrarily-chosen fixed holdout window --
  even the bootstrap CI above only resamples points *within* that one
  window, so a single unlucky/lucky holdout period still biases
  everything computed from it. This repeats `fit_ets`/`fit_sarima`/
  `fit_gradient_boosted_trees` (not `fit_naive_baselines` -- naive
  baselines don't need walk-forward rigor) at multiple non-overlapping
  origins with an expanding training window, and reports the mean/std of
  backtest MAE/RMSE/MAPE across origins -- a large std relative to the
  mean is a genuine, direct measure that a model's apparent edge isn't
  stable across different stretches of the series. Costs `n_origins`
  times a single fit, since each origin genuinely refits the model.
- **`ts-forecaster__search_sarima_orders` is an advisory grid search, not
  an authority.** It searches `(p,q)(P,Q)` combinations (with `d`/
  `seasonal_d` held fixed -- pass them explicitly, informed by
  `ts-analyst`'s stationarity findings, not searched) ranked by AICc,
  reusing `fit_sarima` for every candidate so the fitting logic isn't
  duplicated. This is deliberately scoped to not replace the project's
  existing "the agent reasons about settings from Layer 1 findings"
  design (see `ts-forecaster/SKILL.md`) -- verified directly on the
  project's own synthetic data that the numerically-best-AICc candidate
  can still have `residuals_look_like_white_noise: false`, i.e. a
  candidate this search ranks first can still be a worse choice by other
  criteria the agent needs to check regardless. Bounded by
  `max_combinations` (default 60) to avoid runaway compute.
- **`ts-forecaster`'s gradient-boosted-trees backtest is one-step-ahead**
  (uses true lagged values), while ETS/SARIMA get scored on a genuine
  multi-step forecast -- not directly comparable without accounting for that.
- **`ts-deploy__forecast_naive` now has an analytic prediction interval
  too** -- previously the only `forecast_*` tool with zero interval
  capability, ever. Built from this same naive method's own in-sample
  residual standard deviation (one-step differences for flat naive,
  seasonal differences for seasonal naive) and widening with
  `sqrt(elapsed steps/cycles)` -- the standard textbook interval for a
  random-walk-style forecast (Hyndman & Athanasopoulos), not simulation-
  based. Falls back to point-forecast-only (see `interval_note`) if
  there's fewer than 2 residuals to estimate a standard deviation from
  (i.e. a 2-row series or shorter for flat naive). As a side effect,
  `forecast_ensemble` combinations that include `"naive"` can now get a
  combined interval too, where before they never could.
- **`ts-deploy`'s gradient-boosted-trees forecast is recursive** (each
  prediction feeds back in as a lag for the next step), so errors can
  compound over a long horizon -- a risk that didn't apply to Layer 2's
  evaluation of the same model type. **It now also has a prediction
  interval**, via two extra `GradientBoostingRegressor` models trained
  with `loss="quantile"` alongside the point model -- an approximate
  interval that does NOT itself grow with the recursive compounding risk
  above, unlike SARIMA's analytic interval or ETS's simulated one
  (`interval_note`/`caveat` both say so explicitly). Recursive lag
  features always follow the POINT model's own trajectory, never the
  quantile models' -- one consistent path instead of three diverging
  ones. Independently-fit quantile models can cross (`lower > upper`);
  guarded against with an elementwise min/max before returning.
- **Every `ts-deploy__forecast_*` tool (including `forecast_ensemble`)
  returns a `plausibility_check` field** that automates part of the
  "does this look plausible" eyeball check `ts-deploy/SKILL.md` Step 3
  otherwise leaves entirely to the agent. It compares the forecast's
  implied endpoint change against the empirical distribution of
  horizon-length changes the series has actually made historically
  (`endpoint_change_z_score`, `endpoint_change_percentile_rank`,
  `is_extreme_relative_to_history`), and separately flags
  `goes_below_historical_min`/`goes_above_historical_max`. This is NOT a
  hypothesis test and not a verdict -- there's no null distribution being
  tested, only "has the series done something like this before"; a
  genuine regime change can legitimately produce a flagged forecast
  that's still correct. `null` fields when there's not enough history
  (`n <= horizon`) to compute the comparison at all.
- **`ts-deploy__forecast_ensemble` combines two or more candidates into
  one weighted forecast** -- the tool for "what do I actually deploy" when
  Layer 2 leaves more than one reasonable candidate, filling the gap the
  `ts-forecaster` blog post flagged as a Next Step (combining candidates
  is this layer's job, evaluating them individually is Layer 2's).
  `weights` default to equal, needn't be pre-normalized (raw inverse-MAE
  values from a Layer 2 comparison work directly), and the combined point
  forecast is a straightforward weighted average at each date. The
  combined interval, reported only when EVERY included model contributes
  one of its own, is a weighted average of interval BOUNDS -- an honest
  but naive combination that doesn't account for correlation between the
  component models' errors, unlike a properly derived ensemble interval;
  `interval_note` says so. Including `"gbt"` carries its recursive-
  compounding caveat into the combined result too (diluted by weight, not
  eliminated).
- **`ts-monitor`'s drift detector can't distinguish trend/seasonality from
  a genuine regime change** -- confirmed directly: running it on this
  project's synthetic data (which has a real upward trend) flags
  `drift_detected=True` even with no injected anomaly, purely from trend
  continuation. Read the `interpretation` field rather than treating the
  boolean as an automatic alarm.
- **`ts-monitor__recommend_retraining` is deliberately deterministic
  rather than left to model judgment** -- "should we retrain" is the kind
  of decision worth being reproducible given the same inputs.
- **`ts-retrain` only ever changes the deployment through one gated tool,
  `ts-retrain__execute_redeploy`** -- it re-runs Layers 1-2, hands the
  resulting candidate to `ts-retrain__compare_candidate_to_deployed`
  (deterministic, same reason as `recommend_retraining` above), and
  `execute_redeploy` itself refuses to do anything unless called with
  `confirmed=True`. There is no default that takes action.
- **`ts-retrain` supports two ways of reaching that confirmation**: the
  default is a human explicitly approving the redeploy in conversation.
  An *optional autonomous mode* exists for when a human or a standing
  project instruction has explicitly pre-authorized unattended retraining
  for a specific series -- in that mode, the skill calls
  `execute_redeploy(confirmed=True)` itself the moment
  `should_redeploy: true` comes back, with no pause. Autonomous mode is
  never assumed; the skill's own instructions tell it to fall back to
  human-confirmed mode whenever authorization is ambiguous.
- **`ts-retrain`'s deployment manifest is the only piece of durable state
  in the whole toolkit** -- a JSON file (`deployment_manifest.json` by
  default, written next to the series CSV) recording what model/params/
  backtest metrics are currently deployed. Nothing else persists between
  calls; every other tool is a pure function of its inputs.
- **`execute_redeploy` requires the `deploy` extra installed** (it
  delegates to `omen.deploy.forecast_tools`), regardless of
  which `model_type` is requested, since it imports that module as a
  whole. `ts-retrain`'s diagnostic tools (`load_deployment_manifest`,
  `compare_candidate_to_deployed`, `record_deployment`) have no such
  requirement.

## Next steps

Layer 5's optional autonomous mode (see above) is now built: `ts-retrain`
can either pause for human confirmation before redeploying, or -- given
explicit, unambiguous authorization for a specific series -- call
`execute_redeploy(confirmed=True)` itself the moment
`should_redeploy: true` comes back. The confirmation gate itself
(`execute_redeploy` refusing to act without `confirmed=True`) is
mechanical and tested; the *authorization* decision for autonomous mode
is still a prose contract enforced by the skill's own judgment, not a
config flag the code checks. A natural follow-up here would be making
that authorization inspectable/auditable outside the conversation itself
-- e.g. a small opt-in record (which series, since when, by whom) stored
next to the deployment manifest, so "is autonomous mode on for this
series" doesn't depend solely on what the agent remembers being told.
