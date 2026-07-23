# Appendix A: Glossary

Every statistical term this book actually used, defined in a sentence or two, cross-referenced to the chapter that first introduced it. This is a lookup companion, not a substitute for reading the chapter — each entry here is deliberately shorter than the real explanation.

**ACF (autocorrelation function).** How correlated a series is with a lagged copy of itself, at each lag. Ch. 6.

**AIC (Akaike Information Criterion).** A model-fit statistic that penalizes added parameters — lower is better — used to compare candidate models without a held-out test set. Ch. 9.

**AICc.** AIC with a small-sample correction (Hurvich & Tsai, 1989) that grows more important as the parameter count approaches the training sample size; can diverge meaningfully from plain AIC on the backtest window sizes this book used throughout. Ch. 9, Ch. 10.

**ADF test (Augmented Dickey-Fuller).** A hypothesis test whose null hypothesis is "this series has a unit root" (is non-stationary) — rejecting it is evidence *for* stationarity. Ch. 4.

**AR / MA (autoregressive / moving-average).** The two building blocks SARIMA's `p` and `q` orders count: an AR term predicts from the series' own past *values*; an MA term predicts from past *forecast errors*. Ch. 6, Ch. 10.

**BIC (Bayesian Information Criterion).** A model-fit statistic like AIC — rewards fit, penalizes added parameters — but with a steeper per-parameter penalty that grows with sample size. Ch. 10.

**Bootstrap confidence interval.** A confidence interval built by resampling the data with replacement many times and looking at the spread of a statistic across those resamples, rather than relying on a closed-form formula. Ch. 8.

**Cohen's d.** A standardized effect size for a difference in means — the difference divided by a pooled standard deviation — that tells you the *magnitude* of a shift, not just whether it's statistically significant. Ch. 7's changepoint detection and Ch. 17's drift detection both use it; Ch. 4's own "effect size" entries (mean-reversion half-life, KPSS-statistic-to-critical-value ratio) are a different, unrelated concept sharing only the name. Ch. 7, Ch. 17.

**Coefficient of variation.** A standard deviation divided by its own mean — used in this book to flag when a model's performance is *unstable* across origins, not just what it averages to. Ch. 13.

**Confirmed / deterministic gate.** A code-level check (not a prose instruction) that a consequential action refuses to run without an explicit flag — this book's running example is `execute_redeploy`'s `confirmed=True` requirement. Ch. 19.

**CUSUM statistic.** A cumulative-sum-based statistic used to detect a changepoint — a shift in a series' underlying level or behavior at a specific point in time, as opposed to a single anomalous observation. Ch. 7.

**Cyclical encoding.** Representing a smooth, repeating calendar cycle (like day-of-year) as a `sin`/`cos` pair instead of a discrete bucket (like a 1-12 month integer) — lets a tree-based model split on continuous position-in-cycle instead of a blunt, jump-discontinuous label. Ch. 11.

**Diebold-Mariano test.** A paired hypothesis test (Diebold & Mariano, 1995) for whether two models' forecast errors on the *same* holdout are significantly different, using a loss differential rather than comparing two error numbers directly. Ch. 12.

**Effect size.** A magnitude measure attached to a statistical test, distinguishing "barely detectable" from "enormous" among results that might otherwise share the same p-value. Ch. 4 and throughout.

**Ensembling / model averaging.** Combining two or more forecasts into one weighted forecast, with the combined uncertainty computed via variance combination under an independence assumption. Ch. 15.

**ETS (exponential smoothing / Holt-Winters).** A forecasting model family built from a level, optional trend, and optional seasonal component, each combinable additively or multiplicatively. Ch. 9.

**Feature importance.** In a tree-based model, a measure of how much a given feature reduced prediction error during training — a statement about predictive usefulness within that specific model, not a causal claim. Ch. 11.

**HAC-robust variance (Newey-West).** A variance estimate that accounts for heteroskedasticity and autocorrelation in a sequence of values — necessary for the Diebold-Mariano test because multi-step forecast errors are typically autocorrelated. Ch. 12.

**Interval arithmetic (worst-case/best-case).** Combining two confidence intervals for a ratio-shaped quantity by evaluating the quantity at the *corners* of the joint uncertainty box (not by adding variances), since a ratio's extrema occur at monotonic corners rather than a symmetric combination. Ch. 18.

**KPSS test (Kwiatkowski-Phillips-Schmidt-Shin).** A stationarity test whose null hypothesis is the *opposite* of the ADF test's — "this series is stationary" — making ADF/KPSS agreement or disagreement itself informative. Ch. 4.

**KS statistic (Kolmogorov-Smirnov).** A test for whether two samples come from different distributions, using each sample's whole shape rather than just its mean — catches a spread or shape shift a t-test on the means alone would miss. Ch. 17.

**Lag feature.** In a supervised-learning framing of forecasting, a feature built from a series' own past values (e.g., "the value 7 days ago") used to predict its future value. Ch. 11.

**Ljung-Box test.** A test for whether a sequence of residuals still contains structure ("looks like white noise" is the desired failure to reject). Ch. 9.

**MAD (median absolute deviation).** A robust measure of spread — the median of the absolute deviations from the median — used as the basis for a modified z-score less sensitive to outliers than a standard deviation-based one. Ch. 7, Ch. 16.

**MAE (mean absolute error).** The average absolute difference between forecast and actual — unlike MAPE, well-defined even when actuals are exactly zero. Ch. 8.

**MAPE (mean absolute percentage error).** Average absolute error as a percentage of the actual value — undefined at an actual value of exactly zero, and excluded points are reported explicitly rather than silently dropped. Ch. 8.

**Mean reversion.** The tendency of a series to drift back toward its own long-run average after moving away from it, rather than wandering off permanently — measured by `mean_reversion_lambda` (the estimated speed of the pull-back) and its derived half-life. Not to be confused with the unrelated "effect size" entries this same tool reports (KPSS-statistic-to-critical-value ratio); see Cohen's d above. Ch. 4.

**Modified z-score.** A robust alternative to a standard z-score, built from the median and MAD instead of the mean and standard deviation (Iglewicz & Hoya, 1993) — degrades in a specific, documented way when half or more of the underlying values are identical. Ch. 7, Ch. 16.

**Naive / seasonal-naive baseline.** The simplest possible forecasts — repeat the last value forever, or repeat the last full seasonal cycle — that every real model has to beat to justify its own complexity. Ch. 8.

**One-step-ahead vs. recursive multi-step evaluation.** Whether a backtest scores a model against true lagged values at every point (easier) or against the model's own earlier predictions feeding forward (harder, allows compounding error) — a distinction this book found genuinely easy to conflate by accident. Ch. 11, Ch. 14.

**PACF (partial autocorrelation function).** Like the ACF, but with the correlation at intermediate lags controlled for — used alongside the ACF to reason about a SARIMA model's `p`/`q` orders. Ch. 6.

**Periodogram.** A decomposition of a series into the relative power of different candidate periods, used to find a dominant cycle without guessing its length in advance — vulnerable to a strong trend overwhelming a real seasonal signal. Ch. 5.

**Persistent drift.** Whether `rolling_drift_check`'s drift signal shows up across most of several rolling windows (a sustained shift) or only a minority of them (more consistent with a one-off blip) — a fraction-flagged threshold distinct from Ch. 13's coefficient-of-variation-based instability check, which measures a different thing (backtest accuracy stability, not drift persistence) with no comparable pass/fail flag of its own. Ch. 17.

**Plausibility check.** An automated comparison of a forecast's implied change against a series' own historical distribution of changes — explicitly documented as a prompt for scrutiny, not a hypothesis test or a verdict. Ch. 14.

**Prediction interval.** A range meant to contain a future observation with some stated probability — built differently by different model families in this book (ETS's simulated paths, SARIMA's analytic state-space formula, GBT's quantile regression), each with a different real failure mode. Notably absent from `fit_gradient_boosted_trees`'s own backtest (Ch. 11) — GBT only gets one once deployed (Ch. 14). Ch. 9, Ch. 10, Ch. 14.

**Quantile regression.** A model trained to directly predict a specific percentile of the outcome (e.g. the 5th and 95th) rather than a single mean plus an assumed spread — the basis for GBT's prediction interval, and not derived from the same step-by-step process as a recursive point forecast. Ch. 14.

**Random walk.** A series where each new value is the previous value plus pure, unpredictable noise, with no underlying level to pull it back toward — every deviation is permanent. The exact non-stationary case ADF's null hypothesis and KPSS's alternative hypothesis are both written against, and the reason a naive "repeat the last value" baseline is the mathematically correct forecast for one. Ch. 4, Ch. 8.

**RMSE (root mean squared error).** Like MAE, an average forecast miss in the series' own units, but squares each miss before averaging — so it penalizes a few large misses harder than MAE does. Ch. 8.

**Rolling-origin / walk-forward backtest.** Repeating a backtest at several different points in a series, walking backward, to measure whether a model's performance is stable across stretches rather than a property of one arbitrarily chosen holdout window. Ch. 13.

**SARIMA.** Seasonal ARIMA — `(p,d,q)(P,D,Q,s)` — a model family combining autoregressive terms, differencing, and moving-average terms, with seasonal counterparts at period `s`. Ch. 10.

**Stationarity.** A series whose statistical properties (mean, variance, autocorrelation structure) don't change over time — the standing assumption behind most classical forecasting models, tested rather than assumed throughout this book. Ch. 4.

**Student's t confidence interval.** A confidence interval built using the t-distribution rather than the normal distribution, more appropriate for small samples. Ch. 3.

**Wilson score interval.** A confidence interval for a binomial proportion (like prediction-interval coverage) that stays well-behaved at small sample sizes, unlike a naive normal approximation. Ch. 16.
