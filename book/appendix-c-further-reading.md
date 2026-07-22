# Appendix C: Further Reading

The academic sources Omen's own methods are actually drawn from — not a
general reading list, but the specific papers behind the specific tests
this book ran, chapter by chapter — plus where to go for continued
practice once you've finished the book.

## The Sources Behind the Tools

**Dickey, D. A., & Fuller, W. A. (1979).** "Distribution of the
Estimators for Autoregressive Time Series with a Unit Root." *Journal of
the American Statistical Association*. The augmented Dickey-Fuller
(ADF) test behind `check_stationarity`'s first half. Ch. 4.

**Kwiatkowski, D., Phillips, P. C. B., Schmidt, P., & Shin, Y. (1992).**
"Testing the Null Hypothesis of Stationarity against the Alternative of
a Unit Root." *Journal of Econometrics*. The KPSS test behind
`check_stationarity`'s second half — deliberately testing the opposite
null hypothesis from ADF. Ch. 4.

**Fisher, R. A. (1929).** "Tests of Significance in Harmonic Analysis."
*Proceedings of the Royal Society A*. The g-test behind
`detect_seasonality_period`'s significance check on a periodogram's
dominant frequency. Ch. 5.

**Bartlett, M. S. (1946).** "On the Theoretical Specification and
Sampling Properties of Autocorrelated Time-Series." *Supplement to the
Journal of the Royal Statistical Society*. The formula behind
`acf_pacf_summary`'s lag-dependent significance threshold, used instead
of a flat threshold that would over-flag distant lags. Ch. 6.

**Iglewicz, B., & Hoya, D. C. (1993).** "How to Detect and Handle
Outliers." *ASQC Quality Press*. The median-and-MAD-based modified
z-score behind `detect_anomalies_robust_zscore` and
`compare_forecast_to_actuals`'s residual-outlier check. Ch. 7, Ch. 16.

**Hurvich, C. M., & Tsai, C.-L. (1989).** "Regression and Time Series
Model Selection in Small Samples." *Biometrika*. The small-sample
correction behind every `aicc` value this book reported, from Ch. 9
onward.

**Hyndman, R. J., & Athanasopoulos, G.** *Forecasting: Principles and
Practice* (any edition; freely available at otexts.com/fpp3). The
standard reference for the naive-forecast interval formulas behind
`fit_naive_baselines` and `forecast_naive`, and a genuinely good general
forecasting textbook beyond what this book's own scope covers. Ch. 8,
Ch. 14.

**Diebold, F. X., & Mariano, R. S. (1995).** "Comparing Predictive
Accuracy." *Journal of Business & Economic Statistics*. The paired
significance test behind `diebold_mariano_test`, and the mechanism
behind two of this book's most consequential real findings (Ch. 8 and
Ch. 10's open questions, both resolved in Ch. 12).

**Newey, W. K., & West, K. D. (1994).** "Automatic Lag Selection in
Covariance Matrix Estimation." *Review of Economic Studies*. The
automatic lag-selection rule behind the Diebold-Mariano test's default
HAC-robust variance estimate. Ch. 12.

**Wilson, E. B. (1927).** "Probable Inference, the Law of Succession,
and Statistical Inference." *Journal of the American Statistical
Association*. The Wilson score interval behind
`compare_forecast_to_actuals`'s coverage confidence interval — well-
behaved at the small sample sizes a freshly deployed forecast actually
has. Ch. 16.

**Cohen, J. (1988).** *Statistical Power Analysis for the Behavioral
Sciences* (2nd ed.). The conventional small/medium/large effect-size
bins this book cited, and then complicated with real numbers, in
Chapter 17 — worth reading Cohen's own original caveats about treating
those bins as more universal than he intended.

## For Continued Practice

**`blog-posts/`** — the companion post series covering this same
five-layer arc in shorter form, one post per layer plus the project's
original introductory post. A faster read to hand someone, or to revisit
a layer's core ideas without a full chapter's worth of detail.

**`prompts/testing-and-learning-prompts.md`** — sixty-plus ready-to-use
prompts across all five layers, written for exactly the kind of hands-on
practice Chapter 20 asked you to do with your own material. Chapter 20's
"Your Turn" exercise draws directly from this file.

**`AGENTS.md`** — the project's own internal design log, denser and less
narrated than this book, written for whoever extends Omen's code next
rather than for a first read. The most current source of truth on the
toolkit's actual behavior, including anything this book's real-verified
numbers might drift from as the project keeps evolving after this book's
own writing.
