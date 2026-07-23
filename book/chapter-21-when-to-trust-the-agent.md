# Chapter 21: When to Trust the Agent, and When Not To

Every good operation gets a postmortem, win or lose, and this one has earned a long one: twenty chapters, five layers, one death ray, one secret lab full of mojitos, and a great many statistical tests run for real rather than asserted. This chapter is that postmortem — not about any single series, but about a pattern that shows up, quietly, in every layer's design: certain decisions were taken away from the agent entirely, on purpose, and certain others were deliberately left open. Laid side by side, the line between them turns out to be sharper, and more general, than "Omen's house style."

## The Full List, Gathered in One Place

Every deliberately rule-based decision point this book actually ran, real, with a real reference back to where it happened:

- **`recommend_retraining`** (Chapter 17): four fixed verdicts — `retrain_now`, `investigate`, `monitor_closely`, `no_action_needed` — determined entirely by whether error degradation and drift each cross their own explicit threshold, not by an agent weighing the vibes of the situation.
- **`compare_candidate_to_deployed`**'s `should_redeploy` (Chapter 18): a fixed relative-improvement threshold, real numbers showing it correctly reject a genuine `3.07%` improvement for falling short of `10%`.
- **`execute_redeploy`**'s `confirmed=True` gate (Chapter 19): refuses unconditionally without it — no default, no prose promise, a real code path that returns `not_executed` every single time it's missing.
- **`authorize_autonomous_mode` / `check_autonomous_mode` / `revoke_autonomous_mode`** (Chapter 19): a second, independent gate, demonstrated live to flip from refusal to success to refusal again, purely by what a file on disk said at the moment of the call.
- **`well_calibrated`** interval-coverage checks (Chapters 9, 16): a fixed tolerance band around nominal confidence, the same threshold logic mirrored identically across `ts-forecaster` and `ts-monitor` on purpose (see `AGENTS.md`).
- **`residuals_look_like_white_noise`** (Ljung-Box, Chapters 9-10): a fixed statistical test with a fixed critical value, not a judgment call about whether a residual plot "looks fine."
- **`diebold_mariano_test`**'s `is_significant_difference` (Chapter 12): a fixed `p<0.05` rule, the same test producing every real verdict in that chapter — including, honestly, the ones that overturned the outline's own planned story.
- **`drift_detected`** (Chapter 17): fixed `p<0.05` on two tests, no exceptions for "but it's probably just the trend."

## And, Deliberately, the Opposite List

Just as telling: several places where Omen went out of its way to **not** make something deterministic, even where it easily could have.

- **Which model family to try** — ETS, SARIMA, or gradient-boosted trees — was never decided by a rule anywhere in this book. Chapters 9 through 11 each required looking at a series' actual shape and reasoning about which family's assumptions fit it, and that reasoning is the part no threshold could replace.
- **`search_sarima_orders` refuses to search `d` or seasonal `D`** (Chapter 10) — not a missing feature. Whether a series is stationary is a real, tested, Layer-1 question with a real answer (Chapter 4's ADF/KPSS agreement), and letting a numeric search silently re-decide it based on whatever minimizes AICc would mean the tool overriding a finding it has no way to know is even there.
- **Whether a `drift_detected: true` flag means something worth worrying about** (Chapter 17): the test itself is deterministic; what it means is explicitly not. This book's own real numbers showed why — an entirely ordinary, expected trend produced a Cohen's d of `1.45`, "large" by the exact same textbook bins a genuine incident's `11.91` also cleared. A fixed rule that only looked at "did it clear the threshold" couldn't have told those two situations apart; a human or agent reading the magnitude comparatively could.
- **`plausibility_check`'s `is_extreme_relative_to_history`** (Chapter 14): the tool's own docstring says it directly — "not a hypothesis test... a prompt for scrutiny, not a verdict." A genuine regime change can and should produce an "implausible" forecast that's actually correct; automating a hard stop here would have meant baking in the assumption that the future never legitimately looks unlike the past.
- **Whether to ensemble two candidates at all** (Chapter 15): the Diebold-Mariano test can tell you whether two models are statistically distinguishable; it can't tell you whether you *want* the robustness of blending indistinguishable candidates versus just deploying the single winner. That's a real judgment call about priorities, not a fact the data alone settles.

## The Dividing Line, Stated Directly

Line them up and the actual rule underneath both lists is this: **a decision belongs in a deterministic function when the same inputs should produce the same answer, every time, regardless of who's asking or how the request was phrased — and belongs with agent judgment exactly when that premise doesn't hold.**

`should_redeploy` given a specific MAPE, a specific threshold, and a specific CI has exactly one correct answer, and it shouldn't change because an agent found a competing narrative persuasive that particular afternoon. That's precisely why it's a function, not a prompt. Whether SARIMA or ETS *fits this series' shape* has no such single correct answer computable from a formula — it depends on structural features (does the variance scale with the level? is the seasonal component additive or multiplicative in reality?) that genuinely require looking at the series and reasoning about it, the same reasoning a human forecaster would do. Forcing that into a fixed rule wouldn't make it more rigorous — it would just hide a judgment call behind false precision.

There's a second thread worth naming too, visible across nearly every threshold this book has cited: `improvement_threshold_pct`, `error_degradation_threshold_pct`, `persistence_threshold_frac`, `outlier_z_threshold` — every one of them is an explicit, named parameter with a stated default, never a hidden constant buried in the code. The *enforcement* of a threshold is deterministic; the *calibration* of what that threshold should be is left inspectable and adjustable, because deciding "how much improvement is worth a redeploy" is itself the kind of judgment call that deserves to be made consciously, by whoever's actually accountable for the operation — not quietly hard-coded by whoever wrote the tool.

## A Checklist, for This Toolkit or Any Other

Distilled into something usable beyond Omen: before wiring an agentic tool to decide something automatically, or before leaving it to an agent's judgment, ask —

1. **Would two runs with identical inputs deserve an identical answer?** If yes, that's a strong pull toward a deterministic function, not a prompt.
2. **Is the action hard to reverse, or does it touch shared or production state?** If yes, gate it explicitly — a real `confirmed=True`-style flag, checked in code, not a promise in a docstring an agent is trusted to remember.
3. **Does the rule itself require a judgment call about *where* to set the bar?** If yes, expose that as a named, inspectable parameter rather than a hidden constant — keep the enforcement deterministic and the calibration visible.
4. **Could the same test result mean genuinely different things depending on context a fixed function can't see?** Chapter 17's trend-versus-incident finding is the clearest real example in this book. If the answer is yes, report the number and stop there — don't let the function pretend to a verdict it doesn't actually have the information to make.

## What's Next

This is the shape Omen was built around from Chapter 1 onward, now named directly rather than demonstrated one layer at a time. The conclusion is next — a last look back across all five layers, the running list of honestly-reported gotchas this book collected along the way, and what's still genuinely open.
