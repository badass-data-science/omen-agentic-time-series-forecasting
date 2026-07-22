# Omen: Testing & Learning Prompts

A set of ready-to-use prompts for exercising each of Omen's five layers and
for learning both how this toolkit works and how the underlying forecasting
concepts work in general. Each prompt is written as something you'd actually
type to an agent with the `ts-analyst`/`ts-forecaster`/`ts-deploy`/
`ts-monitor`/`ts-retrain` MCP servers and skills installed (see the project
`README.md`'s Setup section).

A few notes before diving in:

- Most prompts assume you have a series CSV to point at. If you don't have
  one yet, ask the agent to generate synthetic data first -- `ts-analyst`
  exposes exactly this as `generate_synthetic_data`, a thin wrapper around
  `omen.data_prep`'s `generate_synthetic_series` (the same generator the
  project's own tests and blog posts use) -- several prompts below do this
  explicitly.
- Prompts are meant to be adapted, not copy-pasted verbatim forever --
  swap in your own CSV path, horizon, or thresholds once you're comfortable.
- Each layer's prompts move roughly from "does this basic thing work" toward
  "here's a specific behavior/caveat worth understanding," so working
  through a section in order is a reasonable way to actually learn the
  layer, not just poke at it.
- See `AGENTS.md` and the layer's own `SKILL.md` if a prompt's result
  surprises you -- most of this toolkit's non-obvious behavior is
  deliberate and documented, not a bug.
- A few prompts in each section (except Layer 5, which has none) call a
  `plot_*` tool. These return a real inline image, rendered in the same
  turn by any MCP client that supports it, alongside a small JSON status
  dict -- never a replacement for the layer's own numeric tools, just a
  faster way to see what those numbers already established.

## Layer 1 — `ts-analyst`

1. Generate a synthetic demand series and run `basic_stats` on it. What's the mean, and how wide is its confidence interval?
2. Run `check_stationarity` on that series. Do the ADF and KPSS tests agree? If they disagree, what does that specific combination actually mean?
3. What is mean-reversion half-life, and why does `check_stationarity` report a confidence interval on it instead of just the point estimate?
4. Use `detect_seasonality_period` to find the dominant seasonal cycle in the series without telling the tool what period to expect first.
5. Run `acf_pacf_summary` and explain why lag 1 can rank as more statistically significant than lag 7, even on a series with obvious weekly seasonality.
6. Compare `detect_anomalies_zscore` and `detect_anomalies_robust_zscore` on a series with an injected spike -- do they agree on which point is the anomaly, and by how much?
7. Ask `ts-analyst` to explain, in plain language, why a rolling z-score can under-report the severity of the very anomaly that's inflating its own rolling window.
8. Run `detect_changepoints` on a series with a known level shift partway through. Does it find the shift? What effect size (Cohen's d) does it report for it?
9. What's the difference between an anomaly and a changepoint according to `ts-analyst`'s own tools? Can a series have one without the other?
10. Feed `ts-analyst` a pure random walk (no real seasonality or trend) and see whether `check_stationarity` correctly identifies it as non-stationary.
11. Ask `ts-analyst` to summarize its findings on a series as if writing a report for someone who has never seen the data -- including at least one caveat.
12. Run `detect_seasonality_period` with a very narrow `min_period`/`max_period` range that deliberately excludes the series' true seasonal cycle. What happens?
13. Ask for `plot_series` on a series with missing values. Do the gaps show up as real breaks in the line, or does the plot silently smooth over them the way a naive charting tool might?
14. Run `plot_acf_pacf` on a series and compare what's actually visible in the picture to what `acf_pacf_summary`'s own effect sizes already told you -- does the shaded Bartlett band visibly widen as the lag grows?
15. Use `plot_periodogram` with a narrow `min_period`/`max_period` range on a series with a strong trend. Does the marked "top in-range candidate" period differ from the marked "global strongest" one -- and if the trend is strong enough, can the true signal even survive within the plausible range?
16. Run `plot_anomalies` after `detect_anomalies_robust_zscore` flags more than one point. Do all the flagged points look equally dramatic in the picture, or do some barely register against the ordinary noise?
17. Ask for `plot_changepoints` on a series with both an injected single-day spike and a lasting level shift. Does the plot mark the spike, the shift, or both -- and does that match what a changepoint detector is actually supposed to find?
18. Compare `plot_seasonal_decomposition`'s residual panel by eye against the numeric `residual_variance_share`. Does a small share actually look small and pattern-free in the picture, or does the panel reveal structure the number alone didn't make obvious?

## Layer 2 — `ts-forecaster`

1. Split a series into training and holdout windows and explain why every candidate model needs to beat the naive and seasonal-naive baselines, not just have a low error number.
2. Fit ETS and SARIMA on the same series and compare their backtest MAPE. Is the difference statistically significant according to `diebold_mariano_test`, or could it just be noise?
3. Run `fit_gradient_boosted_trees` and explain why its backtest isn't directly comparable to `fit_ets`'s or `fit_sarima`'s, even when the MAPE numbers look similar.
4. Ask `ts-forecaster` to report a SARIMA fit's `aicc` and explain why AICc is preferred over plain AIC when the training window is only a few hundred points.
5. Use `rolling_origin_backtest` on a candidate model. Does its MAPE stay stable across different origins, or does it swing a lot? What would that instability mean if you deployed it?
6. Run `search_sarima_orders` with a fixed differencing order (informed by Layer 1's stationarity findings) and check whether the best-AICc candidate also has white-noise residuals.
7. Fit SARIMA and check its `backtest_interval_coverage`. Does the nominal 95% interval actually cover close to 95% of the holdout, or is it miscalibrated?
8. Explain what the Ljung-Box test is checking for in a model's residuals, and what it means if a fitted model fails it.
9. Compare `seasonal_naive` against a fitted SARIMA model with `diebold_mariano_test`. Can a "fancier" model actually lose to a trivial baseline?
10. What's the difference between `n_lags=0` and the default automatic lag selection in `diebold_mariano_test`, and when would you deliberately choose each?
11. Run `fit_ets` and look at the bootstrap confidence interval on its backtest MAPE. How wide is it on a 30-point holdout, and what does that width tell you?
12. Ask `ts-forecaster` to recommend a model for a series and defend the choice using real error metrics and residual diagnostics, not just "lowest error."
13. Deliberately fit a badly-misspecified SARIMA order (e.g. `order=[0,0,0]`) and see how the residual diagnostics flag the problem.
14. Run `plot_backtest` on both naive's and seasonal-naive's holdout arrays for the same series. Which line visibly tracks the actual values more closely, and does that match the MAPE gap between them?
15. Use `plot_rolling_origin` on a `rolling_origin_backtest` result. Does any bar visibly break outside the shaded mean +/- 1 std band -- and is it the bar you'd have guessed just from reading the origins in order?
16. Run `plot_search_sarima_orders` on a `search_sarima_orders` result where the top two candidates are within a point of each other on AICc. Does the picture make that margin obvious at a glance, or does it still look like a clear winner until you check the axis?

## Layer 3 — `ts-deploy`

1. Deploy a naive forecast alongside your chosen model's real forecast. How much wider is the naive forecast's confidence interval, and why should it be?
2. Generate a 90-day `forecast_gradient_boosted_trees` forecast and read its `caveat` field. What specifically does it warn about, and does that warning matter more at day 5 or day 90?
3. Ask `ts-deploy` to explain why `forecast_naive`'s prediction interval sometimes doesn't exist at all (point-forecast-only).
4. Run `forecast_sarima` and check its `plausibility_check` field. Does the forecast's implied change look extreme relative to the series' own history?
5. Combine SARIMA and ETS into one forecast using `forecast_ensemble` with equal weights. Is the combined interval narrower or wider than either model's own interval alone, and why?
6. Weight `forecast_ensemble` heavily toward gradient-boosted trees and check whether the recursive-compounding caveat still shows up in the combined result.
7. Feed `ts-deploy` a very short, noisy series and see whether `plausibility_check` flags the resulting forecast as extreme relative to history.
8. Compare `forecast_ets`'s and `forecast_sarima`'s `aicc` values on a full-series refit. Why don't these match the `aicc` values `ts-forecaster` reported earlier in the pipeline?
9. Generate `forecast_gradient_boosted_trees`'s `feature_importances` with a bootstrap confidence interval. Which lag feature has the widest uncertainty, and why might that be?
10. Ask `ts-deploy` what would change about a forecast's reliability if a recent anomaly in the series turns out to have been a one-off promotion rather than a permanent shift.
11. Request a forecast with an unusually long horizon (say 120 days) and observe how the tool truncates the reported table for readability.
12. Run `forecast_naive` with both `"naive"` and `"seasonal_naive"` methods on the same series and compare their implied uncertainty.
13. Ask `ts-deploy` to write a short deliverable report that leads with the forecast itself, not the methodology, for a case where no prediction interval is available.
14. Deploy a forecast with `plot_forecast` and look at the shaded interval band's width at day 1 versus the end of the horizon. Does it visibly widen the way you'd expect, or barely change at all?
15. Run `plot_forecast` on `forecast_gradient_boosted_trees` results at two very different horizons (e.g. 5 days and 90 days). Does the interval band visibly grow to reflect the longer horizon's compounding-error risk, or does it stay about the same width regardless -- and what does that tell you about how much to trust it at the longer horizon?

## Layer 4 — `ts-monitor`

1. Once real data exists past a forecast's start date, compare that forecast against reality. What's the elapsed-horizon MAPE, and how wide is its bootstrap confidence interval?
2. Check a forecast's interval coverage against reality. If 100% of the elapsed points fell inside the interval, is that actually as reassuring as it sounds given how few points there are?
3. Run `detect_data_drift` on a series with an ongoing trend but no injected anomaly. Does it flag drift? What does that tell you about the test's blind spot?
4. Ask `ts-monitor` to report the effect size (Cohen's d) alongside a drift flag, not just the p-value. How does that change how alarming the finding feels?
5. Run `rolling_drift_check` across several windows. Does the drift show up consistently (`persistent_drift: true`) or only in one isolated check?
6. Feed `recommend_retraining` a case where the point estimate says "not degraded" but the bootstrap CI straddles the degradation threshold. What does it flag?
7. Use `residual_outliers` (part of `compare_forecast_to_actuals`) to figure out whether a bad elapsed-horizon MAPE is being driven by one unusual day or a systematic miss.
8. What are the four possible `recommend_retraining` verdicts, and what combination of signals produces each one?
9. Run `compare_forecast_to_actuals` on a forecast that has no prediction interval at all. What does the `interval_coverage` field report in that case?
10. Ask `ts-monitor` to explain why `interval_coverage`'s `well_calibrated` threshold is deliberately kept at 15 percentage points instead of something tighter.
11. Inject a large, obvious level shift into a series' most recent window and compare `detect_data_drift`'s Cohen's d against the same check on the unmodified series.
12. Ask `ts-monitor` for a full monitoring report and confirm it hands off to `ts-retrain` when the verdict is `retrain_now`, rather than trying to redeploy anything itself.
13. Run `plot_forecast_vs_actuals` on a forecast checked against a month of real observations that include one unusual day. Does that day visibly break outside the interval band, or does it get swallowed by ordinary noise the way a milder miss might?
14. Use `plot_drift` on a series with only an ongoing trend (no injected incident), then again on a version with a real injected shift on top of it. Do both plots look "flagged," and can you actually tell which one is the more serious problem just from the picture -- or only once you compare the two side by side?
15. Run `plot_rolling_drift` across several walk-forward checks. Does any single bar break from an otherwise steady pattern, and what would that suggest about roughly *when* something changed, that a single most-recent `detect_data_drift` call couldn't have told you on its own?

## Layer 5 — `ts-retrain`

1. Ask `ts-retrain` to load the deployment manifest for a series that has nothing deployed yet. What happens, and what does it suggest you do next?
2. Record a deployment, then ask `ts-retrain` to compare a slightly-better retrained candidate against it. Does a 3% improvement clear the default redeploy threshold?
3. Feed `compare_candidate_to_deployed` a candidate whose bootstrap CI straddles the improvement threshold. Does it still recommend redeploying, and how does it caveat that?
4. Give both the candidate's and the deployed model's backtest metrics their own confidence intervals. Does the combined improvement range come out wider than using the candidate's CI alone?
5. Try calling `execute_redeploy` without passing `confirmed=True`. What happens, and why is there no default that takes action?
6. Redeploy a model with `confirmed=True` and check what `previous_deployment` reports afterward.
7. Try `execute_redeploy` with `autonomous=True` on a series that has never been authorized for autonomous mode. What error comes back?
8. Call `authorize_autonomous_mode` for a specific series, then retry the same autonomous redeploy. Does it succeed this time?
9. Revoke autonomous-mode authorization and immediately try another autonomous redeploy. Does it correctly refuse again right away?
10. Ask `ts-retrain` whether autonomous mode is currently authorized for a series using `check_autonomous_mode`, instead of relying on what you remember being told earlier in the conversation.
11. Ask `ts-retrain` to explain, in its own words, why the deployment manifest and the autonomous-mode authorization record are kept in two separate files instead of one.
12. Have `ts-retrain` re-run `ts-analyst` and `ts-forecaster` on an updated series as part of a full retrain cycle, and report whether the recommended approach changed from before.
13. Ask `ts-retrain` what `should_redeploy: false` actually implies about the original problem `ts-monitor` flagged. Does retraining alone always fix a genuine regime change?
