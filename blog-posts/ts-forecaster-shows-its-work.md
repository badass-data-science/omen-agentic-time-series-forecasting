# ts-forecaster Learns to Show Its Work (or, How Our Heroine Taught Layer 2 That "The Error Was Lower" Is Not An Argument)

*In which a SARIMA model gets caught losing to a baseline it should have crushed, a grid search finds a numerically perfect candidate with structurally broken residuals, and a bug gets caught in the math before it ever reached production.*

Two posts ago, our heroine introduced the whole five-layer assembly line. One post ago, `ts-analyst` got taught to never say "significant" without also saying "by how much" — and in the process, she caught it quietly lying to itself twice. This post is about what happened when that same discipline moved one layer downstream, into `ts-forecaster`, the part of the toolkit whose entire job is picking a winner between competing models.

Layer 2's original sin, as she put it back in the introductory post, was letting "the error was lowest" pass for reasoning when it's actually "a coin flip with extra steps." Fixing that turned out to require more than confidence intervals this time. It required an actual hypothesis test for "is Model A really better than Model B" — and building that test honestly is what led to the most interesting bug of this entire project so far.

## The Problem With a Single Holdout Window

Every backtest in `ts-forecaster` works the same way: hold out the last `holdout_size` rows of the series, fit on everything before that, forecast the holdout, score it. This is completely standard practice. It is also, on its own, a single roll of the dice. If that particular stretch of the series happened to contain an anomaly, or the seasonality lined up unusually well or badly for one candidate over another, every number that comes out the other end — MAE, RMSE, MAPE, even the bootstrap confidence interval added around them — inherits that bias, because a bootstrap CI only resamples points *inside* that one window. It can't tell you whether the window itself was lucky.

And even once you trust the numbers from a single window, you're left with the second problem: two models with different MAPE scores aren't necessarily *meaningfully* different. "4.8% vs. 5.0%" sounds like a real gap. On a 30-point holdout, it might not be.

Fixing both of these — the single-window problem and the "is this difference real" problem — is what the rest of this post is about.

## The Tools, One at a Time

**`holdout_split_summary`** and **`fit_naive_baselines`** are unchanged in spirit — sanity-check the split, then always fit the trivial floor (flat naive, seasonal naive) that every real candidate has to clear. What's new: both baselines' `backtest_metrics` now carry a bootstrap confidence interval, and the whole result includes the raw `holdout_actuals` and `holdout_predicted` arrays, quietly setting up everything downstream.

**`fit_ets`** and **`fit_sarima`** picked up three additions apiece. First, the same bootstrap confidence interval on MAE/RMSE/MAPE that landed everywhere in `ts-analyst` last time — percentile method, resampling paired (actual, predicted) points, deterministic given a seed. Second, `aicc`: a small-sample correction to AIC (Hurvich & Tsai, 1989) that matters because AIC's own bias grows as the parameter count approaches the training size, which is exactly the regime these models usually fit in. Third, and most useful in practice: `backtest_interval_coverage`. Both models can already produce a prediction interval — SARIMA analytically, ETS via simulation — but until now nobody checked whether that interval actually meant anything. Now it does: the interval gets built over the holdout window and checked against what actually happened, using the *exact same* coverage-calibration logic `ts-monitor` already runs after deployment. The difference is timing. Catching a badly calibrated interval during backtesting means catching it before anyone ships it, instead of waiting for Layer 4 to notice weeks later.

**`fit_gradient_boosted_trees`** got the bootstrap CI too, but pointedly not the interval coverage check — it has no native prediction interval, same limitation its deployed forecast already carries in `ts-deploy`. No pretending otherwise.

**`diebold_mariano_test`** is the actual headline. This is a formal statistical test — Diebold & Mariano, 1995 — for whether two models' forecast errors on the *same* holdout are significantly different, not just numerically different. Feed it the real holdout values and two models' predictions; it compares the loss differential between them, accounts for the fact that forecast errors from a multi-step backtest are typically autocorrelated (using a Newey-West variance estimate), and returns a straight answer: significant, or not. Run against the project's own synthetic data, SARIMA with default `(1,1,1)(1,1,1,7)` orders didn't just fail to beat `seasonal_naive` — it lost to it *significantly*, p = 0.0015. That is not a hypothetical edge case invented for a blog post. That is what the tool found the first time our heroine actually pointed it at real output, which is exactly the kind of finding "the error was lower" would have let her miss going the other direction, quietly picking SARIMA anyway because its point estimate looked fine.

**`rolling_origin_backtest`** is the fix for the single-holdout-window problem described above. Instead of trusting one fixed split, it walks a model backward through the series at several different origins — refitting from scratch each time, training window expanding as it goes — and reports the mean and standard deviation of backtest performance across all of them. A model whose MAPE bounces between 3% and 9% depending on which stretch of the series you ask it about does not have a stable edge, and now there's a direct, cheap way to find that out before recommending it. It costs `n_origins` times the compute of one fit, which is the honest price of walk-forward evidence rather than a single snapshot.

**`search_sarima_orders`** is the one our heroine went back and forth on including at all. Every layer of this toolkit is built around the idea that the agent reasons about model settings from what `ts-analyst` actually found — not grid-search blindly. An automated order search cuts directly against that. So it shipped, but scoped deliberately narrow: `d` and seasonal `d` stay fixed, supplied by the caller (informed by `ts-analyst`'s stationarity findings, not guessed), only `(p,q)(P,Q)` get searched, and the result is explicitly labeled a shortlist, never an answer. The tool's own output backs up why that framing matters: run against the project's synthetic data, the single best candidate by AICc came back with `residuals_look_like_white_noise: false`. Ranked first, structurally deficient. Exactly the kind of thing a human — or an agent still doing its job properly — is supposed to catch on the way past a grid search, not before it.

## The Bug That Didn't Ship

Building `diebold_mariano_test` involved implementing the Harvey-Leybourne-Newbold small-sample correction that the DM literature recommends for exactly the holdout sizes this toolkit works with. The first draft parameterized that correction around a "forecast horizon" concept borrowed directly from the classic setup, where you're comparing repeated forecasts from many different origins, each reaching some fixed number of steps ahead.

`ts-forecaster` doesn't have that structure. It has one origin and one holdout window evaluated across increasing horizons within it — a materially different setup. Working through the correction formula by hand for this project's actual case revealed the problem: when the "horizon" parameter equals the sample size, the correction factor collapses to exactly zero. Not approximately. Algebraically, exactly zero, every time. Every test result would have come back non-significant regardless of what the data actually said — a null result generator wearing a rigorous-looking formula as a costume.

Caught before a single line of it reached the actual test suite. The shipped version uses an ordinary Newey-West automatic lag-selection rule instead, decoupled from any "horizon" concept, and a plain Student's t reference distribution for conservatism rather than presenting a specific formula as authoritative when the underlying assumptions don't actually hold for this toolkit's design. Documented at length in `AGENTS.md`, specifically so nobody reintroduces the elegant, degenerate version later because it looked more textbook-correct.

## Next Steps

- **`rolling_origin_backtest` doesn't cover `fit_naive_baselines`.** Deliberately, for now — a naive baseline is cheap and non-parametric enough that walk-forward rigor felt like overkill. Worth revisiting if a baseline's own stability ever becomes load-bearing for a decision.
- **`search_sarima_orders` doesn't search differencing order.** `d` and seasonal `d` are supplied, not searched, on purpose — but a version that at least *validates* the supplied differencing order against `ts-analyst`'s own ADF/KPSS findings, rather than trusting the caller blindly, would close a real gap without reopening the "let the search decide everything" question.
- **No ensemble or model-averaging tooling yet.** Every candidate here is still evaluated and recommended individually. Combining backtest-validated candidates into a weighted forecast is a real technique with real literature behind it — but it's arguably `ts-deploy`'s question to answer, not this layer's, since it's about producing a forecast rather than evaluating candidates for one.

## Conclusion

`ts-forecaster` used to hand back a number and let the agent decide what "better" meant. Now it hands back a number, a confidence interval on that number, a stability check across multiple time windows, and — when it actually matters — a hypothesis test with a p-value attached to the word "better." One of those additions caught a real underperforming model before it could get recommended. Another caught a bug in its own math before it could ship. Our heroine considers that a good return on a few extra JSON fields.

## Code

Code is available at [badass-data-science/Data-Science](https://github.com/badass-data-science/Data-Science/tree/agentic-time-series-tools/Forecasting/omen), on the `agentic-time-series-tools` branch.

## AI Use Statement

This article's prose was drafted by Claude Code, based on our heroine's explicit instructions and matching the voice/structure established in the toolkit's two prior posts; she will review and edit before publishing. All of the `ts-forecaster` work described here — the bootstrap confidence intervals, the Ljung-Box effect size, AICc, backtest prediction-interval coverage, the Diebold-Mariano test (including the small-sample-correction bug caught and fixed before shipping), rolling-origin backtesting, and the advisory SARIMA order search — was designed and built collaboratively with Claude Code across a series of sessions.
