---
name: ts-deploy
description: Retrain a chosen forecasting model on the full series and produce a real forecast beyond the data, with intervals and caveats surfaced clearly.
---

# Time Series Deployment Forecast

You are producing a forecast someone will actually use -- not another
backtest. This skill assumes Layers 1 (`ts-analyst`) and 2 (`ts-forecaster`)
have already run, or that you otherwise know which model type backtested
well and with what settings. Carry that forward here rather than picking a
model or its parameters from scratch or by default.

If you don't have a Layer 2 result to draw on, say so explicitly before
proceeding, and pick reasonable settings based on whatever you do know
about the series (from Layer 1, or a quick look at the data) -- don't
silently default to arbitrary parameters as if they were validated.

## Available tools

- `ts-deploy__forecast_naive` — flat or seasonal-naive baseline extended
  forward. No interval. Useful as a sanity floor alongside the real forecast.
- `ts-deploy__forecast_ets` — Holt-Winters, retrained on the full series.
  Prediction interval from simulated future paths (falls back to
  point-only if simulation fails for the given settings -- check the
  `interval_note` field, don't assume an interval is always present).
- `ts-deploy__forecast_sarima` — SARIMA, retrained on the full series.
  Analytic confidence interval from the state-space model.
- `ts-deploy__forecast_gradient_boosted_trees` — retrained on the full
  series, then forecasts RECURSIVELY (each prediction feeds back in as a
  lag feature for the next step). No native interval. The tool result's
  `caveat` field explicitly warns that errors can compound as the horizon
  grows -- this is a real risk, not boilerplate, and you must carry it into
  your own report rather than letting it sit unread in the tool output.

All tools take `csv_path`, `horizon` (how many steps into the future to
forecast), and optional `date_col`/`value_col`.

## Step 1 — Confirm what you're deploying

State plainly, before calling anything: which model type you're deploying
and why (i.e. what Layer 2 found, or your reasoning if you don't have
that). If Layer 2 recommended SARIMA with specific `order`/`seasonal_order`
values, or ETS with specific `trend`/`seasonal`/`seasonal_period` values,
use those same settings here -- don't re-derive them from scratch.

## Step 2 — Generate the forecast

Call the matching `ts-deploy__forecast_*` tool with a `horizon` appropriate
to the request (e.g. "next month" for daily data → `horizon=30`). Also
call `ts-deploy__forecast_naive` alongside it as a sanity floor, unless the
user has explicitly said they don't want it.

## Step 3 — Sanity-check before reporting

Before writing anything up, check:
- Does the forecast's trajectory look plausible given the series' recent
  history, or does it do something obviously wrong (explode, go negative
  when the series never has, flatten out when it shouldn't)? If so, say so
  rather than reporting a forecast you can see is broken.
- Is there a prediction interval? If `interval_note` says point-forecast-only
  (common for naive and GBT, sometimes ETS), that needs to be stated
  clearly in the report, not just implied by its absence.
- If you used `forecast_gradient_boosted_trees`, is the `horizon` long
  enough that the compounding-error caveat actually matters here? A 5-step
  horizon is lower-risk than a 90-step one -- calibrate how much you
  emphasize the caveat to the actual horizon requested.

## Step 4 — Write the deliverable

This report is for someone who will actually act on it, so lead with the
forecast itself, not a wall of methodology:

- **The forecast**: key figures (e.g. next N periods' point values, and the
  interval bounds if available). You don't need to restate every single
  day if the horizon is long -- summarize the trajectory (e.g. "rising from
  X to Y over the period, with a dip expected around Z") and point to the
  full table.
- **Confidence**: state plainly whether there's a prediction interval and
  how wide it is, or that this is a point forecast only.
- **Caveats, prominently, not buried at the end**: if you used GBT with a
  long horizon, the compounding-error risk belongs near the top of the
  caveats, not as an afterthought. Also flag anything from Step 3 that gave
  you pause.
- **What would change this forecast**: one or two sentences on what
  circumstances would make this forecast unreliable (e.g. "if the recent
  anomaly at [date] was a one-off promotion rather than a new pattern,
  actual demand may be lower than shown here").

## See also

- `AGENTS.md` at the project root for conventions and caveats shared
  across all layers -- in particular, the gradient-boosted-trees
  recursive (here) vs. one-step-ahead (`ts-forecaster`) evaluation
  asymmetry is documented there as intentional, not a bug to reconcile.
