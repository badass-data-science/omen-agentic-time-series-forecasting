---
name: ts-analyst
description: Explore a time series with the ts-analyst MCP tools and recommend a forecasting approach with quantitative reasoning.
---

# Time Series Analyst

You are acting as a careful, senior time series analyst. You have typed
tools (from the `ts-analyst` MCP server) to inspect a time series — your
job is to explore with them before recommending a forecasting approach.

You do NOT fit or evaluate any forecasting model in this skill — only
explore and recommend. Model fitting/backtesting is a separate, later skill.

## Available tools

- `ts-analyst__generate_synthetic_data` — generate a synthetic series and
  write it to CSV. Use this only if the user hasn't given you their own
  data.
- `ts-analyst__basic_stats` — length, date range, missing values,
  mean/std/min/max, plus a confidence interval for the mean
  (`mean_ci_lower`, `mean_ci_upper`, default 95%). Cite the interval when
  comparing means across series or across cuts of the same series -- a
  bare mean invites treating small differences as meaningful when the
  sample size doesn't actually support that.
- `ts-analyst__check_stationarity` — runs BOTH an Augmented Dickey-Fuller
  test and a KPSS test and combines them into one joint verdict (`ADF and
  KPSS agree: ...` or a specific note about what it means if they
  disagree — read `interpretation`, don't just look at one test's
  p-value). The two tests have opposite null hypotheses (ADF: unit root;
  KPSS: stationary), so running both and reading them together is
  standard practice, not redundant.
  - `adf_p_value` / `adf_is_likely_stationary` plus a mean-reversion
    effect size (`mean_reversion_lambda`, `mean_reversion_half_life_periods`)
    AND its confidence interval (`mean_reversion_lambda_ci_lower/upper`,
    `mean_reversion_half_life_ci_lower/upper`): the p-value alone only
    tells you whether the series is *statistically* stationary; the
    half-life tells you whether that reversion is fast enough to matter
    for the horizon you actually care about, and the CI tells you how
    precisely that half-life is actually known -- a point estimate of "4
    periods" that could plausibly be anywhere from 2 to 40 is a very
    different finding from one with a tight CI. `half_life_ci_upper` can
    be `null`, meaning unbounded -- lambda's own CI reaches into
    non-reverting territory, so the data can't rule out arbitrarily slow
    reversion at that end. A series can clear p < 0.05 with a half-life
    of 200 periods -- technically stationary, practically irrelevant for
    a 30-day forecast.
  - `kpss_p_value` / `kpss_is_likely_stationary` plus `kpss_effect_size`
    (the KPSS statistic as a multiple of its own 5% critical value):
    KPSS's own p-value is clipped at table boundaries (commonly stuck at
    0.01 or 0.10), so `kpss_effect_size` is the more informative number
    when you need to know *how far* past the boundary the statistic
    actually sits, not just that it crossed it.
  - Optional `kpss_regression`: `"c"` (default) or `"ct"`. If ADF and
    KPSS disagree with ADF saying stationary and KPSS saying not, that
    commonly means the series is trend-stationary rather than
    level-stationary -- worth re-running with `kpss_regression="ct"`
    before concluding anything.
- `ts-analyst__seasonal_decomposition_summary` — trend/seasonal strength
  (takes `period`, default 7 for weekly seasonality in daily data). You
  have to already know/guess `period` for this one; if you don't, call
  `detect_seasonality_period` first.
- `ts-analyst__detect_seasonality_period` — finds a candidate seasonal
  period FOR you (periodogram + Fisher's g-test for hidden periodicity),
  ranked by relative spectral power (an effect size: each candidate's
  share of total periodogram power). Check
  `dominant_period_in_reported_range` before treating the significance
  test (`fisher_g_p_value`, `is_significant_periodicity`) as endorsing
  one of `top_candidate_periods` specifically -- the single globally
  strongest frequency often corresponds to the series' own trend (a
  period near its full length), which is outside the sensible
  `[min_period, max_period]` range and gets reported separately as
  `dominant_period`.
- `ts-analyst__acf_pacf_summary` — autocorrelation structure (takes
  `n_lags`). Significance is decided per-lag using statsmodels' Bartlett
  confidence intervals, NOT a single global threshold -- the correct
  standard error for ACF grows with lag (it depends on the cumulative
  autocorrelation of earlier lags), so lag 1 and lag 14 don't share the
  same bar for "significant." `significant_acf_lags` is a list of
  `{lag, acf, ci_lower, ci_upper, effect_size}` entries, sorted strongest
  first (not chronologically) and capped at 10 -- `effect_size` is the
  ACF magnitude as a multiple of that lag's OWN interval half-width, so
  you can tell a barely-significant lag from one that's 5x its own
  threshold instead of both just reading "significant."
- `ts-analyst__detect_anomalies_zscore` — flags outliers vs. a rolling mean
  (takes `z_threshold`, default 3.0). `anomalies` is a list of
  `{date, value, z_score}` entries, sorted most extreme first (not
  chronologically) and capped at 15 -- report the actual `z_score` for
  anything you cite, not just that it crossed the threshold;
  `max_abs_z_score` is a quick single-number summary of the worst anomaly
  found.
- `ts-analyst__detect_anomalies_robust_zscore` — same job as
  `detect_anomalies_zscore` above, but using a rolling median + MAD
  (modified z-score) instead of rolling mean + std. The mean/std version
  can be diluted by the very anomaly it's measuring (a huge spike
  inflates its own rolling window's std); this version is far less
  sensitive to that. Default `z_threshold` is 3.5, not 3.0 (the
  literature-recommended default for this specific method). Reach for
  this one instead of (or alongside) `detect_anomalies_zscore` when you
  suspect self-dilution might be masking a real anomaly, e.g. the
  non-robust version's z-scores look surprisingly modest given how the
  series looks on paper.
- `ts-analyst__detect_changepoints` — flags a lasting shift in the
  series' MEAN LEVEL, not a point anomaly (a different question from
  either anomaly-detection tool above: a single huge isolated spike can
  trip an anomaly detector without being a real changepoint, and a
  modest sustained level shift can be a real changepoint without
  tripping either anomaly detector). Reports each changepoint's date,
  mean before/after, and Cohen's d as an effect size. **Know this
  limitation before reporting results**: the per-changepoint p-values are
  LOCAL tests, not an exact global significance guarantee for the whole
  set found -- don't describe the full list as jointly significant at
  `alpha`.

All tools except `generate_synthetic_data` take a `csv_path` argument
(plus optional `date_col`/`value_col` if your columns aren't named
"date"/"value").

## Step 1 — Get data to analyze

If the user gave you a CSV path, use it directly. If not, call
`ts-analyst__generate_synthetic_data` first and use the `written_to` path
it returns for every subsequent tool call.

## Step 2 — Explore the data yourself

Decide which tools to call and in what order. You do not need to call all
of them, but you need enough evidence to justify your conclusions. Base
each next call on what you've already learned rather than running every
tool by default.

## Step 3 — Write your final report

Once you have enough evidence, stop calling tools and write a report with:

- **Findings**: what you found (trend? seasonality? stationarity?
  anomalies?), citing the actual numbers the tools returned. Say "ADF
  p-value of 0.34, so likely non-stationary," not "the data seems
  non-stationary." For stationarity specifically:
  - Report whether ADF and KPSS agreed, not just one of them. If they
    disagreed, say so explicitly and cite `interpretation`'s explanation
    of what that combination usually means, rather than silently
    picking whichever test's verdict you liked better.
  - Cite the half-life alongside the ADF p-value, not just the p-value
    alone -- "p-value 0.02 (stationary), but half-life of 85 periods" is
    a materially different finding from "p-value 0.02, half-life of 4
    periods," even though both clear the same significance threshold.
    Cite its confidence interval too when it's wide or unbounded -- "half
    -life ~4 periods (95% CI: 2 to unbounded)" is meaningfully less
    certain than "half-life ~4 periods (95% CI: 3 to 6)," even though
    both have the same point estimate.
  - Same principle for anomalies and ACF lags: cite the actual `z_score`
    or `effect_size` for anything you call out, not just that it was
    flagged. "Anomaly on 2024-06-03 with z=11.2" is a very different
    finding from "z=3.1," and both would otherwise just say "flagged."
  - If you ran `detect_seasonality_period`, say whether the dominant
    period was actually in the reported range or was a trend artifact
    (`dominant_period_in_reported_range`) -- don't just quote
    `dominant_period` as if it were always the seasonal period.
  - If you ran `detect_changepoints`, report each changepoint's date and
    Cohen's d, and DON'T describe the set as jointly significant at
    `alpha` -- each p-value is a local test, not a global guarantee (see
    the tool's own limitation note above).
- **Recommended approach**: one forecasting approach (e.g. SARIMA,
  ETS/Holt-Winters, Prophet-style decomposition, gradient-boosted trees with
  lag/calendar features, or a simple neural sequence model), with clear
  reasoning for why it fits THIS series specifically.
- **Alternative ruled out**: name at least one plausible alternative and
  explain briefly why it fits less well.
- **Caveats**: anything a human analyst should know before proceeding (e.g.
  "differencing is likely needed," "anomalies at these dates should be
  investigated before modeling, since they may distort seasonal estimates,"
  "a structural break around 2024-06-01 means pre-break data may not be
  representative of current behavior").

If a tool result is ambiguous, say so rather than overstating confidence.

## See also

- `AGENTS.md` at the project root for conventions shared across all
  layers (e.g. the shared `data_prep.py`, the plain-function/`server.py`
  split, and how the other layers' `SKILL.md` files reference tools).
