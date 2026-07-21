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
  the deployed forecast is still tracking reality (now with a bootstrap
  confidence interval on its error metrics), detect data drift (now with
  an effect size, not just a bare p-value), and recommend whether to
  retrain -- flagging when that recommendation is itself close to the
  threshold rather than clear-cut.
- **Layer 5 — `ts-retrain`**: when `ts-monitor` says `retrain_now`,
  re-run Layers 1-2 on the updated series and deterministically decide
  whether the freshly backtested candidate beats what's currently
  deployed by enough to be worth redeploying (now confidence-interval-
  aware on both sides of that comparison, not just bare point estimates).
  Never redeploys without an explicit `confirmed=True` -- by default that
  means stopping for human confirmation, and the optional autonomous-mode
  alternative is now backed by a real, code-checked authorization record
  rather than only a prose contract.

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

That grant is what the agent should turn into a persisted record via
`ts-retrain__authorize_autonomous_mode(csv_path="daily_demand.csv",
authorized_by="user, in conversation")` -- not just remember for the rest
of the session. With that record in place, a later `retrain_now` cycle
for that series will call `execute_redeploy(confirmed=True,
autonomous=True)` itself once `should_redeploy: true` comes back (which
itself re-checks the record before acting), and report what it did rather
than pausing to ask.

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
  **`feature_importances` now includes a bootstrap confidence interval per
  feature** (`{col: {importance, ci_lower, ci_upper}}` -- a shape change,
  not just an added field). Refits the point model on `n_bootstrap`
  (default 100) resamples of the TRAINING ROWS, not resampled errors --
  there's no "error" to resample for a feature-importance question, only
  what the model was fit on. Real extra cost: `n_bootstrap` full model
  refits on top of the three already needed for the forecast/interval.
  Confirmed on the project's own synthetic data that this CI is
  informative, not decorative: `lag_7` (the real weekly seasonality)
  showed `importance=0.593` but `ci_lower=0.26, ci_upper=0.77` -- a
  genuinely wide range, since `lag_7` and `lag_14` compete for
  "explaining" the same weekly pattern and which one wins varies by
  resample. `n_bootstrap=0` skips this cheaply (`ci_lower`/`ci_upper`
  come back `null`) -- `forecast_ensemble`'s internal GBT fit always uses
  this, since ensemble results never surface `feature_importances` at all.
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
  forecast is a straightforward weighted average at each date. **The
  combined interval, reported only when EVERY included model contributes
  one of its own, is a VARIANCE combination, not a bound average**: each
  component's own interval width is converted to an implied standard
  deviation, combined via `sqrt(sum(w_i^2 * sigma_i^2))` assuming the
  components' errors are INDEPENDENT, then rebuilt around the weighted
  point forecast. More principled than literally averaging bounds -- but
  the independence assumption is optimistic (every component is fit on
  the SAME series and shares real error structure), so `interval_note`
  frames the result as a lower bound on the ensemble's true uncertainty,
  not a precise one. Confirmed on the project's own synthetic data: two
  identical naive components at equal weight (0.5/0.5) combine to a
  95% interval exactly `1/sqrt(2)` (≈0.707x) the width of either
  component's own interval alone -- narrower than any single component,
  which is the expected mathematical effect of combining independent
  estimates, not a bug. Including `"gbt"` carries its recursive-
  compounding caveat into the combined result too (diluted by weight, not
  eliminated).
- **`ts-monitor`'s drift detector can't distinguish trend/seasonality from
  a genuine regime change** -- confirmed directly: running it on this
  project's synthetic data (which has a real upward trend) flags
  `drift_detected=True` even with no injected anomaly, purely from trend
  continuation. Read the `interpretation` field rather than treating the
  boolean as an automatic alarm. **It now reports a magnitude alongside
  that boolean, not just a bare p-value**: `mean_shift_cohens_d` (pooled-
  SD effect size for the mean shift) plus the raw `ttest_statistic`/
  `ks_statistic` the two tests are actually built on -- previously
  computed internally and silently dropped before returning, a real
  oversight fixed alongside the effect-size addition. Confirmed on the
  project's own trending synthetic data: the unmodified series' trend-
  driven "drift" comes back with `mean_shift_cohens_d≈-0.42`, while
  injecting an obvious +200 level shift on top of it pushes that to
  `≈7.06` -- both flagged `drift_detected=True`, but only the effect size
  tells you which one is a trend continuation and which one is a wall.
- **`ts-monitor__rolling_drift_check` addresses the same "one arbitrary
  window" fragility `ts-forecaster__rolling_origin_backtest` fixed for
  backtesting, applied to drift detection.** A single `detect_data_drift`
  call only compares one recent window against one reference window --
  it can't tell you whether a flagged shift is a sustained pattern or an
  isolated blip. This repeats the check at `n_checks` (default 5)
  non-overlapping points walking backward through the series and reports
  `persistent_drift: true` when at least `persistence_threshold_frac`
  (default 50%) of them flag drift. Unlike `rolling_origin_backtest`,
  this is cheap per check (a t-test and KS test on numpy arrays, no model
  fitting), so a larger `n_checks` costs little. Confirmed on the
  project's own trending synthetic data: all 5 rolling checks flag drift
  (`frac_flagged=1.0`), correctly identifying the ongoing trend as a
  sustained pattern rather than a one-off blip -- consistent with
  `detect_data_drift`'s own documented false-positive-on-trend caveat.
- **`ts-monitor__compare_forecast_to_actuals`'s `backtest_style_metrics`
  now includes a bootstrap confidence interval** (`mae_ci_lower/upper`,
  etc., same percentile-bootstrap technique and field names as
  `ts-forecaster`'s backtest metrics) -- a comparison drawn from just a
  handful of elapsed forecast dates has real sampling uncertainty of its
  own, arguably more consequential here than in a Layer 2 backtest since
  it's about real post-deployment performance, not a held-out window.
- **`interval_coverage` now also reports a Wilson score confidence
  interval on the coverage percentage itself** (`empirical_coverage_ci_lower/upper`)
  -- coverage is a proportion computed from however many dates have
  elapsed so far, often a small handful, so "100% coverage" from 10
  points is far less reassuring than it sounds. Confirmed directly: 10/10
  matched points inside their interval gives `empirical_coverage_pct=100.0`
  but a Wilson CI of `[72.25%, 100.0%]` -- genuinely wide. This is
  supplementary information only and deliberately does NOT change
  `well_calibrated`'s existing 15-percentage-point threshold verdict,
  which stays intentionally identical to `ts-forecaster`'s mirrored
  `backtest_interval_coverage` check (see `AGENTS.md`).
- **`compare_forecast_to_actuals` now flags residual outliers** among the
  matched-point comparisons, using the same modified-z-score (MAD-based)
  technique as `ts-analyst__detect_anomalies_robust_zscore`, and reports
  `metrics_excluding_outliers` -- letting the caller distinguish "the
  forecast missed by a little every day" from "the forecast was fine
  except for one wild day (a promotion, an outage)," which call for
  different responses when deciding whether the MODEL itself needs
  retraining. **Known limitation, not a bug**: if half or more of the
  residuals are exactly identical (most realistically exactly 0), the
  MAD degenerates to 0 and every z-score collapses to 0, potentially
  masking a genuine outlier -- the same self-dilution failure class
  `ts-analyst`'s original (non-robust) anomaly detector had, just
  triggered by a rarer condition.
- **`ts-monitor__recommend_retraining` is deliberately deterministic
  rather than left to model judgment** -- "should we retrain" is the kind
  of decision worth being reproducible given the same inputs. It can
  now optionally accept `mape_now_ci_lower`/`mape_now_ci_upper` (from the
  bootstrap CI above) and will report `pct_degradation_ci_lower/upper`
  plus flag `degradation_threshold_within_ci: true` when the degradation
  threshold itself falls inside that range -- i.e. the degraded/
  not-degraded verdict is sensitive to sampling noise in `mape_now`, not
  a clean call, and the tool says so in `reasoning` rather than reporting
  a falsely confident point-estimate verdict.
- **`ts-retrain` only ever changes the deployment through one gated tool,
  `ts-retrain__execute_redeploy`** -- it re-runs Layers 1-2, hands the
  resulting candidate to `ts-retrain__compare_candidate_to_deployed`
  (deterministic, same reason as `recommend_retraining` above), and
  `execute_redeploy` itself refuses to do anything unless called with
  `confirmed=True`. There is no default that takes action.
- **`ts-retrain__compare_candidate_to_deployed` now uses confidence-interval
  data it was already being handed but previously ignored.** The full
  `backtest_metrics` dicts passed in as `candidate_metrics`/`deployed_metrics`
  already carry a bootstrap CI for the compared metric (from
  `ts-forecaster`'s `compute_metrics_with_ci`) whenever the candidate came
  from a recent `fit_*` call -- the function just wasn't reading it. It now
  reports `pct_improvement_ci_lower/upper` (the implied improvement range)
  and flags `redeploy_threshold_within_ci: true` when
  `improvement_threshold_pct` falls inside that range -- meaning
  `should_redeploy` is close to a coin flip on backtest sampling noise.
  **If `deployed_metrics` also carries a CI, its uncertainty gets combined
  in too** (`deployed_metrics_ci_used: true`), via proper interval
  arithmetic over both ranges at once rather than a "one side treated as
  fixed" simplification -- confirmed directly: candidate MAPE 6.0% (CI
  `[5.0, 7.0]`) against deployed MAPE 10.0% alone implies `[30.0%, 50.0%]`;
  adding a deployed-side CI of `[9.0, 11.0]` widens that to `[22.22%,
  54.55%]`, exactly as worst-case/best-case reasoning over both ranges
  predicts (worst case: candidate at its highest paired with deployed at
  its lowest; best case: the reverse). Falls back to the old
  fixed-deployed-value behavior automatically whenever `deployed_metrics`
  has no CI for the metric (`deployed_metrics_ci_used: false`) -- e.g. an
  older manifest recorded before this session's CI work.
- **`ts-retrain__execute_redeploy` now returns `previous_deployment`** --
  whatever the manifest held immediately before this call overwrote it (or
  `null` on a genuinely first deployment), read before the write happens
  rather than reconstructed afterward. The manifest file itself is
  unchanged and still only ever holds the single current deployment, not a
  history -- this is a one-time snapshot in the ACTION'S OWN output, so
  "what did this redeploy actually replace" is answerable straight from the
  tool call instead of requiring a trawl back through conversation history.
- **`ts-retrain` supports two ways of reaching that confirmation**: the
  default is a human explicitly approving the redeploy in conversation.
  An *optional autonomous mode* exists for when a human or a standing
  project instruction has explicitly pre-authorized unattended retraining
  for a specific series -- in that mode, the skill calls
  `execute_redeploy(confirmed=True, autonomous=True)` itself the moment
  `should_redeploy: true` comes back, with no pause. Autonomous mode is
  never assumed; the skill's own instructions tell it to fall back to
  human-confirmed mode whenever authorization is ambiguous. **This is no
  longer purely a prose contract** -- `autonomous=True` triggers a real
  code-level check (`check_autonomous_mode`) against a standing
  authorization record, and `execute_redeploy` refuses to act, even with
  `confirmed=True`, if no such record exists for the series. See the next
  bullet.
- **`ts-retrain__authorize_autonomous_mode` (with `revoke_autonomous_mode`/
  `check_autonomous_mode`) makes autonomous-mode authorization
  inspectable, not just conversational** -- closing a gap this project's
  own introductory post flagged as unfinished business. Previously,
  "is autonomous mode on for this series" lived entirely in the agent's
  memory of a conversation; now it's a small persisted JSON record
  (`autonomous_mode.json` by default, next to the series CSV -- a
  *separate* file from the deployment manifest, since authorization and
  deployment are different concerns with different lifecycles) holding
  `authorized`, `authorized_at`, `authorized_by`, and an optional `note`.
  `authorize_autonomous_mode` performs no judgment of its own about
  whether granting it is appropriate -- it only persists a decision
  that's already been made by a human or a standing project instruction,
  the same way `record_deployment` persists a deployment decision rather
  than making one.
- **`ts-retrain` now has TWO pieces of durable state, not one** -- the
  deployment manifest (`deployment_manifest.json`) and the new
  autonomous-mode authorization record (`autonomous_mode.json`), both
  written next to the series CSV. Everything else in the whole toolkit
  remains a pure function of its explicit inputs.
- **`execute_redeploy` requires the `deploy` extra installed** (it
  delegates to `omen.deploy.forecast_tools`), regardless of
  which `model_type` is requested, since it imports that module as a
  whole. `ts-retrain`'s diagnostic and record-keeping tools
  (`load_deployment_manifest`, `compare_candidate_to_deployed`,
  `record_deployment`, `authorize_autonomous_mode`, `revoke_autonomous_mode`,
  `check_autonomous_mode`) have no such requirement -- all plain
  `json`/`os`/`datetime`, nothing beyond core.

## Next steps

Layer 5's optional autonomous mode (see above) is fully built: `ts-retrain`
can either pause for human confirmation before redeploying, or -- given
explicit, unambiguous authorization for a specific series -- call
`execute_redeploy(confirmed=True, autonomous=True)` itself the moment
`should_redeploy: true` comes back. Both the confirmation gate
(`execute_redeploy` refusing to act without `confirmed=True`) AND the
autonomous-mode authorization check (`execute_redeploy` refusing
`autonomous=True` without a standing `check_autonomous_mode` record) are
now mechanical and tested, not just prose contracts the skill is trusted
to follow correctly. This closes the gap flagged as unfinished business
in this project's introductory post -- "is autonomous mode on for this
series" no longer depends solely on what the agent remembers being told;
`authorize_autonomous_mode`/`revoke_autonomous_mode`/`check_autonomous_mode`
make it a small, inspectable, persisted record instead.
