# Chapter 9: Smoothing Things Over — Exponential Smoothing (ETS)

Death-Ray Revenue's naive baseline, from Chapter 8, landed at 17.46% MAPE. That's the number every model in this chapter and the next two has to beat convincingly, not just technically. This chapter fits the first real model in this book — exponential smoothing, also called ETS or Holt-Winters — and along the way finds a genuinely surprising real result: the model **AIC** (the Akaike Information Criterion, a fit-quality statistic explained properly later in this chapter) likes best is not the model that actually forecasts best, and the diagnostic that catches this isn't the one you'd expect.

## What ETS Actually Smooths

Exponential smoothing builds a forecast from a small number of components, each updated recursively as new data arrives: a **level** (roughly, "what's normal right now"), optionally a **trend** (is that level drifting), and optionally a **seasonal** pattern layered on top. Each component can be combined **additively** (it adds a fixed amount) or **multiplicatively** (it scales the level by a percentage) — and a trend can additionally be **damped**, meaning its influence is deliberately weakened the further out the forecast reaches, on the theory that an early trend shouldn't be trusted to continue forever unchecked.

## The First Real Model, and a Real Surprise

**Prompt:**
> Fit ETS on the death-ray revenue series. Do the residuals look like white noise, and does its prediction interval actually cover close to 95% of the holdout?

**What Comes Back** (a real result, additive trend and seasonal components, `seasonal_period=7` — the same untested default Chapter 8 already found unhelpful for this series):

```json
{
  "params": {"trend": "add", "seasonal": "add", "seasonal_period": 7, "damped_trend": false},
  "aic": 486.76, "aicc": 494.35,
  "backtest_metrics": {"mae": 1477.07, "mape_pct": 4.62, "mape_pct_ci_lower": 3.87, "mape_pct_ci_upper": 5.44},
  "backtest_interval_coverage": {
    "empirical_coverage_pct": 36.67, "nominal_confidence_pct": 95.0, "well_calibrated": false,
    "interpretation": "36.67% of holdout actuals fell within their backtest prediction interval... shouldn't be trusted at face value if this model is deployed."
  },
  "residual_diagnostics": {
    "ljung_box_p_value": 0.3862, "ljung_box_effect_size": 0.5812, "residuals_look_like_white_noise": true
  }
}
```

**What It Means, Part One — the Good News:** `4.62%` MAPE is a dramatic improvement over naive's `17.46%`, and the residual diagnostics back it up: `residuals_look_like_white_noise: true`, with the **Ljung-Box test** — which asks whether a sequence of residuals still contains leftover autocorrelation a good model shouldn't have left behind, rather than looking like patternless noise — sitting comfortably under its own critical value (`effect_size: 0.58`, well below the `1.0` line that would mean trouble). This model isn't leaving obvious structure on the table. On error alone, this looks like an easy win.

**What It Means, Part Two — the Bad News:** `backtest_interval_coverage` says only `36.67%` of holdout points actually fell inside their nominal 95% interval. That's not a rounding error — the interval is badly, badly too narrow, and the tool says so in plain language rather than letting a low error number distract from it. A model with excellent point accuracy and a badly miscalibrated interval is not a model you can hand someone an honest range from. This chapter's real work starts here, not at the MAPE number.

## AIC, AICc, and a Trap Worth Walking Into on Purpose

Before chasing the calibration problem, it's worth understanding the two fit statistics sitting right there in the output. **AIC** balances model fit against model complexity — lower is better, and it penalizes adding parameters that don't earn their keep. **AICc** is a small-sample correction to AIC (Hurvich & Tsai, 1989): AIC's own bias grows as the parameter count approaches the training sample size, which is exactly the regime this backtest is in — 40 training weeks is not a lot of data to be estimating several smoothing parameters from. Here, `aicc` (494.35) sits meaningfully above `aic` (486.76) — a gap of nearly 8 points, big enough that trusting the uncorrected AIC on a window this size would be a mistake.

Now the trap, walked into deliberately: what happens if the trend is damped instead of left to run freely?

**What Comes Back** (real result, `damped_trend: true`, everything else unchanged):

```json
{
  "params": {"trend": "add", "seasonal": "add", "seasonal_period": 7, "damped_trend": true},
  "aic": 479.52, "aicc": 487.11,
  "backtest_metrics": {"mae": 3040.42, "mape_pct": 9.50},
  "backtest_interval_coverage": {"empirical_coverage_pct": 6.67, "well_calibrated": false}
}
```

**What It Means:** By AICc, this is the *better* model — `487.11` versus the non-damped version's `494.35`. By everything that actually matters for using the forecast, it's worse across the board: MAPE more than doubles, to `9.50%`, and the prediction interval's calibration collapses further, to `6.67%` coverage. An automated "always pick the lowest AICc" rule would have confidently handed you the *worse* forecasting model here. This is the same lesson Chapter 10 demonstrates again, independently, with SARIMA's own order search — worth noticing now, the first time it shows up, rather than treating it as a SARIMA-specific quirk later.

## Fixing the Interval, Not Just Noticing It's Broken

Here's where `backtest_interval_coverage` earns its keep as a real diagnostic rather than a formality. Both models so far assumed an **additive** seasonal component — a fixed dollar swing added on top of the level, regardless of how large the level has grown. But Death-Ray Revenue has been climbing steadily since Chapter 4, on rental prices that scale with reputation — the kind of growth that plausibly swings by a roughly constant *percentage*, not a constant dollar amount. That's exactly what a **multiplicative** seasonal component represents instead.

**What Comes Back** (real result, `seasonal: "mul"`, trend still additive and undamped):

```json
{
  "params": {"trend": "add", "seasonal": "mul", "seasonal_period": 7, "damped_trend": false},
  "aic": 487.07, "aicc": 494.66,
  "backtest_metrics": {"mae": 1772.87, "mape_pct": 5.55, "mape_pct_ci_lower": 4.70, "mape_pct_ci_upper": 6.52},
  "backtest_interval_coverage": {
    "empirical_coverage_pct": 93.33, "nominal_confidence_pct": 95.0, "well_calibrated": true,
    "interpretation": "93.33% of holdout actuals fell within their backtest prediction interval... interval looks calibrated."
  },
  "residual_diagnostics": {"ljung_box_p_value": 0.2891, "residuals_look_like_white_noise": true}
}
```

**What It Means:** MAPE ticked up slightly, from `4.62%` to `5.55%` — a real cost, not free. In exchange, empirical interval coverage jumped from a badly-broken `36.67%` to a genuinely well-calibrated `93.33%`, within a couple points of the 95% target. AIC and AICc barely moved (`487.07` and `494.66`, essentially tied with the very first model). If you were picking a model by AICc alone, these three candidates would look almost interchangeable. They are not interchangeable at all once you ask "can I trust the interval this model reports" — and that's a question AIC was never built to answer in the first place.

## One Honest Aside About the Interface Itself

While preparing this chapter's examples, an attempt to disable the seasonal component entirely (passing `seasonal: null`, matching what the tool's own docstring describes as a valid option: `"add", "mul", or None`) was rejected outright by the live server with a schema validation error — the deployed tool's parameter type doesn't currently accept a null value, docstring notwithstanding. Worth including rather than quietly working around, because it's a useful reminder in its own right: what an interface's documentation *says* it accepts and what it *actually* accepts at runtime aren't always the same thing, and the honest way to find out is to try it, the same way this book tries to show you rather than just tell you.

## Why the Interval Was Simulated in the First Place

One mechanical note worth knowing before Chapter 10 contrasts it: ETS's prediction interval isn't computed from a closed-form formula. It's built by simulating hundreds of plausible future paths forward from the fitted model and taking percentiles across them — which is also *why* an additive-noise assumption baked into that simulation can produce a badly calibrated interval on a series whose real variance scales with its level, exactly the mismatch this chapter just found and fixed. Simulation can also occasionally fail outright for a given parameter combination; when it does, the tool falls back to a point-forecast-only result rather than erroring out, and says so plainly in `interval_note` rather than leaving you to wonder why the interval fields are missing.

## What's Next

You now have a real, well-calibrated ETS model for Death-Ray Revenue, and — more importantly — direct, hands-on evidence that AIC/AICc, backtest error, and interval calibration can each tell a different part of the story, sometimes even pointing in different directions. Chapter 10 fits SARIMA on the same series and puts the differencing order Chapter 4 already found to direct use, instead of leaving it to another untested default.
