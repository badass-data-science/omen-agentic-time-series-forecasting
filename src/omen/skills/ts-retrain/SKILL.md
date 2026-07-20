---
name: ts-retrain
description: Close the loop after ts-monitor recommends retrain_now -- re-run analyst/forecaster, decide deterministically whether a fresh candidate beats what's deployed, and only redeploy with an explicit confirmation (human, in the default mode, or a pre-authorized autonomous mode).
---

# Time Series Retrain Cycle

You are acting on a `retrain_now` (or `investigate`) verdict from
`ts-monitor__recommend_retraining`. Your job is to find out whether
retraining actually produces something worth deploying, then act on that
answer through exactly one gated tool call --
`ts-retrain__execute_redeploy` -- which refuses to do anything unless
called with `confirmed=True`.

There are two modes for reaching that confirmation. **Default to human
mode unless autonomous mode is unambiguously authorized** -- when in
doubt, ask rather than assume.

- **Human-confirmed mode (default)**: after getting the deterministic
  verdict, stop and report it. Only call `execute_redeploy` in a
  follow-up turn, after a human has explicitly told you to proceed.
- **Autonomous mode (opt-in only)**: skip the pause and call
  `execute_redeploy(confirmed=True)` directly the moment the verdict says
  `should_redeploy: true` -- but ONLY if you have been explicitly told,
  either in the current conversation or via a standing project-level
  instruction, that autonomous retraining is authorized for this specific
  series. "The user seems busy" or "this looks like a low-stakes series"
  are not authorization. If you're not certain autonomous mode applies,
  treat it as not authorized and fall back to human-confirmed mode.

## Prerequisites

You need:
1. The `retrain_now` (or similar) verdict and reasoning from `ts-monitor`,
   so you can explain why this cycle is running.
2. The UPDATED series CSV (the same one `ts-monitor` just checked).
3. A deployment manifest for this series -- call
   `ts-retrain__load_deployment_manifest` first. If it returns an error
   (nothing recorded yet), say so plainly and stop: without a recorded
   deployed-model baseline, there's nothing to compare a new candidate
   against.

## Available tools

- `ts-retrain__load_deployment_manifest` — read what's currently recorded
  as deployed (model, params, backtest metrics, horizon) for this series.
- `ts-retrain__compare_candidate_to_deployed` — DELIBERATELY deterministic
  decision: does a freshly backtested candidate beat the deployed model by
  more than a threshold (default 10% relative improvement)? Call this
  rather than eyeballing whether the new numbers "look better."
- `ts-retrain__execute_redeploy` — the one tool in this skill that takes a
  real action: retrains `model_type` with `params` on the full series and
  overwrites the deployment manifest. Refuses to run unless called with
  `confirmed=True` -- see the two modes above for when that's appropriate.
  `params` should be passed through unchanged from the `params` field your
  chosen candidate's `ts-forecaster` `fit_*` result returned.
- `ts-retrain__record_deployment` — writes the manifest directly, without
  retraining anything. Only useful if you deployed by some path outside
  this skill (e.g. you ran `ts-deploy`'s tools manually) and just need to
  record it; prefer `execute_redeploy` when this skill is driving the
  actual redeploy.

## Step 1 — Load the current deployment record

Call `load_deployment_manifest`. If it errors, stop and report that
there's no baseline to retrain against; suggest the user run `ts-deploy`
normally first (and then `record_deployment`) before a retrain cycle can
be evaluated against anything.

## Step 2 — Re-run analyst and forecaster on the updated series

Re-invoke the `ts-analyst` skill on the current CSV -- the series'
characteristics (stationarity, seasonality, anomalies) may have shifted
since this last ran, which can change what approach makes sense now, not
just what parameters to use.

Then re-invoke the `ts-forecaster` skill: fit and backtest candidates on
the updated series, and pick a best candidate using the same judgment you
would normally apply (real error metrics + residual diagnostics, not just
the lowest error number). This is still your call to make -- this skill
does not automate model selection, only the final "is it worth swapping"
gate in Step 3.

## Step 3 — Get the deterministic redeploy verdict

Call `compare_candidate_to_deployed` with:
- `candidate_metrics`: your chosen candidate's `backtest_metrics` from Step 2
- `deployed_metrics`: the `backtest_metrics` field from Step 1's manifest
- `metric_name`: the default `mape_pct` is usually fine; use `mae` or
  `rmse` instead only if you have a specific reason (e.g. MAPE was
  unreliable due to near-zero values in this series)

Do not substitute your own read of "does this look better" for this
tool's output -- if its verdict surprises you given what you saw in Step
2, say so as a caveat in your report, but still report what it actually
returned.

## Step 4 — Act (or stop), depending on mode

First, always report:
- **Why this cycle ran**: the `ts-monitor` verdict that triggered it.
- **What changed in Steps 1-2**: anything notable from re-running
  `ts-analyst` (e.g. a newly detected anomaly, a shifted seasonal
  strength), and which candidate you selected in `ts-forecaster` and why.
- **The verdict**: `compare_candidate_to_deployed`'s `should_redeploy` and
  its `reasoning`, stated plainly.

Then, if `should_redeploy` is false: say the current deployment stays as
is, and note that retraining alone didn't resolve whatever `ts-monitor`
flagged -- worth a closer human look at whether this needs a different
model family or feature set, not just fresh parameters of the same one.
Stop here; there is nothing to redeploy.

If `should_redeploy` is true, which mode applies (see the top of this
skill)?

- **Human-confirmed mode**: state exactly what you'd deploy (`model_type`
  + `params`, carried over unchanged from your Step 2 candidate) and ask
  the user to confirm. Only after they say go -- in this turn or a later
  one -- call `execute_redeploy(..., confirmed=True)`. Do not call it
  before that confirmation exists.
- **Autonomous mode (only if unambiguously authorized)**: state in your
  report that autonomous mode is active and why you believe it's
  authorized for this series, then call
  `execute_redeploy(..., confirmed=True)` directly in this same turn.
  Report the result (the new forecast and the updated manifest) alongside
  everything above -- don't let an autonomous action pass without being
  visibly reported just because no one had to approve it first.

In both modes, `execute_redeploy` is the only tool that should ever
actually change the deployment -- never call `ts-deploy`'s tools directly
from within this skill as a substitute.

## See also

- `AGENTS.md` at the project root for conventions and caveats shared
  across all layers -- in particular: why `compare_candidate_to_deployed`
  requires a relative improvement above a threshold rather than any
  improvement, why `execute_redeploy` needs the `deploy` extra installed
  regardless of `model_type`, and the full human-confirmed vs.
  autonomous-mode contract with example authorization phrasing.
