# Chapter 15: Strength in Numbers? — Ensembling Multiple Models

Chapter 12 left a specific promise hanging: that a real, honest occasion for ensembling would eventually show up, once two candidates turned out to be genuinely, statistically indistinguishable rather than one just looking slightly better on paper. This chapter goes looking for that occasion on Death-Ray Revenue, using the exact tool built for exactly that — the Diebold-Mariano test — before touching `forecast_ensemble` at all. What it finds changes the chapter's plan.

## Looking for the Legitimate Occasion, and Not Finding One

**Prompt:**
> Run Diebold-Mariano tests between every pair of Death-Ray Revenue's real candidates — naive, seasonal-naive, SARIMA, ETS, and GBT. Is there a single pair that comes back not significantly different?

**What Comes Back** (real results, every pair on the same 30-week holdout):

```
sarima vs gbt:            p=0.0024  significant, favors sarima
ets vs gbt:                p=0.0026  significant, favors ets
naive vs gbt:               p=0.0116  significant, favors naive
seasonal_naive vs gbt:      p=0.0315  significant, favors gbt
naive vs ets:                p=0.0021  significant, favors ets
naive vs sarima:             p=0.0019  significant, favors sarima
sarima vs ets:                p=0.0060  significant, favors ets
seasonal_naive vs ets:        p=0.0009  significant, favors ets
```

(Two more pairs — naive-vs-seasonal_naive and SARIMA-vs-seasonal_naive — were already established in Chapter 12; all ten possible pairs among these five candidates have now, between the two chapters, actually been run.)

**What It Means:** Every single pair, across all five real candidates built up over Chapters 8 through 11, comes back statistically significant. This book's own outline expected SARIMA and ETS specifically to land in a genuine statistical tie here — the natural setup for this chapter's demonstration. That's not what the real test found: ETS beats SARIMA outright, at `p=0.006`. On this series, with these candidates, there simply isn't a legitimate close call to point to. ETS(add, mul, 7) — Chapter 9's well-calibrated multiplicative model — beats everything else it was tested against, every single pair checked. The rigorous, data-driven answer, followed all the way through, is: deploy ETS alone.

That's a genuinely useful thing to know before touching this chapter's main tool at all, and it reframes what this chapter actually needs to teach. Rather than force a manufactured tie, the more honest — and more useful — lesson is what happens when you ensemble anyway, in the absence of that justification, and see the real cost with real numbers.

## The Arithmetic, Verified Exactly

Before that, one piece of pure math worth confirming with a real tool call rather than trusting on faith: combining two **identical** components at equal weight should narrow the interval by a factor of exactly `1/√2`, under the variance-combination formula's independence assumption. `sqrt(0.5² · σ² + 0.5² · σ²) = σ · sqrt(0.5) = σ/√2` — simple enough to check by hand, and worth checking against the real tool rather than just trusting the algebra in isolation.

**What Comes Back** (a real result, SARIMA fit twice with identical parameters, deliberately, deterministic analytic interval so no simulation randomness can blur the comparison):

```
Solo SARIMA interval width:      1556.803
SARIMA + SARIMA ensemble width:  1100.826
Ratio:                           0.7071068...
1/√2:                            0.7071068...
```

**What It Means:** Exact, to the precision the tool reports. This is the mechanism working precisely as designed, on real output — narrowing an interval by combining a model with an exact literal copy of itself is the cleanest possible demonstration that this isn't a bug or a modeling artifact, just the direct arithmetic consequence of assuming independent errors. It's worth noting this exactness relied on picking SARIMA specifically for the demonstration: ETS's interval is built from simulated paths (Chapter 9), and two "identical" ETS components in the same ensemble call each run their own separate, unseeded simulation — close to but not exactly matching each other, which would have blurred this particular arithmetic check without actually changing the underlying principle.

## Ensembling the Wrong Reason, With Real Numbers

**Prompt:**
> Combine SARIMA and ETS into an ensemble anyway, even knowing ETS significantly wins on its own. What does the combined forecast and interval actually look like?

**What Comes Back** (real result, equal weighting, day-30 endpoint):

```
SARIMA solo:    forecast 42,087.82   interval [34,480.93, 49,694.70]  width 15,213.77
ETS solo:       forecast 44,426.57   interval [42,787.12, 46,088.66]  width  3,301.54
Ensemble (0.5/0.5): forecast 43,257.19  interval [39,352.74, 47,161.65]  width  7,808.92
```

**What It Means:** This is the real cost of ensembling in a candidate the data has already told you is worse, made concrete rather than asserted. Two things happen, both real, both quantifiable. First, the point forecast: it moves away from ETS's own, more-accurate `44,426.57` toward a blended `43,257.19`, pulled in the direction of the significantly worse model. Second, and more strikingly, the interval: ETS alone is confident, `3,301.54` wide; SARIMA alone is nearly five times less confident, `15,213.77` wide. The equal-weighted combination comes out at `7,808.92` — narrower than SARIMA's own interval, yes, but more than double ETS's. Averaging in a less accurate, less certain model didn't just risk diluting accuracy in the abstract — it mechanically dragged a genuinely well-calibrated interval wider, in trade for nothing this book's own DM test says you should want. This is what "a way to paper over a candidate that should have been rejected outright" actually looks like on real output, not just as a warning in the abstract.

## The Independence Assumption Was Never Really True

Both of these ensembles, the legitimate arithmetic check and the ill-advised real one, rest on the same optimistic assumption: that the components' forecast errors are independent. They are not, and can't be — SARIMA and ETS were both fit on the exact same 70 weeks of Death-Ray Revenue, so whatever real-world structure either model missed (the same trend quirks, the same noisy weeks, the same underlying data Chapter 4 already found non-stationary) is at least partly shared between them, not independent draws from separate sources of error. The `sqrt(sum(w_i² σ_i²))` formula doesn't know that, and can't account for it. Every combined interval this chapter has shown should be read as a genuine **lower bound** on the ensemble's true uncertainty, not a precise estimate of it — narrower, in reality, than the number on the page suggests, by an amount this formula has no way to quantify.

## When Ensembling Actually Earns Its Keep

Putting this chapter's real findings together into the rule its third learning objective asked for: ensembling is appropriate when a proper comparison — Chapter 12's DM test, not a glance at two MAPE numbers — says two or more candidates are **genuinely, statistically indistinguishable**, and you have a real reason to want more than one of them represented (robustness to whichever one happens to be wrong this particular month, say). It is not a way to hedge your bets when you already have a clear, tested winner. Today, on Death-Ray Revenue, ETS is that clear winner — this chapter's own search across every real pair confirmed it, decisively, five different ways. The honest deployment decision coming out of fifteen chapters of real testing is refreshingly simple: skip the ensemble, deploy ETS.

## What's Next

A forecast is only as good as the world it was fit on continues to resemble. Every model this book has built assumes, implicitly, that Death-Ray Revenue and Mojito Inventory keep behaving the way their history says they do. Chapter 16 opens Part IV's second half — `ts-monitor` — and asks the question this book has been building toward since Chapter 7's changepoints: how do you actually find out when that assumption has quietly stopped being true?
