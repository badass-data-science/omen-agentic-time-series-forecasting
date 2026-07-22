# Appendix B: Tool Reference Table

Every MCP tool this book actually called, grouped by layer, in the order each layer's chapters introduced them. Use this as a fast lookup once you're working with your own data instead of the book's running examples — for full parameter details, the tool's own docstring (visible to any MCP client, including whatever agent you're using) is more current than this table will ever be.

## Layer 1 — `ts-analyst`

| Tool | What it does | Chapter(s) |
|---|---|---|
| `generate_synthetic_data` | Writes a synthetic demand series to CSV — useful for a first connectivity check with no data of your own on hand. | 2 |
| `basic_stats` | Mean, standard deviation, and a confidence interval, with missing values excluded and counted explicitly. | 2, 3 |
| `check_stationarity` | ADF and KPSS tests together, plus mean-reversion half-life with its own confidence interval. | 4 |
| `seasonal_decomposition_summary` | Additive trend/seasonal/residual decomposition with strength scores for each component. | 5 |
| `detect_seasonality_period` | Finds a dominant seasonal cycle via periodogram, without needing the period specified in advance. | 5 |
| `acf_pacf_summary` | Autocorrelation and partial autocorrelation at each lag, with a Bartlett's-formula-based significance threshold. | 6 |
| `detect_anomalies_zscore` | Flags points far from a rolling mean/standard deviation — vulnerable to self-dilution from the anomaly it's trying to catch. | 7 |
| `detect_anomalies_robust_zscore` | The same idea, built on a rolling median and MAD instead — more robust, with its own documented edge case. | 7 |
| `detect_changepoints` | Finds a structural shift in a series' level using a CUSUM statistic and permutation test. | 7 |

## Layer 2 — `ts-forecaster`

| Tool | What it does | Chapter(s) |
|---|---|---|
| `fit_naive_baselines` | Backtests flat and seasonal naive forecasts — the floor every real model has to beat. | 8 |
| `fit_ets` | Backtests exponential smoothing (Holt-Winters), with AIC/AICc, residual diagnostics, and interval coverage. | 9 |
| `fit_sarima` | Backtests SARIMA at a specified `(p,d,q)(P,D,Q,s)` order, with the same diagnostics as `fit_ets`. | 10 |
| `search_sarima_orders` | An advisory grid search over `p`/`q`/`P`/`Q` (never `d`/`D`, which must be supplied), ranked by AICc. | 10 |
| `fit_gradient_boosted_trees` | Backtests gradient-boosted trees on lag and calendar features, one-step-ahead, with feature importances. | 11 |
| `diebold_mariano_test` | A paired significance test for whether two models' backtest errors differ meaningfully. | 12 |
| `rolling_origin_backtest` | Repeats a backtest at several walk-forward origins to measure performance stability, not just its average. | 13 |

## Layer 3 — `ts-deploy`

| Tool | What it does | Chapter(s) |
|---|---|---|
| `forecast_naive` | A deployed naive/seasonal-naive forecast beyond the last observation, with an analytic interval. | 14 |
| `forecast_ets` | A deployed ETS forecast, refit on the entire series, with a simulated prediction interval. | 14 |
| `forecast_sarima` | A deployed SARIMA forecast, refit on the entire series, with an analytic confidence interval. | 14 |
| `forecast_gradient_boosted_trees` | A deployed, recursive multi-step GBT forecast, with a quantile-regression-based interval and an explicit compounding-error caveat. | 14 |
| `forecast_ensemble` | Combines two or more of this layer's own forecasts into one weighted forecast, with variance-combined intervals. | 15 |

## Layer 4 — `ts-monitor`

| Tool | What it does | Chapter(s) |
|---|---|---|
| `compare_forecast_to_actuals` | Matches a deployed forecast against real subsequent observations, with error CIs, interval-coverage CIs, and residual-outlier detection. | 16 |
| `detect_data_drift` | Compares a recent window against a reference window for a distributional shift, reporting both p-values and effect sizes. | 17 |
| `rolling_drift_check` | Repeats `detect_data_drift` at several walk-forward points to distinguish a sustained shift from a one-off blip. | 17 |
| `recommend_retraining` | A deterministic verdict (`retrain_now` / `investigate` / `monitor_closely` / `no_action_needed`) combining degradation and drift signals. | 17 |

## Layer 5 — `ts-retrain`

| Tool | What it does | Chapter(s) |
|---|---|---|
| `record_deployment` | Persists what's currently deployed — model, params, backtest metrics — as a durable, inspectable manifest. | 18 |
| `load_deployment_manifest` | Reads back whatever `record_deployment` last wrote for a series. | 18 |
| `compare_candidate_to_deployed` | A deterministic redeploy verdict requiring a meaningful improvement threshold, with confidence-aware interval arithmetic. | 18 |
| `execute_redeploy` | The one tool that actually changes a live deployment — refuses without `confirmed=True`, and refuses `autonomous=True` without a standing authorization. | 19 |
| `authorize_autonomous_mode` | Records a standing, unattended-redeploy authorization for a specific series. | 19 |
| `revoke_autonomous_mode` | Removes that authorization — safe to call even if none exists. | 19 |
| `check_autonomous_mode` | Reads back whatever authorization state is currently on record for a series. | 19 |
