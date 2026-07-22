# Chapter 13: Trustworthy Across Time — Rolling-Origin Backtesting

Every backtest metric in Part III so far — every MAPE, every bootstrap
CI, every Diebold-Mariano p-value — was computed against the exact same
30-week holdout window: the most recent 30 weeks of Death-Ray Revenue,
fixed, every single time. That's not a flaw in any individual chapter.
It's a shared, unexamined assumption running underneath every one of
them, and this chapter is where it finally gets tested directly: what if
that one window just happened to be an easy one, or a hard one?

## What a Bootstrap CI Still Can't Tell You

It's worth being precise about why the bootstrap confidence intervals
from Chapters 8 through 12 don't already answer this. Those intervals
are built by resampling *points within* the one fixed holdout — they
capture "how much would this metric wobble if I got slightly different
luck on which of these same 30 weeks mattered most," which is real and
useful. They cannot capture "how much would this metric change if the
holdout had been a *different* 30-week stretch of the series entirely."
That's a completely different source of uncertainty, and no amount of
resampling inside one window will ever surface it. Answering it requires
actually moving the window and refitting — a walk-forward, or
rolling-origin, backtest.

## What Rolling-Origin Backtesting Actually Does

`rolling_origin_backtest` repeats a full `fit_ets` / `fit_sarima` /
`fit_gradient_boosted_trees` call at several different **origins**,
walking backward through the series: train on everything available up
to that origin, test on the `holdout_size` window immediately after it,
then move to an earlier origin and do it again, entirely from scratch.
It reports the distribution of backtest performance across origins —
mean, standard deviation, and full per-origin detail — as a direct
measure of how *stable* a model's accuracy actually is, not just what it
happened to be once.

One constraint worth knowing before running it: it needs at least
`holdout_size * (n_origins + 1)` observations, since every origin needs
its own full test window plus training data ahead of it. Death-Ray
Revenue is 70 weeks long — the fixed `holdout_size=30` used everywhere
else in Part III would need 180 weeks for even a single origin's worth
of margin, let alone five. Getting five origins out of this series meant
shrinking to `holdout_size=10` instead — a real, forced tradeoff between
how many origins you can afford to check and how large a holdout each
one gets, not a free parameter to set casually.

## Running It for Real

**Prompt:**
> Run a rolling-origin backtest on SARIMA(1,1,2) across 5 origins. Does
> its MAPE stay stable, or does it swing a lot between origins?

**What Comes Back** (a real result, walking backward through Death-Ray
Revenue, oldest origin first):

```json
{
  "origins": [
    {"train_size": 20, "test_range": ["2024-05-27", "2024-07-29"], "mape_pct": 5.6221},
    {"train_size": 30, "test_range": ["2024-08-05", "2024-10-07"], "mape_pct": 8.7748},
    {"train_size": 40, "test_range": ["2024-10-14", "2024-12-16"], "mape_pct": 3.2465},
    {"train_size": 50, "test_range": ["2024-12-23", "2025-02-24"], "mape_pct": 1.7032},
    {"train_size": 60, "test_range": ["2025-03-03", "2025-05-05"], "mape_pct": 0.8591}
  ],
  "mape_pct_mean": 4.0411,
  "mape_pct_std": 3.2066,
  "interpretation": "Across 5 origin(s)... MAPE averaged 4.0411% (std 3.2066). MAPE varies a lot across origins (relative spread 0.79) -- this model's performance looks unstable across different stretches of the series, not just noisy within one holdout."
}
```

**What It Means:** The headline number — `4.04%` mean MAPE — looks
excellent, competitive with the best single-window results from Chapters
9 and 10. It is also, on its own, misleading. MAPE ranges from `0.86%`
at the most recent origin all the way up to `8.77%` two origins earlier
— a nearly ten-fold spread — and the tool's own instability check agrees:
a relative spread (coefficient of variation) of `0.79` clears its `0.5`
threshold for flagging real cross-origin instability, not just noise.
This is exactly the scenario this chapter's third learning objective
warns about: a good average can sit directly on top of a genuinely
unstable model, and the average alone will never tell you that.

## An Honest Look at *Why*, Without Forcing a Tidy Story

This book's outline originally planned a specific narrative for this
instability — a bidding war driving one window's numbers unusually good,
a publicized malfunction driving another unusually bad. That's not
what's actually in this series; Death-Ray Revenue's data was never built
with either event, and pretending otherwise here would mean writing
fiction into a chapter about respecting what a real backtest actually
shows you.

What the real per-origin numbers suggest instead is less dramatic and
worth taking just as seriously: MAPE broadly *improves* as training size
grows across origins — `5.62%` at 20 weeks of training data down to
`0.86%` at 60 weeks — which lines up with plain intuition: more history
to fit a trend-plus-seasonal model on tends to produce a better fit. But
the pattern isn't clean. The `30`-week-training origin, in the middle,
comes in *worse* (`8.77%`) than the `20`-week origin before it — breaking
the trend rather than smoothly continuing it. Nothing in this chapter's
setup identifies a single specific cause for that one origin's test
window landing badly; it's exactly the kind of ordinary sampling
volatility a single fixed-window backtest would never reveal, because a
single fixed-window backtest, by construction, only ever shows you one
origin. The honest lesson here isn't "here's the exact cause of the
instability" — it's that instability like this exists, is real, and
usually doesn't arrive with a one-sentence explanation attached. Chapter
9's `4.62%` MAPE and Chapter 10's `7.23%`, both computed on the single
most-recent 30-week window, were each just one point drawn from
something that swings roughly this much depending on where the window
happens to land.

## The Honest Price of This Evidence

Two things worth being upfront about before reaching for this tool by
default on every model from now on. First, the compute cost is exactly
what it looks like: `n_origins` full refits, not one. Five origins here
means five separate SARIMA fits, each with its own bootstrap CI
computation — a real multiple of a single `fit_sarima` call, not a
free upgrade. That's a deliberate design choice, not an inefficiency to
optimize away: walk-forward evidence is only genuine walk-forward
evidence if every origin is actually refit from scratch on only the data
that would really have been available at that point in time.

Second, notice what `model_type` refuses to accept:

```json
{"error": "model_type must be one of ['ets', 'sarima', 'gbt'], got 'naive' (naive baselines aren't supported here -- they don't need walk-forward validation)."}
```

This is a deliberate line, not an oversight. Naive and seasonal-naive
don't fit anything — there are no parameters that could have been
estimated well on one stretch of data and poorly on another, so
walking the origin backward and refitting from scratch wouldn't be
testing anything a fitted model's rolling-origin backtest actually
tests. They're a cheap, non-parametric floor, exactly as Chapter 8
introduced them, and floors don't need to prove they're stable across
time the way a model with parameters to overfit does.

## What's Next

Part III closes here with a genuinely uncomfortable finding sitting in
plain sight: this project's own flagship model looks meaningfully less
reliable once you stop trusting a single window. That's not a reason to
abandon everything built in Chapters 9 through 12 — it's a reason to
carry the instability forward honestly rather than quietly forgetting
it once a model gets deployed. Part IV starts exactly there: Chapter 14
takes a model out of the backtest sandbox entirely and puts it into
`ts-deploy`, generating real, forward-looking predictions instead of
one more score against data that's already happened.
