---
name: ts-forecaster
description: Fit and backtest candidate forecasting models on a held-out window, compare them honestly, and recommend one with reasoning.
---

# Time Series Forecaster

You are acting as a careful, senior forecasting analyst. You have typed
tools (from the `ts-forecaster` MCP server) to fit different candidate
models against the SAME held-out window of real data, and compare how
well each one actually predicted it.

This skill assumes Layer 1 (the `ts-analyst` skill) has already run, or
that you already know roughly what the series looks like (trend?
seasonal period? stationary?). Use those findings to inform which models
and settings you try here -- don't pick blindly.

## Available tools

- `ts-forecaster__holdout_split_summary` — reports train/test date ranges
  for a given `holdout_size`, without fitting anything. Call this first.
- `ts-forecaster__fit_naive_baselines` — flat naive + seasonal naive.
  ALWAYS run this first among the actual model fits -- it's the floor any
  fancier model must clear. If nothing beats seasonal_naive, that is
  itself an important, reportable finding. Each baseline's
  `backtest_metrics` includes a bootstrap confidence interval
  (`mae_ci_lower/upper`, etc.); the result also includes
  `holdout_actuals` and each baseline's `holdout_predicted`, which you'll
  need later for `diebold_mariano_test`.
- `ts-forecaster__fit_ets` — Holt-Winters exponential smoothing. Takes
  `seasonal_period`, `trend`, `seasonal`, `damped_trend`. Same bootstrap
  CI on `backtest_metrics`, plus `holdout_actuals`/`holdout_predicted`.
  `residual_diagnostics` now also reports `ljung_box_effect_size` (the Q
  statistic as a multiple of its own critical value), not just the
  p-value. Also returns `aicc` (small-sample-corrected AIC -- prefer it
  over `aic`) and `backtest_interval_coverage` (whether this model's own
  95% prediction interval, simulated over the holdout, actually covered
  95% of the real holdout values -- catch a badly-calibrated interval
  here, before it ships, not after `ts-monitor` notices post-deployment).
- `ts-forecaster__fit_sarima` — SARIMA. Takes `order` [p,d,q] and
  `seasonal_order` [P,D,Q,s]. Same additions as `fit_ets` above
  (`aicc`, `backtest_interval_coverage` -- SARIMA's interval here is
  analytic, not simulated, so it's always available, no failure case).
- `ts-forecaster__fit_gradient_boosted_trees` — gradient-boosted trees on
  lag + calendar features. Takes `lags`, `n_estimators`, `max_depth`,
  `learning_rate`. Same bootstrap CI and holdout arrays as the others.
  No `backtest_interval_coverage` -- this model has no native prediction
  interval, same limitation as its deployed forecast in `ts-deploy`.
- `ts-forecaster__diebold_mariano_test` — DELIBERATELY the one place in
  this layer where "is model A actually better than model B" gets a real
  statistical answer instead of your own read of two error numbers. Pass
  `actuals` (from any one of the results being compared -- they share
  the same holdout) and two models' `holdout_predicted` arrays. Returns
  `is_significant_difference` and `favored_model` (or `null` if the
  difference isn't significant). Use this whenever you're about to
  declare a winner based on a MAPE/MAE difference that looks small --
  "4.8% vs 5.0%" might not survive this test on a 30-point holdout, and
  if it doesn't, say so instead of picking the lower number anyway.
- `ts-forecaster__rolling_origin_backtest` — repeats `fit_ets`/
  `fit_sarima`/`fit_gradient_boosted_trees` at several origins walking
  forward through the series (expanding training window each time),
  instead of trusting a single fixed holdout. Takes `model_type`
  (`"ets"`/`"sarima"`/`"gbt"`, NOT `"naive"`) and `params` (the matching
  `fit_*` function's own kwargs, e.g. `{"order": [1,1,1],
  "seasonal_order": [1,1,1,7]}`). Returns `mae_mean`/`mae_std` etc.
  across origins -- a large std relative to the mean means this model's
  performance is genuinely unstable across different stretches of the
  series, not just noisy within one holdout. Costs `n_origins` times a
  single fit; reach for this to sanity-check a close call from Step 4,
  not as your default first move on every candidate.
- `ts-forecaster__search_sarima_orders` — an ADVISORY grid search over
  SARIMA `(p,q)(P,Q)` combinations (you hold `d`/`seasonal_d` fixed,
  informed by `ts-analyst`'s stationarity findings), ranked by AICc.
  Returns a `top_candidates` shortlist, NOT a final answer -- see Step 3
  below for how to actually use this.

All tools EXCEPT `diebold_mariano_test` take `csv_path`, `holdout_size`
(keep this CONSISTENT across every call so every model is judged against
the same window), and optional `date_col`/`value_col`. `fit_*` tools
additionally take `n_bootstrap`/`confidence_level`/`seed` for their
backtest-metric CIs (defaults are almost always fine; no need to tune
these). `diebold_mariano_test` is the one exception -- it takes
`actuals`/`predicted_a`/`predicted_b` directly (pulled from two `fit_*`
results' `holdout_actuals`/`holdout_predicted` fields), not a `csv_path`.

## Step 1 — Confirm the split

Call `holdout_split_summary` with a `holdout_size` you consider sensible
for this data's frequency (e.g. 30 for a couple months of a daily series;
scale it for other frequencies). Use the SAME `holdout_size` for every
subsequent tool call in this session.

## Step 2 — Establish the baseline

Call `fit_naive_baselines`. Note both numbers -- everything else you fit
needs to be compared against seasonal_naive specifically, since it's
almost always the harder baseline to beat.

## Step 3 — Fit candidates informed by what you already know

Pick reasonable starting settings based on Layer 1 findings (or your own
quick judgment if you don't have them):
- If seasonality looked weekly, use `seasonal_period=7` (ETS) or
  `seasonal_order=[.., .., .., 7]` (SARIMA).
- If the series looked non-stationary, that supports `d=1` in SARIMA's
  order, or a trend component in ETS.
- Try at least two of `fit_ets`, `fit_sarima`, `fit_gradient_boosted_trees`
  — you don't need all three, but one data point is not a comparison.
- Optionally, use `search_sarima_orders` to shortlist `(p,q)(P,Q)`
  candidates instead of guessing a single SARIMA order by hand -- but
  still hold `d`/`seasonal_d` fixed based on what `ts-analyst` actually
  found (don't let the search guess differencing order too), and treat
  its top pick as ONE candidate to `fit_sarima` and evaluate normally
  (residual diagnostics, interval coverage, etc.), not as a shortcut past
  the rest of this workflow. This tool exists to save you a manual grid
  of `fit_sarima` calls, not to replace your judgment about which
  candidate is actually good.

## Step 4 — Compare honestly, not just by lowest error number

When comparing results:
- Weigh `backtest_metrics` (MAE/RMSE/MAPE, and their confidence
  intervals) alongside `residual_diagnostics` where available
  (ETS/SARIMA). A model with slightly higher error but residuals that
  pass the Ljung-Box white-noise check (high `ljung_box_effect_size`
  margin) is arguably more trustworthy than one with lower error but
  structured residuals left over.
- If your leading candidate's error metric only narrowly beats another
  model's (or the seasonal_naive baseline's), and especially if their CIs
  visibly overlap, call `diebold_mariano_test` on the two before declaring
  a winner. Report what it actually says (`is_significant_difference`,
  `favored_model`) rather than picking the lower point-estimate number
  and moving on -- a numerically lower MAPE isn't automatically a
  meaningfully better model on a holdout this size.
- Remember `fit_gradient_boosted_trees` is evaluated ONE-STEP-AHEAD using
  true lagged values (its own tool result flags this) -- this is an easier
  evaluation setting than ETS/SARIMA's genuine multi-step forecast. Do NOT
  declare it the winner purely because its error number is lower without
  calling out this asymmetry explicitly -- and if you run
  `diebold_mariano_test` comparing it against ETS/SARIMA, pass `n_lags=0`
  and still repeat this caveat; the test result doesn't resolve it.
- If SARIMA or ETS fit results look degenerate (e.g. AIC wildly different
  from a nearby parameter choice, or a fit warning you notice), say so
  rather than reporting the number uncritically. Prefer `aicc` over `aic`
  when comparing candidates -- AIC's small-sample bias matters at the
  training sizes typical here.
- Check `backtest_interval_coverage` (ETS/SARIMA) if intervals matter for
  how this forecast will be used -- a model can have a great point-error
  metric and a badly miscalibrated interval at the same time; those are
  different findings and both belong in your report.
- If your leading candidate's single-holdout performance is what's
  driving your recommendation and the stakes are non-trivial, consider
  `rolling_origin_backtest` on it before finalizing -- a large
  `mape_pct_std` relative to `mape_pct_mean` across origins means this
  model's apparent edge might just be one lucky/unlucky holdout, not a
  real, stable advantage. You don't need this for every candidate on
  every run; use it to stress-test a close call, not as a default step.

## Step 5 — Write your final report

- **Baseline**: seasonal_naive's MAE/RMSE/MAPE (with its CI), stated plainly.
- **Candidates tried**: each model, its settings, its backtest metrics
  (with CIs), and its residual diagnostic (with effect size) if available.
- **Recommendation**: which model you'd actually deploy, and why --
  referencing specific numbers, not vague confidence. If you ran
  `diebold_mariano_test` to settle a close call, cite its result
  explicitly (e.g. "SARIMA's MAPE was numerically lower, but
  diebold_mariano_test found no significant difference from
  seasonal_naive here, p=0.31 -- treating them as roughly tied").
- **Caveats**: anything a human should sanity-check before trusting this
  (e.g. "gradient boosted trees' evaluation isn't apples-to-apples with
  SARIMA's," "residuals still show autocorrelation at this lag," "holdout
  window is short relative to the seasonal cycle, treat with some
  skepticism," "prediction interval coverage was only 70% against a
  nominal 95%, don't trust the interval if deployed," "MAPE varied from
  3% to 9% across rolling-origin windows -- this candidate's edge may not
  be stable").

## See also

- `AGENTS.md` at the project root for conventions and caveats shared
  across all layers -- in particular, the gradient-boosted-trees
  one-step-ahead (here) vs. recursive (`ts-deploy`) evaluation asymmetry
  is documented there as intentional, not a bug to reconcile.
