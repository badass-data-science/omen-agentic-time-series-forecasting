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
  portion of the horizon and prediction interval coverage if applicable.
- `ts-monitor__detect_data_drift` — compares a recent window of the series
  against a reference window just before it (t-test + KS test). Can flag
  false positives on a trending or seasonal series -- read the
  `interpretation` field, don't treat `drift_detected` as automatic alarm.
- `ts-monitor__recommend_retraining` — a DELIBERATELY deterministic,
  rule-based decision (not a judgment call for you to make from scratch)
  combining error degradation and drift into one of: `retrain_now`,
  `investigate`, `monitor_closely`, `no_action_needed`. Call this rather
  than eyeballing your own verdict -- the point of this tool existing is
  that this decision should be reproducible given the same inputs.

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

## Step 3 — Get the retrain recommendation

Call `recommend_retraining`, passing:
- `mape_now` from Step 1's `backtest_style_metrics.mape_pct`
- `mape_backtest` from the original Layer 2 result (or omit/pass None if
  you don't have it, and say so in your report)
- `drift_detected` from Step 2
- `interval_coverage_pct` / `nominal_confidence_pct` from Step 1's
  `interval_coverage`, if it was available

Do not substitute your own judgment for this tool's output -- if you think
its recommendation seems off given what you saw in Steps 1-2, say so as a
caveat in your report, but still report what it actually returned.

## Step 4 — Write your report

- **Current accuracy**: the elapsed-horizon MAPE, and how it compares to
  the original backtest MAPE (or a note that you don't have the backtest
  number to compare against).
- **Interval calibration**: if available, whether coverage looks right.
- **Drift status**: what the tests found, and your own read on whether a
  `drift_detected=True` looks like trend/seasonality vs. something new.
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
