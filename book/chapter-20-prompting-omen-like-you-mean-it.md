# Chapter 20: Prompting Omen Like You Mean It

Nineteen chapters have shown Omen's tools working correctly, given
reasonably well-formed requests. This chapter is about the requests
themselves — three real submitted prompts, each with a real flaw, rewritten
and explained. No new series this time; every example reuses history this
book has already built.

## Prompt One: Too Vague to Carry Anything Forward

> **As submitted:** "Forecast the mojito inventory series."

This looks harmless. It is exactly the prompt that reproduces Chapter
14's opening mistake. Handed straight to an agent with no further
context, "forecast the mojito inventory series" has no reason to route
around the raw, uninterpolated CSV — Chapter 3's own file, the one with
five missing days baked in — and no reason to pick a model informed by
anything this book has already established about this series. The most
literal reading of this prompt calls `forecast_ets` directly on the raw
data. Chapter 14 already showed, in full, real detail, exactly what that
produces: thirty `null` forecasts and a `plausibility_check` that
actively, falsely, reports the result as unremarkable. A vague prompt
doesn't just risk a mediocre answer here — it risks silently reproducing
a documented, serious failure mode, with no error message anywhere to
catch it.

**Rewritten:** "Using the cleaned, interpolated mojito inventory series
from Chapter 14, deploy a SARIMA forecast with a 30-day horizon, and
tell me if the plausibility check raises any concerns."

What changed, specifically: it names *which* series (the cleaned one,
not Chapter 3's raw file — carrying forward a finding instead of leaving
the agent to rediscover, or miss, it), *which* layer (`ts-deploy`, not
an ambiguous "forecast" that could mean a Layer 2 backtest or a Layer 3
deployment), and *which* model (SARIMA, this series' most-analytically-
confident option per Chapter 14's real interval comparison). It still
leaves real room for judgment: the horizon is specified, but *how* to
read the plausibility check's output is left to the agent, not
dictated. This is the shape a well-formed prompt for this toolkit
should have — specific about the settled questions, open about the ones
that still require reasoning over real tool output.

## Prompt Two: So Specific It Leaves Nothing to Reason About

> **As submitted:** "Call `fit_sarima` with `csv_path=deathray_revenue.csv`,
> `order=[1,1,2]`, `seasonal_order=[0,0,0,2]`, `holdout_size=30`,
> `confidence_level=0.95`, `n_bootstrap=1000`, `seed=42`, and just tell
> me the `aicc` value. Nothing else."

Every parameter here is, in fact, correct — this is Chapter 10's own
real winning configuration, verified live in this book. That's exactly
what makes this prompt worth flagging rather than praising: it's
correct today, by accident of having been copied from a chapter that
already did the reasoning, and it forecloses the agent from doing any
reasoning of its own if circumstances change. Nothing here asks whether
`(1,1,2)` is *still* the best choice — Chapter 10's own
`search_sarima_orders` result flagged its top two candidates as
separated by less than one AICc point, explicitly recommending a
Diebold-Mariano check before trusting either blind. A prompt that
hard-codes the winning order skips past the very verification step this
book spent two full chapters establishing as necessary. And restricting
the output to a single number throws away everything else the tool
computes for free — residual diagnostics, interval coverage, the
bootstrap CI on that same AICc-adjacent MAPE — all real, all already
paid for by the call, all discarded by the prompt's own instruction.

**Rewritten:** "Fit SARIMA on death-ray revenue, using Chapter 4's
finding that `d=1`. Search reasonable `p`/`q` combinations rather than
guessing, and tell me whether the top candidate's residuals actually
look clean before I trust it."

This keeps exactly one hard constraint — `d=1`, because that's not a
free parameter this book left unexamined, it's Chapter 4's real,
tested finding, and re-deriving it every time would waste real
verification work already done. Everything downstream of that one
grounded fact is left open: which `p`/`q` combination wins, whether its
residuals hold up, whether a close second candidate deserves a DM test.
That's the line this book keeps drawing, chapter after chapter: specify
the constraint that's actually settled, and let the agent — and the
tools built for exactly this — do the reasoning that isn't.

## Prompt Three: Right Question, Wrong Layer (Or Is It?)

> **As submitted:** "Is the SARIMA model good enough to keep running, or
> should we switch to something else?"

This one is harder to fault on vagueness — it's a real, well-formed
question a person would actually ask. The problem is that it maps onto
three genuinely different real questions this book has already answered
three genuinely different real ways, depending on which layer is meant:

- As a **Layer 2 model-selection** question — "does SARIMA still beat
  the alternatives on a fresh backtest" — Chapter 12's real
  Diebold-Mariano result says ETS significantly beats SARIMA on
  Death-Ray Revenue (`p=0.006`).
- As a **Layer 4 production-monitoring** question — "is the currently
  *deployed* SARIMA still tracking real observations well" — that's an
  entirely different real tool (`compare_forecast_to_actuals` and
  `recommend_retraining`), answered with real degradation and drift
  numbers, not a backtest comparison at all.
- As a **Layer 5 redeploy-decision** question — "does a freshly
  retrained candidate clear the bar to replace what's live" — Chapter
  18's real result found a retrained SARIMA candidate only marginally
  ahead (`3.07%`), correctly rejected for falling under the redeploy
  threshold.

**What It Means:** All three answers are real, all three are already
published in this book, and they don't agree with each other — because
they're not actually the same question. Handed the prompt as submitted,
an agent has to *guess* which one was meant, and a plausible-sounding
answer to the wrong one of the three is worse than an agent that stops
to ask, because it doesn't announce itself as wrong.

**Rewritten (pick one):** "Using `ts-monitor`, compare the currently
deployed forecast against real observations from the last month, and
tell me what `recommend_retraining` suggests" — or, if the Layer 2
question was actually meant, "Using `ts-forecaster`, run a fresh backtest
comparison between SARIMA and ETS on the current data, and tell me if
Diebold-Mariano finds a significant difference." Naming the layer isn't
pedantry — it's the difference between three well-defined, previously-
answered real questions and one ambiguous one with no single correct
answer to be graded against.

## Your Turn

This chapter's exercises are prompt-writing exercises, not tool calls.
Pick two or three prompts from `prompts/testing-and-learning-prompts.md`
— written for testing and learning, not for polish — and rewrite them
the way this chapter just did: name the layer, carry forward whatever an
earlier step in the pipeline already established, and check whether
you've left genuine room for the agent to reason, or quietly closed it
off. The two failure modes this chapter demonstrated are mirror images
of each other — too little direction, and the agent falls back on
arbitrary defaults; too much, and there's no agent left in the loop at
all, just a very expensive way to run a fixed script. The prompts worth
writing sit in the real space between them.

## What's Next

Prompt craft only gets you as far as the tools' own honesty allows.
Chapter 21 turns to the harder, more general question underneath
everything this book has demonstrated: across nineteen chapters of real
results, where did Omen's own tools deserve trust outright, where did
they need a second look, and how do you tell the difference *before*
a result surprises you rather than after?
