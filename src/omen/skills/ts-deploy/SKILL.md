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
  forward. Useful as a sanity floor alongside the real forecast. Includes
  an analytic prediction interval built from this same method's own
  in-sample residual standard deviation, widening with the horizon
  (falls back to point-only if there isn't enough history to estimate
  one -- check `interval_note`).
- `ts-deploy__forecast_ets` — Holt-Winters, retrained on the full series.
  Prediction interval from simulated future paths (falls back to
  point-only if simulation fails for the given settings -- check the
  `interval_note` field, don't assume an interval is always present).
- `ts-deploy__forecast_sarima` — SARIMA, retrained on the full series.
  Analytic confidence interval from the state-space model.
- `ts-deploy__forecast_gradient_boosted_trees` — retrained on the full
  series, then forecasts RECURSIVELY (each prediction feeds back in as a
  lag feature for the next step). The tool result's `caveat` field
  explicitly warns that errors can compound as the horizon grows -- this
  is a real risk, not boilerplate, and you must carry it into your own
  report rather than letting it sit unread in the tool output. It now
  DOES have a prediction interval (via quantile regression), but that
  interval is approximate and doesn't itself account for the compounding
  risk -- `interval_note` and `caveat` both say so; don't present it with
  the same confidence as SARIMA's analytic interval. `feature_importances`
  now includes a bootstrap confidence interval per feature
  (`{col: {importance, ci_lower, ci_upper}}`) -- a wide CI on a feature
  means its apparent importance isn't very stable across resamples of the
  training data, worth mentioning if you're leaning on feature importance
  to explain the forecast. This CI costs real extra compute (`n_bootstrap`
  extra model fits, default 100); pass `n_bootstrap=0` if you don't need it.
- `ts-deploy__forecast_ensemble` — combines two or more of the above into
  one weighted forecast. Use this when more than one candidate backtested
  reasonably well in Layer 2 and you don't want to force a single winner.
  See "Combining candidates" below.

All single-model tools take `csv_path`, `horizon` (how many steps into the
future to forecast), and optional `date_col`/`value_col`. Every one of
them (including `forecast_ensemble`) also returns a `plausibility_check`
field -- see Step 3.

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
  when the series never has, flatten out when it shouldn't)? Every
  forecast tool now automates part of this eyeball check for you via its
  `plausibility_check` field: it compares the forecast's implied change
  against the empirical distribution of changes the series has actually
  made historically, and flags `is_extreme_relative_to_history` plus
  whether the forecast leaves the historical min/max range entirely. This
  is NOT a verdict -- a genuine regime change can legitimately produce an
  "extreme" forecast that's still correct -- but treat a flagged result as
  a prompt to look closer and say something about it, not something to
  silently pass through.
- Is there a prediction interval? If `interval_note` says point-forecast-only
  (possible for naive when there's too little history, sometimes ETS),
  that needs to be stated clearly in the report, not just implied by its
  absence. GBT now reports an interval too, but `interval_note` explicitly
  flags it as approximate -- don't present it with SARIMA's level of
  confidence. Naive's interval is a genuine analytic textbook formula
  (residual-std-based, growing with the horizon), reasonable to present
  with the same confidence as SARIMA's, just usually much wider since it
  isn't informed by any actual model of the series' structure.
- If you used `forecast_gradient_boosted_trees`, is the `horizon` long
  enough that the compounding-error caveat actually matters here? A 5-step
  horizon is lower-risk than a 90-step one -- calibrate how much you
  emphasize the caveat to the actual horizon requested.

## Combining candidates with `forecast_ensemble`

If Layer 2 left you with more than one reasonable candidate (e.g. SARIMA
and ETS both backtested acceptably, with no statistically significant
difference between them per `diebold_mariano_test`), you don't have to
force a single winner here. Call `forecast_ensemble` with `model_types`
set to the candidates you want combined:

- Default weighting is equal across the listed models. If you have a
  principled reason to weight one candidate more (e.g. its Layer 2
  `backtest_metrics.mae` was meaningfully lower), pass `weights` -- raw
  inverse-error values are fine, they get normalized internally, you
  don't need to pre-compute proportions yourself.
- Read `interval_note`: a combined interval is only reported if every
  included model contributed one of its own, and even then it's built by
  combining each component's implied variance under an INDEPENDENCE
  assumption between models -- more principled than a plain bound
  average, but still optimistic, since every component is fit on the SAME
  series and shares real error structure. Say so if you report it. It can
  come out narrower than any single component's own interval -- that's
  the expected effect of combining independent estimates, not a bug worth
  second-guessing, but still worth a caveat in the report (treat the
  combined interval as a lower bound on true uncertainty).
- If you include `"gbt"`, the recursive-compounding caveat still applies
  and shows up in the result's own `caveat` field -- it doesn't go away
  just because other models are blended in, only gets diluted by weight.
- This is not a substitute for Layer 2's own comparison -- only combine
  candidates that already backtested reasonably on their own merits, not
  as a way to average away a candidate you'd otherwise have rejected.

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
