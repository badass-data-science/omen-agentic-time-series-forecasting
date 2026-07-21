# Chapter 4: Is This Thing Stable? — Stationarity, ADF & KPSS

The mojito inventory series from Chapter 3 was, if you'd looked closely,
a fairly well-behaved thing — it wobbled around a level, the way a
well-run supply chain should. This chapter introduces a series that
does not do that, on purpose, because most of the forecasting techniques
in Part III assume — explicitly or implicitly — that the series they're
being asked to model has a stable statistical personality over time. Find
out whether that assumption holds *before* you fit anything. That's the
whole chapter.

## What "Stationary" Actually Means

A time series is **stationary** if its statistical properties — mean,
variance, the way it correlates with its own past — don't systematically
change as time goes on. A stationary series can still go up and down; it
just doesn't have a *trend* to its ups and downs, and it doesn't get more
or less volatile as the years pass. A **non-stationary** series does one
or both of those things, and it matters enormously, because a large
family of classical forecasting models (you'll meet SARIMA specifically
in Chapter 10) are built on an assumption of stationarity and will
produce nonsense — confidently — if you hand them a series that doesn't
have it.

The two formal tests this chapter teaches don't just disagree by
accident on how to check this. They test genuinely **opposite null
hypotheses**, which is the whole reason Omen runs both together rather
than picking one:

- **ADF (Augmented Dickey-Fuller)** — null hypothesis: *the series has a
  unit root* (is non-stationary). A low p-value here is evidence
  *against* non-stationarity — i.e., evidence *for* stationarity.
- **KPSS (Kwiatkowski–Phillips–Schmidt–Shin)** — null hypothesis: *the
  series is stationary*. A low p-value here is evidence *against*
  stationarity.

Because the nulls point in opposite directions, running both and reading
them together gives you a genuine four-way readout instead of one test's
blind spot standing in for the whole truth:

| ADF says | KPSS says | Verdict |
|---|---|---|
| stationary | stationary | Both agree — trust it |
| non-stationary | non-stationary | Both agree — trust it |
| stationary | non-stationary | Disagreement — investigate further |
| non-stationary | stationary | Disagreement — investigate further |

## Meet Death-Ray Revenue

**Death-Ray Revenue** — weekly income from renting out the Secret Lab™'s
death ray to other operations that would rather lease world-ending
hardware than build their own — is this book's first deliberately
non-stationary series. Reputation compounds, rental rates have climbed
accordingly, and the series has been trending upward for well over a
year now. It's introduced here and comes back repeatedly through Part
III as the flagship "let's actually build a model for this" example.

**Prompt:**
> Is the death-ray revenue series stationary? If ADF and KPSS disagree,
> what should I do about it?

**What Comes Back** (a real result, from 70 weeks of revenue aggregated
from a synthetic daily series with a strong upward trend, generated the
same way the project's own test data always is):

```json
{
  "adf_statistic": 1.4069,
  "adf_p_value": 0.9971,
  "adf_is_likely_stationary": false,

  "mean_reversion_lambda": -0.001116,
  "mean_reversion_lambda_ci_lower": -0.022961,
  "mean_reversion_lambda_ci_upper": 0.020729,
  "mean_reversion_half_life_periods": 620.9,
  "mean_reversion_half_life_ci_lower": 30.19,
  "mean_reversion_half_life_ci_upper": null,

  "kpss_statistic": 1.2649,
  "kpss_p_value": 0.01,
  "kpss_critical_value_5pct": 0.463,
  "kpss_effect_size": 2.7319,
  "kpss_is_likely_stationary": false,

  "interpretation": "ADF and KPSS agree: series is likely non-stationary; differencing may be needed. Mean-reversion half-life is ~620.9 periods (95% CI: 30.19 to unbounded (CI for lambda includes non-reverting values)) -- small values correct quickly, large ones are slow even if statistically detectable. KPSS statistic is 2.7319x its 5% critical value (exceeds it)."
}
```

**What It Means:** No disagreement to referee this time — ADF and KPSS
both land on non-stationary, which is the easy case in the table above,
and exactly what you'd expect from a series with an obvious, sustained
upward trend. An ADF p-value of `0.9971` is about as unambiguous as this
test gets: there is essentially no evidence against the unit-root null.
This series needs differencing (Chapter 10 shows you exactly how) before
it's a reasonable candidate for a model that assumes stationarity.

## The Effect Size Behind the Verdict

A bare "non-stationary: true" would already be useful. But look at what
else came back — `mean_reversion_lambda` and
`mean_reversion_half_life_periods` — and this is where the chapter earns
its subtitle.

`mean_reversion_lambda` is the estimated speed at which the series pulls
back toward its own mean, fit from the regression `Δy_t = λ·y_{t-1} + μ
+ ε_t`. Here it's `-0.001116` — technically negative, technically
implying *some* reversion — but look at its confidence interval:
`[-0.022961, 0.020729]`. That interval comfortably straddles zero. In
plain terms: the data cannot actually distinguish "reverts extremely
slowly" from "doesn't revert at all," and reporting the point estimate
alone, without that interval, would have implied a confidence the number
doesn't earn.

This turns into something even more concrete once you convert it to a
half-life — how many weeks it would take a deviation from the mean to
shrink by half. The point estimate is `620.9 weeks` — just under twelve
years. Its confidence interval is `[30.19, null]` — the upper bound is
`null` specifically because `lambda`'s own interval reaches into
non-negative territory, and a lambda of zero or higher implies a
half-life of infinity. This is Omen refusing to report a fabricated
finite number for "how long until this reverts" when the honest answer
is "the data can't rule out *never*." A half-life measured in decades,
with an upper bound of "possibly forever," is not information you can
build a 30-day forecast around — which is exactly the point this
chapter's introduction promised: **a series can clear statistical
significance on paper while being practically useless for the timeframe
you actually care about, and the effect size is the only place that
shows up.**

One general caution worth carrying forward, even though this particular
series is a smooth trend rather than a textbook random walk: for series
that genuinely do have a unit root, this same `lambda` estimate is known
to skew slightly negative in finite samples even when there's zero true
reversion. That means a small negative lambda, on its own, is never
proof of real mean-reversion — you always need the confidence interval
and the ADF/KPSS verdict alongside it, exactly as this example just
demonstrated.

## Why KPSS Gets an Effect Size Too

KPSS's own p-value has a quirk worth knowing about before you lean on it
too heavily: it's interpolated from just four lookup-table points and
clipped at the table's edges. That's why it landed at a suspiciously
round `0.01` above — that's the floor, not necessarily "exactly a 1%
probability of anything." Two wildly different series could both report
`p=0.01` and give you no way to tell, from the p-value alone, whether one
just barely crossed the line and the other blew straight through it.

`kpss_effect_size` exists to answer that: the KPSS statistic expressed as
a multiple of its own 5% critical value. Here, `2.7319` means the
statistic came in at nearly 2.7 times the threshold — comfortably,
unambiguously past it, not a borderline call. Where the coarse p-value
alone would have left you guessing, the effect size tells you this isn't
close.

## What's Next

You now have two independent, opposite-null tests agreeing that
Death-Ray Revenue is non-stationary, with effect sizes that explain
*how* non-stationary, not just a yes/no. Chapter 5 asks the next natural
question about a series like this: underneath that trend, is there a
real, repeating rhythm to the business — and if so, at what period,
proven, not assumed?
