# Forecasting for Supervillains
### Statistical Time Series Prediction with Omen and Agentic AI
**Proposed Outline**

---

## About This Outline

This is a chapter-by-chapter proposal for the book, not the book itself. Every
chapter below follows the same template so the structure stays comprehensible
at this length:

- **Concept(s) taught** — the statistical/forecasting idea(s) at the center of the chapter.
- **Omen tools used** — the actual MCP tools the chapter's exercises call, by name.
- **Learning objectives** — what the reader should be able to do afterward.
- **The villainous example** — the running dataset for the chapter, and why its shape fits the lesson.
- **Gotchas & rationale** — the specific "here's why this isn't as simple as it looks" content the book promises, grounded in real, documented behavior of the toolkit (not invented for the outline).
- **Sample prompts** — 2–3 representative prompts in the book's prompt-based instructional style, in the same voice as `prompts/testing-and-learning-prompts.md`.

Chapters escalate in difficulty roughly in the same order the five Omen
layers were designed to be used — explore, backtest, deploy, monitor,
retrain — because that ordering already *is* a reasonable forecasting
curriculum: you can't honestly evaluate a model until you've looked at the
data, and you can't honestly monitor a model until you've deployed one.

Two datasets recur across multiple chapters as a light narrative
through-line, the same way the companion blog posts return to "the Secret
Lab™" repeatedly: **Secret Lab™ Mojito Inventory** (introduced in Chapter 3,
finally deployed for real in Chapter 14) and **Death-Ray Revenue**
(introduced in Chapter 4, stress-tested throughout Part III). Every chapter
also gets its own purpose-built example chosen specifically because its
shape teaches that chapter's concept honestly — a series with no seasonality
doesn't belong in the seasonality chapter no matter how funny the premise is.

---

## Front Matter

- **Title Page** — title, subtitle, "as told by our heroine the data
  scientist," and a one-paragraph framing note connecting this book to the
  `Omen` blog post series (`blog-posts/`), which readers are encouraged to
  treat as companion reading, not a prerequisite.
- **How to Use This Book**
  - Who this book assumes you are: comfortable with mean/variance/p-values
    and basic regression, new to time series specifically and to agentic
    tool-use generally.
  - The prompt-based convention used throughout: every worked example shows
    a boxed **Prompt** (what you'd actually type to your agent) followed by
    **What Comes Back** (the tool's real JSON output, trimmed for space) and
    **What It Means** (the plain-language interpretation).
  - A note that every tool result shown in this book is a *real* result from
    a *real* run against synthetic data generated the same way the project's
    own test suite generates it — not a hand-typed mockup — and that every
    named dataset (Secret Lab™ Mojito Inventory, Death-Ray Revenue, and the
    rest) can be regenerated exactly, from the same fixed seeds, by running
    `book/examples/generate_book_datasets.py` (see `book/examples/README.md`).
  - Pointers to `prompts/testing-and-learning-prompts.md` (more prompts per
    layer than the book has room to use) and `AGENTS.md` (the toolkit's own
    running design-decision log, useful once you want to go deeper than any
    one chapter).
- **A Word on AI Use** — this book's prose was drafted collaboratively with
  an AI coding assistant against the actual Omen codebase and its test
  suite; every tool name, field name, and numeric example was checked
  against real behavior, not invented. (Matches the AI Use Statement
  convention already established in the blog post series.)

---

## Part I — Meet Your New Henchman

### Chapter 1: Introducing Omen and Agentic AI

**Concept(s) taught:** What "agentic AI" actually means in a forecasting
context, as distinct from "an AI that writes forecasting code for you"; why
a five-layer pipeline with typed tools beats a general-purpose chat session
improvising `pandas` from scratch every time; the specific idea of
*deterministic gates around agentic judgment* that recurs through the whole
book.

**Omen tools used:** None yet — this chapter is conceptual scaffolding. It
previews `basic_stats` output as a teaser without explaining it.

**Learning objectives:**
- Distinguish "agentic AI" (an LLM driving a sequence of typed tool calls,
  reasoning between them) from "an LLM that free-hands analysis code."
- Explain why some forecasting decisions in Omen are deliberately *not*
  left to agent judgment, with at least one concrete example.
- Describe the five-layer shape of the pipeline (explore → backtest →
  deploy → monitor → retrain) and what question each layer answers.
- Understand what FastMCP and OpenClaw-style skills are, at a level
  sufficient to follow Chapter 2's install instructions.

**The villainous example:** A cold open — our heroine's Secret Lab™ has been
tracking mojito inventory by hand on a whiteboard for six months, and the
Powers That Be™ have started asking pointed questions about a stockout that
happened right before the last board meeting. This is the problem the book
solves, not yet with data — just with a promise that Chapter 3 picks this
back up.

**Gotchas & rationale:**
- Why "just ask the AI to forecast this" fails silently: an LLM with no
  typed tools will happily fit *something*, report a number with false
  confidence, and never mention that it never checked whether the series
  was even stationary.
- The core design tension this whole book keeps returning to: agent
  judgment is genuinely valuable for open-ended reasoning (which model
  family fits this series' shape?) and genuinely dangerous for
  consequential yes/no actions (should this go to production right now?)
  — and Omen's layer boundaries exist specifically along that fault line.

**Sample prompts:**
- "Explain, in your own words, why Omen doesn't just let you ask for 'a
  forecast' in one step."
- "What's the difference between `ts-forecaster` recommending a model and
  `ts-retrain` deciding whether to redeploy one?"

---

### Chapter 2: Installing Omen (OpenClaw, Claude Code, Hermes, and Friends)

**Concept(s) taught:** How MCP (Model Context Protocol) servers and clients
actually connect — stdio transport, tool discovery, the console-script
pattern — enough for the reader to install Omen on whatever agentic
platform they're actually using, not just the one the book happens to
screenshot.

**Omen tools used:** None (this is infrastructure), but the chapter ends
with a real smoke test: connecting a client and calling
`ts-analyst__basic_stats` once, successfully, as proof of life.

**Learning objectives:**
- Install Omen (`pip install -e ".[all]"` or per-layer extras) into a clean
  virtual environment.
- Register all five MCP servers with at least one agentic platform.
- Diagnose the single most common installation failure (a launched
  subprocess not inheriting the venv's `PATH`) and fix it.
- Confirm installation success via a live tool call, not just "the install
  command didn't error."

**The villainous example:** No dataset yet — the "example" here is the
install process itself, treated as the first real exercise. The chapter's
final smoke test uses a tiny hardcoded series (`"Secret Lab™ Weekly
Grumbling Level, 5 data points"`) specifically because it's too small to
mean anything statistically, which is the point: this chapter proves the
wiring works, not that the forecasting is good.

**Gotchas & rationale:**
- **OpenClaw**: the primary target platform for this book. Install
  `omen`, merge `openclaw.config.snippet.jsonc` into
  `~/.openclaw/openclaw.json`, copy the bundled skills
  (`skills_dir()`) into the OpenClaw workspace, verify with
  `openclaw mcp status --verbose` and `openclaw mcp doctor --probe`.
- **Claude Code**: registering an MCP server via Claude Code's own
  MCP-server configuration, pointing at the same console scripts; the
  skill files become useful as reference material even where Claude Code
  doesn't consume `SKILL.md` natively the way OpenClaw does.
- **Hermes** (and other MCP-speaking agent frameworks generally): rather
  than guessing at a specific proprietary config format, this section
  teaches the underlying contract — any client that can launch a
  stdio-speaking MCP server by command + args can run Omen — so readers on
  a platform this book doesn't name-check specifically can still get
  there.
- **Generic / other MCP clients** (e.g. Claude Desktop, or any future
  MCP-compatible tool): same underlying pattern, different config file
  location.
- **The gotcha, demonstrated live, not just described**: a subprocess
  launched by a bare command name (`"ts-analyst-server"`) can fail with
  `FileNotFoundError` even though the same command works fine when typed
  in a terminal, because the subprocess doesn't inherit the parent
  process's activated-venv `PATH`. Fix: use the absolute path to the
  installed console script. (This is a real failure this book's own
  author hit while testing the very first example against a live server —
  worth narrating exactly that way.)

**Sample prompts:**
- "Confirm the `ts-analyst` MCP server is running and list every tool it
  exposes."
- "Run `basic_stats` on a five-point toy series just to prove the
  connection works end to end."

---

## Part II — Reading the Series Before You Trust It
*(`ts-analyst`, Layer 1)*

### Chapter 3: First Contact — Loading Data and Basic Statistics

**Concept(s) taught:** What a time series "is" as a data structure (ordered,
dated, one value per timestamp); the difference between a population
statistic and a sample statistic; confidence intervals on a simple mean as
the gentlest possible introduction to "never report a number without also
reporting how sure you are."

**Omen tools used:** `ts-analyst__basic_stats`.

**Learning objectives:**
- Load a CSV into Omen and interpret `n_observations`, `inferred_frequency`,
  and `n_missing_values`.
- Compute a confidence interval on a mean by hand (conceptually) well
  enough to sanity-check what the tool reports.
- Explain why the standard error calculation must use the count of
  *non-missing* values, not the raw row count.

**The villainous example:** **Secret Lab™ Mojito Inventory** (daily count of
mojitos on hand, six months of data, a few missing days from "the
incident"). This is the series teased in Chapter 1 — its first real
appearance.

**Gotchas & rationale:**
- A series with gaps that gets its standard error computed from `len(df)`
  instead of the non-null count will silently report a *narrower*
  confidence interval than the data actually supports — demonstrated with
  the mojito series' own missing days.
- A constant series (imagine a mojito supply that literally never changes)
  has zero variance, and `mean_ci_lower`/`mean_ci_upper` correctly come
  back `null` rather than a fabricated zero-width interval — worth showing
  explicitly so readers recognize `null` as "correctly refuses to answer,"
  not a bug.

**Sample prompts:**
- "Load the mojito inventory series and tell me the average daily stock
  level, with a confidence interval."
- "How many days of data are missing, and does that change how much you'd
  trust the reported average?"

---

### Chapter 4: Is This Thing Stable? — Stationarity, ADF & KPSS

**Concept(s) taught:** Stationarity as a concept (constant mean/variance
over time); why it matters for classical forecasting models; the
Augmented Dickey-Fuller and KPSS tests as complementary, opposite-null
tests; effect sizes for a hypothesis test, not just its p-value.

**Omen tools used:** `ts-analyst__check_stationarity`.

**Learning objectives:**
- State the null hypothesis of ADF and of KPSS, and explain why they're
  opposites rather than redundant.
- Read a four-way stationarity verdict (both agree stationary, both agree
  non-stationary, or either disagreement) and know what each implies.
- Interpret mean-reversion half-life as a real, physically meaningful
  number, and its confidence interval as "how precisely do we actually
  know that."

**The villainous example:** **Death-Ray Revenue** (weekly income from
renting out the Secret Lab™'s death ray to other operations, trending
steadily upward as our heroine's reputation — and rental prices — grow.
This is the book's first deliberately *non-stationary* series, introduced
here and reused through Part III as the flagship "let's build a real model
for this" example).

**Gotchas & rationale:**
- A series can clear `p < 0.05` on ADF while reverting to its mean so
  slowly (a long half-life) that "stationary" is technically true and
  practically useless for a 30-day forecast — the effect size is what
  actually tells you this, not the p-value.
- Under a genuine unit root, the OLS mean-reversion coefficient is known
  to skew slightly *negative* in finite samples even with zero true
  reversion — so a small negative lambda is not proof of "no reversion,"
  and the book explicitly warns against that intuitive-but-wrong reading.
- KPSS's own p-value is coarse (interpolated from four lookup-table
  points, clipped at the edges) — two very different series can both
  report `p=0.01`, and only the effect size distinguishes "barely past
  the boundary" from "wildly past it."

**Sample prompts:**
- "Is the death-ray revenue series stationary? If ADF and KPSS disagree,
  what should I do about it?"
- "What's the mean-reversion half-life here, and how confident should I be
  in that number specifically?"

---

### Chapter 5: The Rhythm of Evil — Seasonality Detection & Decomposition

**Concept(s) taught:** Additive decomposition (trend + seasonal + residual);
periodograms and spectral power as a way to *find* a seasonal period rather
than assume one; a real, formal significance test for "is this periodicity
real" (Fisher's g-test) instead of eyeballing a chart.

**Omen tools used:** `ts-analyst__seasonal_decomposition_summary`,
`ts-analyst__detect_seasonality_period`.

**Learning objectives:**
- Decompose a series into trend/seasonal/residual components and describe
  what each captures.
- Use a periodogram-based search to find a candidate seasonal period
  without supplying one in advance.
- Explain why the single strongest frequency in a periodogram can
  correspond to a series' trend, not its seasonality — and how to avoid
  that trap.

**The villainous example:** **Henchman Costume Dry-Cleaning Bills** (weekly
spend, with an unmistakable spike every October as costumes go out for
Halloween-adjacent "public appearances," plus a slower creeping increase
as the henchman roster grows).

**Gotchas & rationale:**
- The globally strongest frequency in a raw periodogram is often the
  series' own trend (a period near the full series length), not its real
  seasonal cycle — demonstrated directly on the dry-cleaning series, where
  the trend nearly outranks the genuine 52-week cycle.
- The reported significance test uses a standard conservative
  approximation of Fisher's g-test, not the full exact formula — good
  enough for "is there real periodicity here," not precise enough for a
  borderline academic claim.

**Sample prompts:**
- "Find the dominant seasonal cycle in the dry-cleaning series without
  telling the tool to expect a 52-week period."
- "Is the strongest signal in the periodogram actually the seasonality, or
  could it be something else?"

---

### Chapter 6: Echoes — Autocorrelation and the ACF/PACF

**Concept(s) taught:** Autocorrelation and partial autocorrelation as
"how much does this series remember its own past"; why the correct
significance threshold for a lag *grows* with earlier lags (Bartlett's
formula) rather than staying constant; how ACF/PACF shape hints at model
order, as a bridge into Part III.

**Omen tools used:** `ts-analyst__acf_pacf_summary`.

**Learning objectives:**
- Read an ACF/PACF plot (or its numeric summary) and identify the
  strongest significant lags.
- Explain why a uniform `1.96/√n` significance threshold is only exactly
  correct at lag 1, and what goes wrong if you apply it uniformly anyway.
- Connect an ACF/PACF pattern to an intuition about which model family
  (AR-like, MA-like, seasonal) might fit.

**The villainous example:** Reuses the **Henchman Costume Dry-Cleaning
Bills** series from Chapter 5, specifically so readers can see the *same*
data teach two different lessons back to back.

**Gotchas & rationale:**
- On this exact series, a uniform threshold incorrectly ranks the weekly
  seasonal lag as the single strongest signal; the correct, Bartlett-based
  per-lag threshold ranks lag 1 as strongest instead, because lag 1's own
  standard error is the tightest (nothing earlier is inflating it) — a
  worked example of a *real* correctness bug this exact toolkit shipped
  and fixed, not a hypothetical.
- `acf()`'s confidence intervals are centered on the estimated ACF value
  itself, not on zero — a subtlety that trips up anyone computing
  significance by comparing against the raw interval bounds directly
  instead of the interval's half-width.

**Sample prompts:**
- "Which lags are statistically significant in the dry-cleaning series,
  and how much does the required threshold change as the lag grows?"
- "Based on the ACF/PACF shape alone, would you guess this series needs an
  AR term, an MA term, or both?"

---

### Chapter 7: Spikes and Regime Changes — Anomaly and Changepoint Detection

**Concept(s) taught:** The difference between a point anomaly (one
weird day) and a changepoint (a lasting shift in level) as genuinely
different phenomena needing different tools; robust statistics (median/MAD)
versus classical statistics (mean/std) and why the robust version exists;
permutation testing as a way to get a p-value without assuming a
closed-form distribution.

**Omen tools used:** `ts-analyst__detect_anomalies_zscore`,
`ts-analyst__detect_anomalies_robust_zscore`,
`ts-analyst__detect_changepoints`.

**Learning objectives:**
- Distinguish "one point is weird" from "the series' baseline permanently
  moved," using both a rolling z-score and CUSUM/permutation-based
  changepoint detection.
- Explain self-dilution: how a naive rolling z-score can under-report the
  very anomaly that's inflating its own window's standard deviation.
- Interpret Cohen's d as reported for a detected changepoint, and
  understand the explicit limitation that per-split p-values aren't a
  global significance guarantee across all detected breaks.

**The villainous example:** **Secret Lab™ Power Consumption** (daily
kilowatt-hours) — a huge one-day spike when the death ray misfires
(anomaly), *and*, later in the same series, a permanent step up in
baseline consumption after annexing a rival's lair and its equipment
(changepoint) — deliberately containing both phenomena so the chapter can
show why one tool would miss what the other catches.

**Gotchas & rationale:**
- Demonstrated with real numbers: an injected +500 spike on a
  ~200-scale series only scores a rolling z-score of ~3.4 (barely over the
  default threshold of 3.0) because the spike inflates its own window's
  standard deviation — while the robust, MAD-based version scores the
  *same* spike at ~17, correctly flagging it as unmissable.
- The changepoint detector answers a different question than either
  anomaly detector — a huge isolated spike can trip an anomaly detector
  without being a real changepoint, and a modest sustained shift can be a
  real changepoint without tripping either anomaly detector.

**Sample prompts:**
- "Does the power consumption series have any anomalous days? Check with
  both the standard and the robust detector — do they agree?"
- "Separately, has the series' baseline level permanently shifted at any
  point? What's the effect size of that shift?"

---

## Part III — Building and Judging Candidate Models
*(`ts-forecaster`, Layer 2)*

### Chapter 8: The Floor Is Naive — Baselines You Must Beat

**Concept(s) taught:** Why every "real" model must be benchmarked against
trivial baselines; the difference between a flat naive forecast and a
seasonal-naive forecast; MAE, RMSE, and MAPE as complementary error
metrics with different failure modes.

**Omen tools used:** `ts-forecaster__fit_naive_baselines`.

**Learning objectives:**
- Compute and interpret naive and seasonal-naive backtest error.
- Explain why MAPE excludes near-zero actual values, and what that means
  for series that legitimately hit zero.
- Understand bootstrap confidence intervals on a backtest metric, and why
  a 30-point holdout's error estimate has real sampling uncertainty of its
  own.

**The villainous example:** **Death-Ray Revenue** (weekly total rental
income collected, introduced in Chapter 4, now getting its first real
backtest).

**Gotchas & rationale:**
- A model that "beats naive" by a numerically tiny margin (say 4.8% MAPE
  vs. 5.0%) hasn't necessarily beaten it in any *meaningful* sense until
  you've seen the bootstrap CI on both — this chapter plants the seed
  Chapter 12 pays off with a formal test.
- MAPE's near-zero exclusion is reported explicitly as a count, not
  silently — a series with several genuinely zero weeks (a slow month for
  death-ray bookings) will have some points quietly excluded from the
  MAPE calculation, and the tool says exactly how many.

**Sample prompts:**
- "Fit naive and seasonal-naive baselines on the death-ray revenue series.
  Which one wins, and by how much?"
- "How wide is the confidence interval on that baseline's own MAPE?"

---

### Chapter 9: Smoothing Things Over — Exponential Smoothing (ETS)

**Concept(s) taught:** Exponential smoothing / Holt-Winters as a
trend+seasonal model family; AIC and AICc as small-sample-corrected model
fit criteria; residual diagnostics (Ljung-Box) as a check for "did the
model leave structure on the table."

**Omen tools used:** `ts-forecaster__fit_ets`.

**Learning objectives:**
- Fit an ETS model with trend/seasonal/damping options and explain what
  each option changes.
- Read `aic` vs. `aicc` and explain when AICc's correction actually
  matters (small training windows relative to parameter count).
- Interpret a Ljung-Box test result and its effect size, and explain what
  a *low* p-value means for residuals specifically (the model missed
  something), as opposed to a low p-value on the original series.

**The villainous example:** Continues **Death-Ray Revenue**.

**Gotchas & rationale:**
- ETS's prediction interval is *simulated* (many future paths, then
  percentiles), not analytic — meaning it can occasionally fail for a
  given parameter combination, in which case the tool falls back to a
  point-forecast-only result rather than erroring out, and says so
  explicitly.
- `backtest_interval_coverage` checks the simulated interval against real
  holdout values *during backtesting* — catching a badly calibrated
  interval before it ever ships, rather than waiting for production
  monitoring to notice weeks later.

**Sample prompts:**
- "Fit ETS on the death-ray revenue series. Does its prediction interval
  actually cover close to 95% of the holdout, or is it miscalibrated?"
- "Do the residuals look like white noise, or is the model still missing
  something?"

---

### Chapter 10: SARIMA and the Order-Selection Ritual

**Concept(s) taught:** ARIMA/SARIMA notation (p,d,q)(P,D,Q,s) as a
generalization of what Chapters 4 and 6 already taught (differencing for
stationarity, AR/MA order from ACF/PACF shape); grid search as an advisory
tool, not a replacement for that reasoning.

**Omen tools used:** `ts-forecaster__fit_sarima`,
`ts-forecaster__search_sarima_orders`.

**Learning objectives:**
- Translate Chapter 4's stationarity findings directly into a SARIMA `d`
  and seasonal `D`, rather than guessing.
- Fit a SARIMA model and read its analytic prediction interval and
  interval coverage.
- Use `search_sarima_orders` to shortlist `(p,q)(P,Q)` candidates and
  explain why it deliberately does *not* search `d`/`D` and does *not*
  crown a single winner automatically.

**The villainous example:** Continues **Death-Ray Revenue**.

**Gotchas & rationale:**
- A worked, real example where the numerically best-AICc candidate from
  `search_sarima_orders` comes back with `residuals_look_like_white_noise:
  false` — ranked first, structurally deficient — making the book's point
  about grid search concretely, not just in theory.
- SARIMA's confidence interval is analytic (no simulation needed, unlike
  ETS) — a nice contrast for readers to hold both approaches in mind at
  once.

**Sample prompts:**
- "Given that Chapter 4 found this series non-stationary with `d=1`, fit
  SARIMA using that differencing order rather than guessing."
- "Run an advisory order search. Does the best-ranked candidate actually
  have clean residuals, or does it just have the best AICc?"

---

### Chapter 11: Teaching Trees to Predict the Future — Gradient Boosted Trees

**Concept(s) taught:** Framing time series forecasting as supervised
learning on lag and calendar features; feature importance as a model
explanation tool; the crucial evaluation-setting distinction between
one-step-ahead (true lagged values) and recursive multi-step (predictions
feeding back into their own lag features) forecasting.

**Omen tools used:** `ts-forecaster__fit_gradient_boosted_trees`.

**Learning objectives:**
- Construct lag and calendar features for a tree-based model, conceptually.
- Explain why this layer's GBT backtest is evaluated one-step-ahead, and
  why that makes its error numbers an "easier" evaluation setting than
  ETS/SARIMA's genuine multi-step forecast.
- Read feature importances and describe what they do and don't tell you
  about causality.

**The villainous example:** **Minion Overtime Hours** (daily hours,
strongly driven by day-of-week and a monthly "quota deadline" calendar
effect — chosen specifically because calendar features carry real signal
here, unlike a smoothly trending series).

**Gotchas & rationale:**
- This chapter's central warning, stated plainly and revisited in Chapter
  14: GBT's backtest number here is *not* directly comparable to ETS's or
  SARIMA's multi-step backtest, because it's evaluated under an easier
  setting (true lagged values, not its own recursive predictions) — a
  model can look deceptively strong here and compound errors badly once
  actually deployed recursively.

**Sample prompts:**
- "Fit gradient-boosted trees on the minion overtime series and show me
  which features matter most."
- "Explain why this model's backtest error isn't a fair apples-to-apples
  comparison against the SARIMA model from Chapter 10."

---

### Chapter 12: Statistically Better, or Just Different? — Diebold-Mariano Testing

**Concept(s) taught:** Formal hypothesis testing for "is Model A actually
better than Model B," as opposed to eyeballing two error numbers;
autocorrelated forecast errors and why they need a HAC-robust (Newey-West)
variance estimate rather than a naive t-test.

**Omen tools used:** `ts-forecaster__diebold_mariano_test`.

**Learning objectives:**
- State what the Diebold-Mariano test actually compares (loss
  differential, not raw error).
- Explain why forecast errors from a multi-step backtest are typically
  autocorrelated, and why that breaks a naive independent-samples test.
- Correctly choose between the default autocorrelation-aware lag
  selection and `n_lags=0` for two one-step-ahead backtests specifically.

**The villainous example:** Pits **SARIMA vs. seasonal-naive** on the
Death-Ray Revenue series head-to-head — deliberately reusing a case
where the "fancier" model does *not* actually win, so the lesson lands
with real stakes instead of a foregone conclusion.

**Gotchas & rationale:**
- The book's single best "gotcha" story: SARIMA can lose to
  seasonal-naive *significantly* (a real, documented p=0.0015 result
  against this project's own synthetic data) — exactly the kind of
  finding "the error was numerically lower" would let you miss if you
  went the other direction and quietly deployed SARIMA anyway.
- A cautionary tale from the toolkit's own development: an earlier version
  of this exact test had a subtle but total bug (a small-sample correction
  that silently zeroed out under the toolkit's actual backtest structure,
  making every result non-significant regardless of the data) — caught
  before shipping, and worth walking through as a lesson in verifying a
  statistical implementation algebraically, not just running it once and
  trusting the output.

**Sample prompts:**
- "Is SARIMA's backtest error significantly different from seasonal-naive's,
  or could the gap just be noise?"
- "If I wanted to compare two one-step-ahead models instead, how would I
  need to change the test's settings, and why?"

---

### Chapter 13: Trustworthy Across Time — Rolling-Origin Backtesting

**Concept(s) taught:** Walk-forward / rolling-origin validation as a fix
for the "one lucky or unlucky holdout window" problem; stability of model
performance as its own thing to measure, separate from average accuracy.

**Omen tools used:** `ts-forecaster__rolling_origin_backtest`.

**Learning objectives:**
- Explain why a single fixed holdout window's bootstrap CI still can't
  tell you if the *window itself* was unusual.
- Run a model at multiple origins and interpret the mean/std of its
  backtest performance across them.
- Recognize when a high standard deviation across origins should worry you
  more than a mediocre average.

**The villainous example:** Continues **Death-Ray Revenue**, deliberately
walking backward across a stretch that includes an unusually good month
(a bidding war between rival factions for exclusive rental rights) and an
unusually bad one (a widely publicized death-ray malfunction that scared
off bookings for weeks) — so the instability shows up honestly in the
data, not as a contrived example.

**Gotchas & rationale:**
- The real cost of this rigor is compute: `n_origins` times the cost of a
  single fit, since each origin genuinely refits the model from scratch —
  the book frames this explicitly as "the honest price of walk-forward
  evidence," not a free lunch.
- Naive baselines are deliberately excluded from this tool — cheap,
  non-parametric baselines don't need walk-forward rigor the way a fitted
  model does, and the book explains why that's a defensible line to draw,
  not an oversight.

**Sample prompts:**
- "Run a rolling-origin backtest on the SARIMA model across 5 origins.
  Does its MAPE stay stable, or does it swing a lot between origins?"
- "If the standard deviation across origins is large, what does that
  imply about deploying this model with confidence?"

---

## Part IV — Shipping and Living With a Forecast
*(`ts-deploy` and `ts-monitor`, Layers 3–4)*

### Chapter 14: Deploying for Real — Full-Series Refits and Prediction Intervals

**Concept(s) taught:** The difference between a backtest fit (held-out data
withheld) and a deployment fit (trained on everything); prediction
intervals as first-class citizens, not an afterthought; automated
plausibility checking as a replacement for "eyeballing the chart."

**Omen tools used:** `ts-deploy__forecast_naive`, `ts-deploy__forecast_ets`,
`ts-deploy__forecast_sarima`, `ts-deploy__forecast_gradient_boosted_trees`.

**Learning objectives:**
- Explain why a deployment forecast is fit on the *entire* series, with no
  holdout, and why that's correct rather than wasteful.
- Compare interval-generation strategies across model types: analytic
  (SARIMA), simulated (ETS), and quantile-regression-based (GBT).
- Interpret a `plausibility_check` result and explain why it's a prompt
  for scrutiny, not a verdict.

**The villainous example:** **Secret Lab™ Mojito Inventory** returns —
this is the chapter where the series introduced in Chapter 3 finally gets a
real, deployed forecast, closing the loop the book opened in Chapter 1.

**Gotchas & rationale:**
- GBT's recursive multi-step forecast — direct payoff of Chapter 11's
  warning — means errors can compound as the horizon grows, a materially
  different risk than its one-step-ahead backtest ever exposed; the
  chapter shows this concretely by comparing a 5-step and a 90-step
  horizon side by side.
- GBT's prediction interval (via quantile regression) is real but
  approximate — it does not itself grow with that same recursive
  compounding risk, so the book explicitly warns against reading it with
  SARIMA's level of confidence.
- The naive forecast's own interval is a genuine textbook analytic formula
  (residual-std-based, widening with the horizon) — shown to be honestly,
  dramatically wider than any fitted model's interval, which is exactly
  the point of carrying it forward as a sanity floor.

**Sample prompts:**
- "Deploy a real forecast for mojito inventory using the model Chapter 10
  recommended. Include a naive floor alongside it."
- "Does the forecast's trajectory look plausible given the series' own
  history, or does the plausibility check flag anything?"

---

### Chapter 15: Strength in Numbers? — Ensembling Multiple Models

**Concept(s) taught:** Combining multiple forecasts into one; variance
combination under an independence assumption; the genuinely
counterintuitive result that combining two uncertain estimates can produce
a *narrower* combined interval than either alone.

**Omen tools used:** `ts-deploy__forecast_ensemble`.

**Learning objectives:**
- Combine two or more deployed forecasts with explicit or inverse-error
  weights.
- Explain, mathematically, why combining independent estimates can reduce
  combined uncertainty — and why that's an optimistic assumption in
  practice, not a free improvement.
- Decide when ensembling is appropriate (multiple candidates that each
  backtested reasonably) versus when it's a way to paper over a candidate
  that should have been rejected outright.

**The villainous example:** **Death-Ray Revenue** again, this time
combining SARIMA and ETS after Chapter 12 found no statistically
significant difference between them — the natural, honest occasion for an
ensemble, not a forced one.

**Gotchas & rationale:**
- A concrete, verified worked example: two identical components at equal
  weight combine to an interval exactly `1/√2` the width of either alone
  — the "expected effect of combining independent estimates, not a bug"
  point made with real arithmetic the reader can check by hand.
- The independence assumption is explicitly flagged as optimistic — both
  components were fit on the *same* series and share real error structure
  the combination can't see — so the combined interval is a lower bound on
  true uncertainty, not a precise one.

**Sample prompts:**
- "Combine the SARIMA and ETS forecasts for death-ray revenue into one
  ensemble. Is the combined interval narrower or wider than either
  model's own interval?"
- "Why shouldn't I trust that narrower interval quite as much as it looks
  like I should?"

---

### Chapter 16: Watching the Watchtower — Monitoring a Forecast in Production

**Concept(s) taught:** Closing the loop once real observations exist;
binomial confidence intervals on small-sample proportions (interval
coverage); distinguishing "the forecast missed a little every day" from
"the forecast was fine except one wild day."

**Omen tools used:** `ts-monitor__compare_forecast_to_actuals`.

**Learning objectives:**
- Compare a deployed forecast against real subsequent observations and
  compute elapsed-horizon error with a confidence interval.
- Interpret prediction-interval coverage, including why "100% coverage"
  from a small sample is less reassuring than it sounds.
- Use residual-outlier detection to decide whether an aggregate error
  figure is being driven by one unusual day.

**The villainous example:** **Secret Lab™ Mojito Inventory**, one month
after Chapter 14's deployment — real observations have accumulated, and
one of them coincides with an unplanned "product testing event" (a party)
that blew through normal demand for exactly one day.

**Gotchas & rationale:**
- A real, verified example: 10-for-10 matched points inside their interval
  reports as "100% coverage" — but with only 10 points, the Wilson score
  confidence interval on that figure is a startlingly wide `[72%, 100%]`,
  meaning the calibration read is genuinely provisional this early.
- The residual-outlier check exists specifically because these two
  failure modes call for different responses: a single-day miss from an
  unusual event isn't evidence the *model* needs retraining, but a
  systematic daily miss is.
- A documented edge case worth knowing about: if half or more of the
  matched residuals are exactly identical (an unusually "too-perfect"
  forecast on most days), the median-absolute-deviation-based outlier
  check can degenerate and miss a real outlier — a known limitation, not
  a bug to paper over.

**Sample prompts:**
- "Compare the mojito forecast against what actually happened. How wide is
  the confidence interval on that error?"
- "Is the elapsed-horizon error being driven by one unusual day, or is it
  spread evenly across the month?"

---

### Chapter 17: When to Sound the Alarm — Drift Detection and Its Blind Spots

**Concept(s) taught:** Statistical tests for distributional drift (Welch's
t-test, Kolmogorov-Smirnov); the crucial distinction between "the test
fired" and "something is actually wrong," using effect size to tell them
apart; walk-forward validation applied to monitoring itself, not just
backtesting.

**Omen tools used:** `ts-monitor__detect_data_drift`,
`ts-monitor__rolling_drift_check`, `ts-monitor__recommend_retraining`.

**Learning objectives:**
- Run a drift check between a recent window and a reference window, and
  read both the p-values and the effect sizes.
- Explain, with a real example, why an ordinary trend can trigger a drift
  flag with zero anomalous behavior present.
- Use a rolling, multi-window drift check to distinguish a sustained shift
  from a one-off blip.
- Read `recommend_retraining`'s four possible verdicts and the signal
  combinations behind each.

**The villainous example:** **Interpol Attention Level** (a weekly
"heat" index our heroine tracks about her own operation) — genuinely
trending upward over time as the Secret Lab™'s ambitions grow, which is
exactly the shape that exposes the drift detector's real, documented blind
spot.

**Gotchas & rationale:**
- Shown with real numbers: the unmodified, merely-trending Interpol series
  reports `mean_shift_cohens_d ≈ -0.42` (small-to-medium) while injecting
  an actual, obvious level shift on top of it pushes that to `≈ 7.06`
  (enormous) — both flag `drift_detected: true`, and only the effect size
  tells a reader which is a rounding error and which is a five-alarm fire.
- `rolling_drift_check`, run across this same series, correctly flags the
  ongoing trend as *persistent* (drift shows up in every window checked)
  rather than a one-off blip — the right conclusion, arrived at
  correctly, even though "drift" here is really just "an ordinary trend
  continuing."
- `recommend_retraining` can flag its own verdict as sensitive to sampling
  noise when a bootstrap CI on the degradation estimate straddles the
  decision threshold — worth reading as "this call is close," not
  papering over the ambiguity with false confidence.

**Sample prompts:**
- "Check the Interpol attention series for drift. Is the flag driven by a
  genuine regime change, or could it just be the ongoing trend?"
- "Run a rolling drift check across several windows. Does the shift show
  up consistently, or only once?"
- "Given everything above, what does `recommend_retraining` actually
  suggest doing next?"

---

## Part V — The Retrain Decision and Beyond
*(`ts-retrain`, Layer 5)*

### Chapter 18: Should You Even Redeploy? — Deterministic Gates and Confidence-Aware Comparisons

**Concept(s) taught:** Deterministic decision functions as a deliberate
design choice, not a missed opportunity for "smarter" agent judgment;
requiring a *meaningful* improvement threshold, not just any improvement;
combining two independent confidence intervals via interval arithmetic
(as distinct from Chapter 15's variance combination, and why the
difference matters for a ratio-shaped quantity).

**Omen tools used:** `ts-retrain__load_deployment_manifest`,
`ts-retrain__compare_candidate_to_deployed`.

**Learning objectives:**
- Explain why "should we redeploy" is treated as a rule-based decision
  in Omen rather than left to LLM judgment, and articulate the general
  principle behind that choice.
- Compute an improvement-threshold comparison and recognize when a
  bootstrap CI on that comparison straddles the decision threshold.
- Understand why combining two ratio-shaped confidence intervals correctly
  requires worst-case/best-case corner reasoning, not a variance-additive
  shortcut.

**The villainous example:** **Death-Ray Revenue**, revisited one
"regime change" later — a rival supervillain has started renting out a
competing death ray at cut-rate prices, and our heroine needs to know
whether a freshly retrained model actually
adapts to the new competitive landscape enough to be worth redeploying.

**Gotchas & rationale:**
- A real, verified worked example: a candidate at 6.0% MAPE (CI `[5.0,
  7.0]`) against a deployed model at 10.0% implies a `[30%, 50%]`
  improvement range alone — and widens to `[22.22%, 54.55%]` once the
  deployed model's *own* uncertainty is folded in too, using proper
  worst-case/best-case interval arithmetic rather than a one-sided
  simplification.
- Marginal improvements are rejected on principle, by design — redeploying
  and resetting the monitoring baseline over noise-level differences is
  explicitly framed as "how you end up chasing your own tail."

**Sample prompts:**
- "Compare this freshly retrained candidate against what's currently
  deployed. Does it clear the redeploy threshold?"
- "Given both models' own confidence intervals, how much does that
  widen the range around the improvement estimate?"

---

### Chapter 19: The Suspicious Foreman — Human Confirmation and (Careful) Autonomy

**Concept(s) taught:** Action-gating as a design pattern for any agentic
tool, not just this one; the difference between a prose-enforced contract
and a code-enforced one; durable, inspectable state as an alternative to
trusting an agent's memory of a conversation.

**Omen tools used:** `ts-retrain__execute_redeploy`,
`ts-retrain__authorize_autonomous_mode`, `ts-retrain__revoke_autonomous_mode`,
`ts-retrain__check_autonomous_mode`.

**Learning objectives:**
- Explain why exactly one tool in the entire toolkit is allowed to change
  a live deployment, and why it refuses to act without an explicit
  `confirmed=True`.
- Set up, verify, and revoke a standing autonomous-mode authorization for
  a specific series.
- Articulate, generally, why "the agent remembers being told this is
  fine" is a weaker guarantee than "a file on disk says this is fine" —
  and when that distinction actually matters.

**The villainous example:** **Self-Destruct Countdown Timer Adjustments**
(a wonderfully on-the-nose dataset for a chapter about who's allowed to
authorize an unattended action) — has anyone actually authorized the lab's
systems to reset the countdown automatically when conditions look safe, or
is that decision supposed to require a human hand on the actual button
every time?

**Gotchas & rationale:**
- Demonstrated as a real, run sequence: an unauthorized autonomous call
  refuses with a clear error; authorizing it and retrying succeeds;
  revoking authorization and trying a third time refuses again,
  immediately — proof the check is real code, not a description of
  intended behavior.
- The authorization record and the deployment manifest are deliberately
  two separate files, not one field bolted onto the other — because
  authorization and deployment are different concerns with different
  lifecycles, and conflating them would mean revoking one accidentally
  touches the other.
- Ordinary human-confirmed calls never touch this machinery at all — a
  human's in-conversation "go ahead" remains its own complete
  authorization, which the chapter frames as the sane default precisely
  because it requires no setup to be safe.

**Sample prompts:**
- "Try to redeploy without confirming. What happens?"
- "Authorize autonomous mode for this series, then retry the same
  unattended redeploy — does it succeed now?"
- "Revoke that authorization and try once more. Does it correctly refuse
  again right away?"

---

## Part VI — Becoming a Better Forecasting Villain

### Chapter 20: Prompting Omen Like You Mean It

**Concept(s) taught:** Practical prompt craft for a multi-tool agentic
pipeline: being specific about which layer's judgment you want, carrying
settings forward between layers instead of re-deriving them, and recognizing
when a tool's own output is telling you something the prompt didn't ask
for.

**Omen tools used:** A deliberate mixed review across all five layers.

**Learning objectives:**
- Write prompts that carry Layer 1's findings into Layer 2's model choice,
  rather than starting from scratch.
- Recognize the difference between a prompt that under-specifies (leading
  to arbitrary defaults) and one that over-specifies (defeating the
  point of asking an agent to reason at all).
- Use `prompts/testing-and-learning-prompts.md` as a springboard for
  writing your own.

**The villainous example:** A "clinic" chapter — takes three real, submitted
example prompts (deliberately including one vague one and one overly
rigid one) and rewrites each, explaining the fix, using series introduced
in earlier chapters as the working material rather than introducing a new
one.

**Gotchas & rationale:**
- A vague prompt ("forecast this") pushes model selection onto whatever
  default the agent happens to reach for, silently defeating Part II and
  III's entire lesson about grounded model choice.
- An overly rigid prompt (hand-specifying every parameter) defeats the
  point of using an agent at all — the book draws the line between
  "specify the constraint, let the agent reason within it" and
  "micromanage every keystroke."

**Sample prompts:**
- (This chapter's exercises *are* prompt-writing exercises — readers are
  asked to draft and then critique their own.)

---

### Chapter 21: When to Trust the Agent, and When Not To

**Concept(s) taught:** A retrospective, cross-cutting look at every
deliberately-deterministic decision point encountered in the book
(`recommend_retraining`, `compare_candidate_to_deployed`, the
`confirmed=True` gate, autonomous-mode authorization) as instances of one
general design principle, generalized into a checklist readers can apply
to their *own* agentic tools, not just Omen.

**Omen tools used:** None new — this is a synthesis chapter.

**Learning objectives:**
- Articulate a general rule for "when should a decision be rule-based
  instead of agent-judged" and test it against several examples from the
  book.
- Recognize the pattern in Omen's own layer boundaries as evidence for
  that rule, not just as this toolkit's arbitrary house style.

**The villainous example:** No new dataset — a structured retrospective
across every dataset used so far, framed as "the postmortem meeting our
heroine holds after any operation."

**Gotchas & rationale:**
- The chapter's central thesis, stated directly: reproducibility given the
  same inputs is the dividing line — decisions worth being reproducible
  (should we retrain? should we redeploy?) get rule-based functions;
  decisions that genuinely benefit from open-ended reasoning (does this
  model family fit this series' shape?) stay with the agent.

**Sample prompts:**
- "Looking back at everything this book covered, list every point where
  Omen deliberately took a decision away from agent judgment. What do
  they have in common?"

---

### Chapter 22: Conclusion

**Concept(s) taught:** A wrap-up, not a new concept — consolidates the
book's arc from "look before leaping" through "should you even redeploy."

**Content:**
- A full recap of the five-layer pipeline in light of everything the
  reader now knows in depth, not just the Chapter 1 preview.
- A pointer back to the companion blog post series (`blog-posts/`) for
  readers who want the same material in a shorter, funnier form, plus a
  pointer to `AGENTS.md` for readers who want to go build on Omen
  directly.
- A closing status update on the running examples: the mojito stockout
  problem from Chapter 1 is solved; the death-ray rental market's rival
  supervillain from Chapter 18 is still out there, which is the honest,
  open-ended note
  a book about *forecasting* — not fortune-telling — should end on.
- A short "where the toolkit itself goes next" section, pulled honestly
  from Omen's own real, currently-open items (no CI pipeline yet, no
  expiry on autonomous-mode grants, PyPI publishing still pending) rather
  than invented future features — modeling, one last time, the book's own
  running lesson about not overclaiming certainty.

**Sample prompts:**
- "Summarize everything you now know about this series across all five
  layers, as if handing off to another analyst who's never seen it."

---

## Appendices

- **Appendix A — Glossary.** Every statistical term introduced across the
  book (stationarity, effect size, AICc, HAC-robust variance, Wilson score
  interval, etc.), defined in one or two sentences each, cross-referenced
  to the chapter that introduced it.
- **Appendix B — Tool Reference Table.** Every MCP tool used in the book,
  grouped by layer, with a one-line description and the chapter(s) that
  cover it — a fast lookup companion once readers start working with their
  own data instead of the book's examples.
- **Appendix C — Further Reading.** The academic sources this toolkit's own
  methods are drawn from (Dickey & Fuller; Kwiatkowski, Phillips, Schmidt &
  Shin; Fisher's 1929 g-test; Diebold & Mariano 1995; Iglewicz & Hoya 1993;
  Hurvich & Tsai 1989), plus the companion blog post series and
  `prompts/testing-and-learning-prompts.md` for continued practice.
