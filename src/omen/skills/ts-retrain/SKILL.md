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
  verdict, stop and report it. Only call `execute_redeploy(confirmed=True)`
  (leave `autonomous` at its default `False`) in a follow-up turn, after a
  human has explicitly told you to proceed.
- **Autonomous mode (opt-in only)**: skip the pause and call
  `execute_redeploy(confirmed=True, autonomous=True)` directly the moment
  the verdict says `should_redeploy: true` -- but ONLY if you have been
  explicitly told, either in the current conversation or via a standing
  project-level instruction, that autonomous retraining is authorized for
  this specific series, AND that authorization has actually been recorded
  via `authorize_autonomous_mode` (see "Granting or checking
  autonomous-mode authorization" below). "The user seems
  busy" or "this looks like a low-stakes series" are not authorization.
  If you're not certain autonomous mode applies, treat it as not
  authorized and fall back to human-confirmed mode. Unlike the rest of
  this contract, this specific check is NOT just a prose instruction you
  have to remember correctly -- `execute_redeploy` itself refuses to
  proceed with `autonomous=True` unless a standing record exists, so an
  agent that skips this step gets a hard error back, not a silent policy
  violation.

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

## Granting or checking autonomous-mode authorization (not a retrain-cycle step)

This is separate from the four-step cycle below -- it's how the
standing authorization record itself gets created, not something you do
every cycle. Only relevant if autonomous mode is in play for this series
at all; skip straight to Step 1 otherwise.

- If a human explicitly grants autonomous retraining for a specific
  series in conversation (or a standing project instruction unambiguously
  covers it), call `ts-retrain__authorize_autonomous_mode` to persist
  that -- pass `authorized_by` describing who/what granted it (e.g.
  `"user, in conversation on 2026-07-21"`), so the record is
  self-explanatory to whoever reads it back later. Do this once, not
  every cycle -- the record persists until revoked.
- If you're ever unsure whether autonomous mode is actually authorized
  for a series (rather than just recalled from earlier in the
  conversation), call `ts-retrain__check_autonomous_mode` and trust its
  `authorized` field over your own memory of the conversation.
- If a human revokes authorization, or you're told autonomous mode should
  no longer apply to a series, call `ts-retrain__revoke_autonomous_mode`.

## Available tools

- `ts-retrain__load_deployment_manifest` — read what's currently recorded
  as deployed (model, params, backtest metrics, horizon) for this series.
- `ts-retrain__compare_candidate_to_deployed` — DELIBERATELY deterministic
  decision: does a freshly backtested candidate beat the deployed model by
  more than a threshold (default 10% relative improvement)? Call this
  rather than eyeballing whether the new numbers "look better." If your
  candidate's `backtest_metrics` has a bootstrap CI for the compared metric
  (it will, if it came from a recent `ts-forecaster` `fit_*` call), the
  result also reports `pct_improvement_ci_lower`/`pct_improvement_ci_upper`
  and flags `redeploy_threshold_within_ci: true` when the threshold itself
  falls inside that range -- meaning `should_redeploy` is close to a coin
  flip on backtest sampling noise, not a clean call. If the deployed
  model's manifest also has a CI for the same metric (from a CI-aware
  deployment), that uncertainty gets combined in too
  (`deployed_metrics_ci_used: true`) rather than treating the deployed
  value as a fixed point.
- `ts-retrain__execute_redeploy` — the one tool in this skill that takes a
  real action: retrains `model_type` with `params` on the full series and
  overwrites the deployment manifest. Refuses to run unless called with
  `confirmed=True` -- see the two modes above for when that's appropriate.
  `params` should be passed through unchanged from the `params` field your
  chosen candidate's `ts-forecaster` `fit_*` result returned. On success
  its result includes `forecast_result` (the actual new forecast) and
  `manifest` (the deployment record as just written) -- report both, not
  just a bare "redeployed successfully." It also includes
  `previous_deployment` -- whatever was deployed immediately before this
  call (or `null` on a first deployment) -- so what actually changed is
  right there in the tool's own output, not something you have to
  reconstruct from earlier in the conversation. Pass `autonomous=True` for
  an unattended autonomous-mode call specifically -- it will refuse even
  with `confirmed=True` unless `authorize_autonomous_mode` has already
  recorded standing authorization for this series.
- `ts-retrain__authorize_autonomous_mode` / `ts-retrain__revoke_autonomous_mode` /
  `ts-retrain__check_autonomous_mode` — persist, remove, and read back a
  standing autonomous-mode authorization record for a specific series (a
  small JSON file next to the manifest, not a field within it).
  `authorize_autonomous_mode` returns `record` (`authorized_at`,
  `authorized_by`, `note`); `check_autonomous_mode` returns those same
  fields flat when `authorized: true`, or `checked_path` (which file it
  looked at) when not -- cite `authorized_by`/`authorized_at` when
  reporting that autonomous mode applied, not just the bare boolean. See
  "Granting or checking autonomous-mode authorization" above -- these are
  not part of the normal four-step cycle.
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
returned. If `redeploy_threshold_within_ci: true` came back, say so
plainly in your report before Step 4 -- the verdict is close to the
threshold, not a clean call, even though it's still the verdict you act on.

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
  `execute_redeploy(..., confirmed=True, autonomous=True)` directly in
  this same turn. If you're not certain a standing authorization record
  actually exists, call `check_autonomous_mode` first rather than
  guessing -- but even if you skip that, `execute_redeploy` itself will
  refuse and return an explanatory error rather than silently redeploying
  when `autonomous=True` has no matching record. Report the result
  (`forecast_result` and `manifest`) alongside everything above -- don't
  let an autonomous action pass without being visibly reported just
  because no one had to approve it first.

In either mode, once `execute_redeploy` has run, report what it says
`previous_deployment` was alongside the new deployment -- a concrete
"replaced X with Y" statement is a better report than just "redeployed
successfully," and the tool's own output already has the old model/params
right there, no need to dig back through the conversation for them.

In both modes, `execute_redeploy` is the only tool that should ever
actually change the deployment -- never call `ts-deploy`'s tools directly
from within this skill as a substitute.

## See also

- `AGENTS.md` at the project root for conventions and caveats shared
  across all layers -- in particular: why `compare_candidate_to_deployed`
  requires a relative improvement above a threshold rather than any
  improvement, why `execute_redeploy` needs the `deploy` extra installed
  regardless of `model_type`, the full human-confirmed vs. autonomous-mode
  contract with example authorization phrasing, and why the autonomous-mode
  authorization record is a separate file from the deployment manifest.
