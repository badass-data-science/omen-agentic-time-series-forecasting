---
name: ts-monitor
description: Check whether a deployed forecast is still tracking reality, detect data drift, and recommend whether to retrain.
---

# Time Series Monitor

You are checking up on a forecast that was already deployed (via
`ts-deploy`), now that some time has passed and real observations exist
for at least part of its horizon. Your job is to find out whether it's
still trustworthy, and whether the underlying data has changed in a way
that calls for re-running earlier layers.

You need three things to do this properly:
1. The forecast that was produced (the `forecast` list a `ts-deploy` tool
   returned -- if you don't have it in this conversation, ask for it or
   for the settings needed to regenerate it).
2. The UPDATED series CSV, now containing real observations for at least
   part of the forecast horizon.
3. The original Layer 2 backtest MAPE for whatever model is deployed (so
   you have something to compare current performance against). If you
   don't have this, say so explicitly -- `recommend_retraining` can still
   run without it, but the degradation check becomes uninformative.

## Available tools

- `ts-monitor__compare_forecast_to_actuals` — matches the forecast against
  real values now available, returns error metrics over the elapsed
  portion of the horizon (now WITH a bootstrap confidence interval on
  each -- `mae_ci_lower/upper`, `rmse_ci_lower/upper`,
  `mape_pct_ci_lower/upper` inside `backtest_style_metrics`, same
  percentile-bootstrap technique as `ts-forecaster`'s backtest metrics)
  and prediction interval coverage if applicable, now also with a Wilson
  score confidence interval on the coverage percentage itself
  (`empirical_coverage_ci_lower/upper`) -- supplementary context, doesn't
  change the existing `well_calibrated` verdict, but a wide CI here (a
  small number of elapsed dates) means treat that verdict as provisional.
  Also returns `residual_outliers`: `flagged_dates` (any matched-point
  residuals that look like outliers, same modified-z-score technique as
  `ts-analyst__detect_anomalies_robust_zscore`), `max_abs_modified_z_score`,
  `per_point` (every matched date's own residual and modified z-score, not
  just the flagged ones), and `metrics_excluding_outliers`, so you can tell
  "the forecast missed a little every day" from "the forecast was fine
  except one wild day" before treating the aggregate error as evidence the
  model needs retraining.
- `ts-monitor__detect_data_drift` — compares a recent window of the series
  against a reference window just before it (t-test + KS test). Can flag
  false positives on a trending or seasonal series -- read the
  `interpretation` field, don't treat `drift_detected` as automatic alarm.
  Also returns `mean_shift_cohens_d` and the raw `ttest_statistic`/
  `ks_statistic` -- when reporting a drift flag, cite the magnitude
  (Cohen's d, KS statistic), not just the fact that a p-value cleared 0.05.
- `ts-monitor__rolling_drift_check` — repeats `detect_data_drift` at
  several points walking backward through the series instead of trusting
  one single recent/reference split. Reports `checks` (a chronological
  list of each individual window's own `recent_window_end_date`,
  `drift_detected`, `mean_shift_cohens_d`, `ks_statistic` -- inspect this
  if you want to know WHICH window(s) flagged, not just the aggregate),
  `n_checks_failed`, `n_flagged`/`frac_flagged` (how many of the checks
  flagged drift, and what fraction), and `persistent_drift` (true once
  `frac_flagged` clears `persistence_threshold_frac`, default 50%). Use
  this when `detect_data_drift` flags drift and you want to know whether
  it's a SUSTAINED shift (`persistent_drift: true`) or looks more like an
  isolated blip (`frac_flagged` low) -- cheap to run (no model fitting),
  so reach for it whenever the single-window verdict alone would leave
  you guessing.
- `ts-monitor__recommend_retraining` — a DELIBERATELY deterministic,
  rule-based decision (not a judgment call for you to make from scratch)
  combining error degradation and drift into one of: `retrain_now`,
  `investigate`, `monitor_closely`, `no_action_needed`. Call this rather
  than eyeballing your own verdict -- the point of this tool existing is
  that this decision should be reproducible given the same inputs. Pass
  `mape_now_ci_lower`/`mape_now_ci_upper` (from Step 1's
  `mape_pct_ci_lower`/`mape_pct_ci_upper`) if you have them -- the result
  then reports the implied degradation range as `pct_degradation_ci_lower`/
  `pct_degradation_ci_upper`, and when the degradation threshold falls
  inside that range, flags `degradation_threshold_within_ci: true` and
  says so in `reasoning`, meaning the verdict is sensitive to sampling
  noise, not clear-cut.
- `ts-monitor__plot_forecast_vs_actuals` — visual, INLINE-rendered
  companion to `compare_forecast_to_actuals`: forecast trajectory (with
  interval band, if any) against the real observed actuals. Same
  `forecast`/`csv_path` arguments as that tool -- reuses its own
  date-matching internally, so the points plotted are exactly the ones
  its `backtest_style_metrics` were computed from.
- `ts-monitor__plot_drift` — visual companion to `detect_data_drift`:
  recent-vs-reference window distributions side by side, annotated with
  the real Cohen's d and drift verdict. Same `csv_path`/window-size
  arguments as that tool; calls it internally rather than reimplementing
  the statistics.
- `ts-monitor__plot_rolling_drift` — visual companion to
  `rolling_drift_check`: Cohen's d across the walk-forward checks, with
  flagged checks marked. Takes that tool's own `checks` list directly.

All three plot_* tools are supplementary visual feedback, never a
substitute for the exact numbers in the JSON tools above -- report those
numbers regardless of whether you also show a plot.

## Step 1 — Compare forecast to reality

Call `compare_forecast_to_actuals`. If it returns an error saying no
actuals exist yet for any forecasted date, stop here and tell the user to
check back once more data has been collected -- don't force a comparison
that isn't possible yet.

## Step 2 — Check for drift

Call `detect_data_drift` on the updated series. If `drift_detected` is
true, look at whether the series has an obvious ongoing trend or just
passed a seasonal transition before treating it as a genuine concern --
the tool cannot tell the difference between that and an actual regime
change, only you (by looking at the numbers and what you already know
about this series from earlier layers) can make that call.

If `drift_detected` is true and you're still unsure whether it's a
one-off blip or something sustained, call `rolling_drift_check` next --
it's cheap, and `persistent_drift: true` (flagged across most of the
rolling checks) is meaningfully stronger evidence of a genuine shift than
a single `detect_data_drift` call can provide on its own. Not required
every time, but worth reaching for whenever the single-window verdict
alone would leave you guessing.

## Step 3 — Get the retrain recommendation

Call `recommend_retraining`, passing:
- `mape_now` from Step 1's `backtest_style_metrics.mape_pct`
- `mape_backtest` from the original Layer 2 result (or omit/pass None if
  you don't have it, and say so in your report)
- `drift_detected` from Step 2
- `interval_coverage_pct` / `nominal_confidence_pct` from Step 1's
  `interval_coverage`, if it was available
- `mape_now_ci_lower` / `mape_now_ci_upper` from Step 1's
  `backtest_style_metrics.mape_pct_ci_lower` / `mape_pct_ci_upper` --
  pass these whenever you have them, it costs nothing and lets the tool
  flag a borderline verdict for you instead of you having to notice it

Do not substitute your own judgment for this tool's output -- if you think
its recommendation seems off given what you saw in Steps 1-2, say so as a
caveat in your report, but still report what it actually returned.

## Step 4 — Write your report

- **Current accuracy**: the elapsed-horizon MAPE and its confidence
  interval, and how it compares to the original backtest MAPE (or a note
  that you don't have the backtest number to compare against). If
  `recommend_retraining` flagged `degradation_threshold_within_ci: true`,
  say so plainly -- the verdict is close to the threshold, not a clean call.
  If `residual_outliers` flagged any dates, mention whether the error is
  concentrated in those days (check `metrics_excluding_outliers`) rather
  than spread evenly across the elapsed horizon.
- **Interval calibration**: if available, whether coverage looks right --
  and if `empirical_coverage_ci_lower/upper` is wide, say the calibration
  read is provisional given how few dates have elapsed so far.
- **Drift status**: what the tests found -- cite the magnitude
  (`mean_shift_cohens_d`, `ks_statistic`), not just that a p-value cleared
  0.05 -- your own read on whether a `drift_detected=True` looks like
  trend/seasonality vs. something new, and, if you ran it,
  `rolling_drift_check`'s `persistent_drift` verdict.
- **Recommendation**: exactly what `recommend_retraining` returned, plus
  its `reasoning` field.
- **What to do next**: if the recommendation was `retrain_now` (or
  `investigate`), say clearly that this means invoking the `ts-retrain`
  skill next -- it re-runs `ts-analyst` and `ts-forecaster` on the updated
  series and decides deterministically whether the resulting candidate is
  actually worth redeploying, then redeploys only through its own gated,
  confirmed workflow. Don't just report the verdict and stop, and don't
  tell the user to run `ts-analyst`/`ts-forecaster`/`ts-deploy` by hand as
  if `ts-retrain` didn't exist.

## See also

- `AGENTS.md` at the project root for conventions and caveats shared
  across all layers -- e.g. why `detect_data_drift` treats an ongoing
  trend as a plausible false positive by design, not a bug.
