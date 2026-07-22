# Chapter 14: Deploying for Real — Full-Series Refits and Prediction Intervals

Secret Lab™ Mojito Inventory has been waiting since Chapter 3. Every chapter since then borrowed Death-Ray Revenue instead — a fair trade for teaching model comparison on a single consistent series, but it left Chapter 1's opening promise unfinished for the series that actually started this book. This chapter closes that loop: a real, deployed forecast for mojito inventory, using `ts-deploy` instead of `ts-forecaster` for the first time. It also opens with a mistake worth making on purpose, because the mistake teaches more than skipping past it would.

## The Mistake: Deploying Straight From Chapter 3's Own CSV

Chapter 3's mojito inventory series has 5 missing days baked into it — "the incident," `basic_stats`' own `n_missing` field caught it cleanly back then. It would be easy to assume that since `basic_stats` handled it gracefully, every other tool in this book does too.

**Prompt:**
> Deploy an ETS forecast for mojito inventory, straight from the CSV Chapter 3 used.

**What Comes Back** (a real result — every single field, not a truncated excerpt):

```json
{
  "aic": null, "aicc": null,
  "forecast": [{"date": "2024-07-01", "forecast": null, "lower": null, "upper": null}, "... 29 more, all null ..."],
  "plausibility_check": {
    "forecast_endpoint_change": null,
    "is_extreme_relative_to_history": false,
    "interpretation": "The forecast implies a change of nan over this horizon, which is nan standard deviations below the historical average 30-step change (nan ± nan) -- within the range of moves this series has made before."
  }
}
```

**What It Means:** No error. No exception. No field anywhere named `error`. Just thirty `null` forecasts and, worse, a `plausibility_check` that actively reports `is_extreme_relative_to_history: false` and a prose interpretation that reads as reassuring — "within the range of moves this series has made before" — about a forecast that is not, in any meaningful sense, a forecast at all. The 5 missing days from Chapter 3 propagated straight through the ETS fit as `NaN`, and every downstream computation quietly inherited them rather than refusing to run. This is the most important gotcha in this chapter, and arguably in this book: a *silent* failure that dresses itself up as a normal, unremarkable result is categorically more dangerous than a loud one. Chapter 1's whole framing — deterministic gates for consequential decisions, agent judgment for open-ended reasoning — assumed a deterministic tool either does its job correctly or fails visibly. This one did neither. The lesson isn't "don't trust this tool" — it's "don't trust *any* tool's absence of an error message as proof its output is meaningful," and to keep checking real values, not just checking that a call returned without raising.

## The Fix, and Why It's Chapter 3's Own Finding Put to Use

The fix is exactly what Chapter 3 already told you was missing: interpolate the 5 gaps before doing anything else with this series.

```python
df["value"] = df["value"].interpolate(method="linear")
# n_missing: 5 -> 0
```

Every result for the rest of this chapter runs against this cleaned series. This connects back to something Chapter 1 said in the abstract — carry earlier layers' findings forward — and makes it concrete: Layer 1's `basic_stats` output for this exact series isn't just informational, it's a checklist item that has to be resolved before Layer 3 can be trusted with the same data.

## Full-Series Refit: Why No Holdout This Time

Every `fit_*` call in Part III deliberately withheld the most recent data to score against. `ts-deploy`'s forecast tools do the opposite on purpose: they retrain on the **entire** cleaned series, with nothing held back, because there's nothing left to score a forecast for dates that don't exist yet against. Withholding data here wouldn't buy rigor — it would just throw away real information the deployed model could have used.

One consequence worth flagging explicitly: the `aicc` this layer reports is **not** comparable to Chapter 9 or 10's `fit_ets`/`fit_sarima` `aicc` for the same series, even though it's the same statistic with the same name. The training set size and the fitted parameters can both differ between a backtest-split fit and a full-series fit — the tool's own docstring says so, and this chapter's real numbers below (`aicc=867.67` for ETS, `aicc=1281.61` for SARIMA) exist to be read on their own terms, not stacked next to Part III's numbers as if they were the same measurement.

## Comparing Interval Strategies, For Real

**Prompt:**
> Deploy naive, ETS, and SARIMA forecasts, 30 days out. How do their prediction intervals compare?

**What Comes Back** (real results, day-30 endpoint only, cleaned series):

| Model | Day-30 forecast | Day-30 interval | Width |
|---|---|---|---|
| Seasonal-naive (analytic) | 271.33 | [207.68, 334.98] | 127.30 |
| ETS (simulated) | 238.56 | [70.72, 397.66] | 326.95 |
| SARIMA (analytic) | 251.09 | [217.45, 284.73] | 67.28 |

**What It Means:** This book's outline expected the naive floor to be the honest, dramatically-widest interval of the three — the textbook "admit you know nothing" baseline. That's not what actually happened here. ETS's *simulated* interval is more than twice as wide as naive's analytic one by day 30, and nearly five times wider than SARIMA's. It's worth understanding why rather than just noting it: naive's interval formula scales a single fixed residual standard deviation by `sqrt(horizon)` — smooth, bounded growth by construction. ETS's interval comes from actually simulating hundreds of future paths forward through a model with its own trend and seasonal dynamics, and letting those paths' own spread at day 30 define the interval — which can genuinely diverge much further than a simple textbook scaling formula would, especially for a model whose components (as Chapter 9 already found, on a different series) aren't necessarily well-calibrated to begin with. SARIMA's analytic interval, by contrast, comes out narrowest — not because it's more careful, but because it's a direct property of this specific fitted state-space model's own math on this specific series. None of the three interval-construction strategies is inherently the most honest one. Which is widest is an empirical question, answered fresh every time, not something to assume in advance from which model sounds simplest.

## The Recursive Forecast, Compared at Two Horizons

**Prompt:**
> Deploy a gradient-boosted-trees forecast at 5 days and at 90 days. Does the interval actually reflect the extra uncertainty of forecasting 90 days out using the model's own earlier predictions?

**What Comes Back** (real results; the tool's own `caveat`, then the interval width at the start of each horizon and the end of the 90-day one):

> *"This is a RECURSIVE multi-step forecast: each prediction feeds back in as a lag feature for later steps, so errors can compound as the horizon grows... The interval above is quantile-regression-based, not derived from this same recursive process... treat it as a rough guide, not a rigorous bound on the compounding risk specifically."*

```
5-day horizon,  day 5:  forecast 217.90, interval width  63.47
90-day horizon, day 90: forecast 208.94, interval width  59.71
```

**What It Means:** The interval barely moved — `63.47` wide at day 5, `59.71` wide at day 90, eighty-five days later. That's the caveat above made concrete: this interval genuinely does not grow with the compounding risk of forecasting recursively off the model's own earlier guesses. And the point forecast itself is worth a second look too: the 90-day trajectory doesn't visibly blow up or drift somewhere absurd — inspecting the final five days (`267.6, 242.0, 227.9, 210.3, 208.9`) shows almost the same weekly oscillation shape as the first five days (`233.7, 267.5, 261.6, 242.2, 217.9`). That's not reassuring once you understand *why* it happens: with only `lag_1`, `lag_7`, and `lag_14` as features and (per Chapter 11's real finding on a different series) `lag_7` dominating everything else, this model doesn't really extend a trend or reason about the future — it recursively re-plays the most recent strong repeating pattern it has memory of, forever. That's a perfectly reasonable forecast if the future keeps looking like the recent past. It is *not* a model that will visibly warn you the moment that assumption breaks — it'll keep confidently repeating the old pattern instead, with an interval that, as just shown, doesn't widen to reflect the extra distance from anything real.

And the `plausibility_check` on this 90-day forecast passes cleanly: `is_extreme_relative_to_history: false`, z-score `-0.32`, "within the range of moves this series has made before." That's the sharpest version of this chapter's third learning objective: a clean plausibility check is not a certificate of trustworthiness. It's checking one specific thing — does the *endpoint* look like a move this series has made before — and a model that's just replaying an old pattern will, almost by definition, pass that particular check every time, right up until the moment the real future stops cooperating.

## What's Next

Mojito inventory now has four real, deployed forecasts, each honest about what it does and doesn't know — including, in GBT's case, honest about a blind spot its own interval can't see around. Chapter 15 asks the natural next question: when more than one of these looks reasonable, should you actually pick just one?
