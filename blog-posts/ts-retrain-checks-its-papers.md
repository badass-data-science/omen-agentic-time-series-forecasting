# ts-retrain Checks Its Papers (or, How Our Heroine Taught the Suspicious Foreman to Stop Trusting Its Own Memory)

*In which a threshold comparison learns to doubt both sides of an argument instead of just one, a redeploy finally gets receipts, and the one promise this project's very first blog post made about autonomous mode — inspectable, not just conversational — gets kept.*

Back in the introductory post, our heroine described `ts-retrain` as "the suspicious foreman," the layer she was proudest of specifically because of everything it refuses to do. It re-runs `ts-analyst` and `ts-forecaster` on the updated series, hands the resulting candidate to a small deterministic function that decides whether it's actually worth swapping in, and — the whole point of the layer — will only ever change the live deployment through one tool, `execute_redeploy`, which refuses to run without an explicit `confirmed=True`.

Here's the thing about that post, though: it also ended with a confession. Quoting it directly: *"the authorization decision for autonomous mode is still a prose contract enforced by the skill's own judgment, not a config flag the code checks."* That sentence sat there, accurate and slightly uncomfortable, for the rest of this project's rigor pass while every other layer got its confidence intervals and effect sizes sorted out. `ts-retrain` was built fresh mid-session rather than retrofitted like its four siblings, which meant it started this project's statistics-and-honesty campaign a step behind. This post is about it catching up — on both fronts, the statistical one and the "actually check the ID before letting anything unattended happen" one.

## The Foreman's Two Blind Spots

`ts-retrain` had exactly two real gaps by the time everything else in this toolkit had gone through its rigor pass. Neither was subtle once looked at directly.

**First: `compare_candidate_to_deployed` was being handed uncertainty data and throwing it away.** The function's whole job is comparing a fresh candidate's backtest metric against the deployed model's, and both of those metrics — if they came from a recent `ts-forecaster` `fit_*` call — already carry a bootstrap confidence interval. The function just never looked at it. It made its threshold call off two bare point estimates and moved on, exactly the kind of "verdict without a magnitude" this project spent its first few posts rooting out of every other layer.

**Second: autonomous mode's authorization check was a memory, not a record.** The skill's instructions were explicit about when autonomous mode applies — a human has to unambiguously grant it, per series, in conversation or via a standing project instruction. But nothing in the actual code enforced that. `execute_redeploy(confirmed=True)` didn't know or care whether the `True` came from a human saying "go ahead" in this exact turn or from an agent's recollection of something said several turns — or several *sessions* — ago. The gate that mattered most was the one made entirely of prose.

## Fixing the First One Was the Easy Part

`compare_candidate_to_deployed` now reads `{metric_name}_ci_lower`/`{metric_name}_ci_upper` straight out of `candidate_metrics` if they're there, and reports the implied `pct_improvement_ci_lower`/`pct_improvement_ci_upper` — flagging `redeploy_threshold_within_ci: true` whenever the swap threshold itself falls inside that range, meaning the redeploy-or-don't verdict is closer to a coin flip on backtest noise than a clean call.

That much shipped first, treating the deployed model's own value as fixed — the same simplification `ts-monitor__recommend_retraining`'s degradation check already uses. But it turned out `deployed_metrics` can *also* carry a CI, whenever the currently-deployed model's manifest was itself recorded from a CI-aware fit. Ignoring that felt like solving half the problem on purpose, so the function got a second pass: when both sides have a CI, it computes the true worst-case and best-case corners of the box formed by both ranges at once, not just the candidate's.

This isn't the same trick `forecast_ensemble` uses to combine two forecasting models' uncertainty — that technique assumes independence and combines variances, which only works cleanly for a *linear* combination. `pct_improvement = 100 × (deployed − candidate) / deployed` is a ratio, and ratios don't play along with variance addition the same way. What it *is* instead is honest interval arithmetic: the function is monotonically decreasing in the candidate's value and increasing in the deployed value, so its extreme points over a two-dimensional box occur at opposite corners — worst case is the candidate at its highest plausible value paired with the deployed model at its lowest, best case is the reverse. No distributional assumption required, just calculus.

Run against real numbers: a candidate at MAPE 6.0% with a CI of `[5.0, 7.0]`, compared against a deployed model at a flat MAPE of 10.0%, implies an improvement range of `[30.0%, 50.0%]`. Give the deployed model its own CI of `[9.0, 11.0]` — meaning it's not perfectly certain either — and that range widens to `[22.22%, 54.55%]`. Both numbers came out of the exact corner-pairing arithmetic described above, not a fudge factor. Wider is the correct, expected direction: acknowledging a second source of uncertainty should never make you *more* confident in the answer.

## Fixing the Second One Meant Actually Checking

The interesting part of this post is what "closing" the autonomous-mode gap actually required, because the honest answer is: not much code, and a small but real design decision about where that code should live.

Three new small tools now exist purely to persist and read back a decision that's already been made elsewhere: `authorize_autonomous_mode`, `revoke_autonomous_mode`, and `check_autonomous_mode`. None of them exercise any judgment of their own about whether granting autonomous access is a good idea — same division of labor as `record_deployment`, which persists a deployment decision without ever second-guessing it. The record lives in its own file, `autonomous_mode.json`, deliberately separate from the deployment manifest — authorization and deployment are different concerns with different lifecycles. Revoking someone's standing permission to redeploy unattended shouldn't touch what's currently live, and redeploying shouldn't quietly extend or reset a permission grant nobody asked it to touch.

The part that actually closes the gap: `execute_redeploy` picked up a new `autonomous` parameter. When it's `True`, the function calls `check_autonomous_mode` on its own, internally, before doing anything else — and refuses to proceed, even with `confirmed=True` already in hand, if there's no standing record. Verified directly, in sequence, against the same series: an autonomous call with no authorization on file comes back `not_executed` with an explanatory error. Call `authorize_autonomous_mode`, try again — `redeployed`. Call `revoke_autonomous_mode`, try a third time — `not_executed` again, immediately, no lag. And critically, ordinary human-confirmed calls (the default, `autonomous=False`) never touch any of this machinery at all — a human's in-conversation "go ahead" remains its own complete authorization, exactly as it always was.

| | Before | After |
|---|---|---|
| `compare_candidate_to_deployed` uncertainty | Two bare point estimates | Candidate CI, or both sides' CI via interval arithmetic |
| Autonomous-mode authorization | A prose contract the skill was trusted to follow | A persisted record `execute_redeploy` checks itself |
| "Is autonomous mode on for this series?" | Whatever the agent remembers being told | `check_autonomous_mode(csv_path)["authorized"]` |

## The Part Where Documentation Almost Undersold Its Own Feature

One more small thing worth admitting to, because it very nearly undermined the whole point of the work above: after building the authorization record specifically so it would be "self-explanatory to whoever reads it back later" — that phrase is straight out of the function's own docstring — an audit of `SKILL.md` and the tool docstrings found that the actual field names holding that explanation (`record`, `authorized_by`, `authorized_at`, `checked_path`) were never once written down anywhere an agent would see them. Same story on the redeploy side: `execute_redeploy`'s two most important success fields, `forecast_result` and `manifest`, were being described only as "the new forecast and the updated manifest" in prose, with the literal keys never named. A tool that returns receipts nobody was told how to read isn't meaningfully different from a tool that doesn't return receipts at all. Fixed in the same pass — every field mentioned above now has its exact name written down where the agent driving this skill will actually see it.

## Next Steps

- **The authorization record has no history, only a current state** — the same single-record design already accepted for the deployment manifest, and for the same reason (simplicity), but worth naming as a real limitation rather than an oversight: there's no way to ask "when was this last revoked and by whom" after the fact.
- **No expiry.** A standing autonomous-mode grant persists until someone explicitly revokes it — there's no time-boxing, no "authorized for the next 30 days" option. A credential that never expires is a reasonable default for a first version and a real thing to reconsider later.
- **The combined-CI interval arithmetic is a valid bound, but a conservative one.** It answers "what's the worst/best case consistent with both reported ranges," not "what's the actual joint probability distribution of the improvement." A version with access to both models' raw bootstrap resamples could run a proper Monte Carlo combination for a tighter, less pessimistic interval — this project doesn't currently thread raw samples that far, only their summary bounds.

## Conclusion

The suspicious foreman earned that nickname by refusing to redeploy anything without being asked twice. It's now also the layer that, when it does eventually get asked to act without being asked twice, actually checks a signed piece of paper first instead of just recalling that someone probably said it was fine a while back. Our heroine considers a gatekeeper that keeps its own receipts a meaningfully more trustworthy gatekeeper than one that merely means well.

Want to actually work through this layer's tools yourself, with real worked examples? Chapters 18-19 of *Agentic Time Series Forecasting for Supervillains* (`../book/`) cover `ts-retrain` in depth — including a full live-run sequence proving the authorization gate refuses, succeeds, and refuses again exactly when it should.

## Code

Code is available at [badass-data-science/omen-agentic-time-series-forecasting](https://github.com/badass-data-science/omen-agentic-time-series-forecasting).

## AI Use Statement

This article's prose was drafted by Claude Code, based on our heroine's explicit instructions and matching the voice/structure established in the toolkit's five prior posts; she will review and edit before publishing. All of the `ts-retrain` work described here — the candidate-and-deployed-side confidence interval combination in `compare_candidate_to_deployed`, the `previous_deployment` snapshot in `execute_redeploy`, the `authorize_autonomous_mode`/`revoke_autonomous_mode`/`check_autonomous_mode` authorization record and its code-level enforcement inside `execute_redeploy`, and the documentation gaps found and fixed along the way — was designed and built collaboratively with Claude Code across a series of sessions.
