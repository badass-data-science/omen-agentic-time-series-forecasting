# Chapter 12: Statistically Better, or Just Different? — Diebold-Mariano Testing

Two questions have been sitting unanswered since earlier chapters, on purpose. Chapter 8 asked whether naive's win over seasonal-naive was real, given that their MAPE confidence intervals overlapped. Chapter 10 flagged two SARIMA candidates separated by less than a single AICc point and explicitly said the ranking needed a proper test before it could be trusted. This chapter is that test, and it finally answers both.

## What the Test Actually Compares

The Diebold-Mariano test (Diebold & Mariano, 1995) does not compare two error numbers directly. It compares a **loss differential**, `d_t = g(e_a,t) - g(e_b,t)`, computed separately at every holdout point, where `g` is squared error (the default) or absolute error and `e` is actual minus predicted. If that differential averages out to something reliably different from zero across the holdout, the two models' accuracy is judged significantly different; if it doesn't, they're treated as indistinguishable regardless of how different their headline MAPE numbers look. This is the paired design Chapter 8 promised was coming — it uses the fact that both models were scored on the exact same holdout points, which is strictly more information than two separate confidence intervals computed in isolation from each other.

There's one more piece of machinery to understand before the results: forecast errors from a genuine multi-step backtest — the kind ETS and SARIMA produce, forecasting an entire holdout from one fixed origin — are typically **autocorrelated**. An error at step 12 isn't independent of the error at step 11; whatever made step 11 miss high or low tends to still be influencing step 12. A plain t-test assumes independent observations and would understate the real uncertainty here. This test instead uses a Newey-West (Bartlett-kernel) HAC-robust variance estimate, with the number of lags it accounts for chosen automatically by the standard Newey & West (1994) rule unless told otherwise.

## Resolving Chapter 8: Was Naive's Win Real?

**Prompt:**
> Chapter 8 found naive beating seasonal-naive on Death-Ray Revenue, but their MAPE confidence intervals overlapped. Is that difference actually significant?

**What Comes Back** (a real result, same 30-week holdout used throughout Part III):

```json
{
  "n_observations": 30,
  "n_lags_used": 3,
  "mean_loss_differential": -9193233.75,
  "dm_statistic": -4.2903,
  "p_value": 0.0002,
  "is_significant_difference": true,
  "favored_model": "naive",
  "interpretation": "Statistically significant difference (p=0.0002): naive has significantly lower average squared loss on this holdout."
}
```

**What It Means:** `p=0.0002` — decisively significant, in naive's favor. Chapter 8's caution about the overlapping CIs turns out to have been exactly the right instinct to flag, but the answer to the question it raised is a clean yes: naive's win is real, not noise. This is the paired-test advantage in action, concretely. Eyeballing two independently computed intervals is a conservative shortcut — real, useful, worth having as an instinct — but a test built on the point-by-point differences between two models scored on the *same* holdout can find significance that two separate intervals, looked at side by side, would leave you unsure about.

## Resolving Chapter 10: Was the Near-Tie Actually a Tie?

**Prompt:**
> Chapter 10's order search found SARIMA(1,1,2) and SARIMA(2,1,2) less than one AICc point apart. Is their backtest accuracy actually distinguishable?

**What Comes Back** (a real result, both fit with `d=1` fixed per Chapter 4, on the same holdout):

```json
{
  "n_observations": 30,
  "n_lags_used": 3,
  "mean_loss_differential": -587884.31,
  "dm_statistic": -2.8349,
  "p_value": 0.0083,
  "is_significant_difference": true,
  "favored_model": "SARIMA(1,1,2)",
  "interpretation": "Statistically significant difference (p=0.0083): SARIMA(1,1,2) has significantly lower average squared loss on this holdout."
}
```

**What It Means:** This cuts against a tempting intuition. An AICc gap of `546.52` versus `547.12` — under one point — looks, on its face, like "these are basically the same model." They are not: `(1,1,2)` significantly outperforms `(2,1,2)` on actual holdout accuracy, at `p=0.0083`. AICc measures in-sample fit penalized for complexity; it is not a direct statement about out-of-sample forecast accuracy, and a small gap in one doesn't guarantee a small gap in the other. `search_sarima_orders`' own advice from Chapter 10 — flag close candidates and verify with this exact test rather than trusting the ranking blind — was earning its keep here, not just being cautious for the sake of it.

## An Honest Reversal of This Chapter's Own Plan

This book's outline originally planned a different headline result for this chapter: SARIMA losing to seasonal-naive, a "the fancier model doesn't automatically win" gotcha. Run for real, on this project's actual Death-Ray Revenue series, that's not what happened.

**What Comes Back** (real result, SARIMA(1,1,2) vs. each Chapter 8 baseline, same holdout):

```json
{"SARIMA vs seasonal_naive": {"p_value": 0.0008, "favored_model": "SARIMA(1,1,2)"}}
{"SARIMA vs naive":          {"p_value": 0.0019, "favored_model": "SARIMA(1,1,2)"}}
```

**What It Means:** SARIMA beats both baselines, decisively, on this series. Rather than force the originally planned upset, here's plainly what actually happened and why it's still a useful result: a test like this doesn't exist to manufacture a specific storyline — it exists to tell you the truth about whichever two models you hand it, and sometimes the truth is that the complicated model really did earn its extra machinery. That's a just-as-real, just-as-useful outcome as an upset would have been. The failure mode this whole book keeps warning about isn't "trusting a complex model" — it's trusting one *without checking*. Here, the check came back in SARIMA's favor, honestly.

## Choosing `n_lags` for a Genuinely One-Step-Ahead Comparison

Every comparison so far involved at least one genuinely multi-step backtest, where the default HAC-robust lag selection is the right choice. Chapter 11's `evaluation_caveat` flagged a different situation: `fit_gradient_boosted_trees`' backtest is one-step-ahead, scored against true lagged values at every holdout point rather than the model's own compounding predictions — the autocorrelation concern this test's default lag rule exists for doesn't apply the same way there.

**Prompt:**
> Fit two gradient-boosted-trees variants — depth 3 and depth 6 — on the minion overtime series. Are they significantly different, and does it matter whether I use the default lag selection or `n_lags=0`?

**What Comes Back** (a real result; `max_depth=6`'s own backtest first, then both DM comparisons):

```json
{"max_depth=6": {"mae": 1.5515, "rmse": 1.8347, "mape_pct": 11.8765}}
```

```json
{"default n_lags (n_lags_used=3)": {"p_value": 0.8465, "is_significant_difference": false},
 "n_lags=0":                       {"p_value": 0.8595, "is_significant_difference": false}}
```

**What It Means:** Depth 6's MAE (`1.55`) looks numerically better than depth 3's (`1.63`) from Chapter 11 — and the test says, both ways, that the gap isn't statistically meaningful (`p=0.85` and `p=0.86` respectively). Two conclusions worth drawing here. First, the direct one: don't switch to the deeper, more expensive model on the strength of that MAE gap alone — it's indistinguishable from noise on this holdout. Second, a more subtle one about the parameter itself: on this particular comparison, `n_lags=0` and the automatic rule landed on almost the same p-value. That won't always be true — the whole reason the parameter exists is that it *can* matter, particularly near a significance boundary, which this comparison simply doesn't happen to sit close to. The rule for which to use isn't "check whether it changes the answer" — you won't know that without running both — it's "match the setting to what the backtest actually is": default for genuinely multi-step comparisons, `n_lags=0` when comparing two one-step-ahead ones, decided by what the backtests *are*, not by which answer either setting gives you. And one thing this test still doesn't resolve, echoing Chapter 11: even a "not significantly different" verdict between two GBT variants says nothing about how either would hold up once forecasting recursively, multiple steps ahead, off its own predictions instead of true lagged values. That question is still open, and Chapter 14 is still where it gets answered.

## What's Next

Two long-open questions are closed, and a third, unplanned finding — SARIMA's real, decisive win over both baselines — is now part of the record instead of the loss this chapter was originally supposed to show. Every comparison in this chapter still rests on one fixed 30-week holdout, though, and Chapter 8 already flagged that a single window has its own sampling luck baked in. Chapter 13 asks the next honest question: would any of this still hold up if the holdout window itself had landed somewhere else in the series?
