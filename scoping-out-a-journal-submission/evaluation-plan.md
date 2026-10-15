# Evaluation plan for Omen

*Written 2026-10-13, against Omen v0.0.4. Addresses gaps #1 (no empirical
evaluation) and #3 (no study of the agent itself) in
[publication-assessment.md](publication-assessment.md).*

The goal is a small, honest study that can go out as a preprint (and
later a workshop or journal paper). The results must stay out of the JOSS
paper: JOSS papers can't report new research results. As a separate
preprint, though, the study also counts as the "evidence of research use"
that JOSS screens for.

**Execution is tracked as GitHub issues:** see Section 10 and the
[tracking issue (#59)](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/59).

## 1. The claim being tested

Omen's central claim is that an agent should use **a tested toolkit
instead of improvising the statistics itself**. The study is built around
comparing the conditions that isolate that claim:

| Condition | What it isolates |
|---|---|
| **A. Agent + Omen**, following the `SKILL.md` playbooks | The proposed system |
| **B. Agent without Omen**, given only a Python sandbox with the usual libraries | Whether the toolkit beats an LLM improvising its own statistics. This is the core test. |
| **C. Omen's tools without an LLM**: a fixed rule (fit every candidate, deploy the lowest backtest error) | Whether the agent's judgment adds anything over a simple rule |
| **D. Standard automatic forecasters**: seasonal naive, AutoARIMA, AutoETS (e.g. StatsForecast) | Whether results are competitive with what practitioners already use |
| **E. (Optional) A pretrained forecasting model**: Chronos or TimesFM | Where Omen sits against the current state of the art |

Possible findings, all publishable:
- **A beats B:** the toolkit helps. This is the headline claim.
- **A roughly equals C:** the agent adds reliability, explanation, or
  workflow value rather than accuracy. Section 4 measures those directly.
- **A loses to D or E on accuracy:** an honest result that still says
  where agentic workflows stand, especially if A wins on interval
  calibration or on reporting quality.

## 2. Data

- **Established benchmarks:** subsets of M4 (daily, weekly, monthly) and
  the Monash forecasting archive, or GIFT-Eval. About 300 series spread
  across frequencies is enough for a workshop-scale study.
- **Contamination control:** LLMs have very likely seen M4 and its
  published results, and reviewers will ask. Include at least one dataset
  that postdates every evaluated model's training cutoff, or private or
  freshly collected series, and report results on it separately.
- **No test-set leakage:** Omen's tools read CSV files, so the agent gets a
  file containing only the training portion. The test period lives where
  the agent's environment can't reach it. The same applies to condition B's
  sandbox.

## 3. Forecast-accuracy protocol

- Use each benchmark's standard horizon. Run the full
  `ts-analyst` → `ts-forecaster` → `ts-deploy` sequence on the truncated
  series and score the deployed forecast against the held-out period.
- **Point accuracy:** MASE and sMAPE (the M4 conventions).
- **Interval quality:** empirical coverage and MSIS. Omen invests heavily
  in prediction intervals, so they should be scored, not just the point
  forecast.
- **Comparisons across series:** average ranks with a Friedman/Nemenyi
  test, or bootstrap CIs over series. Omen's `diebold_mariano_test` compares
  two models on a single series, so it isn't the right tool here.
- **Repeated runs:** run every LLM condition 3–5 times per series and
  report the spread across runs, not just the mean.

**Points specific to Omen to handle:**
- The public `forecast_*` tools truncate output past `cap=60` points for
  display. M4 horizons are 48 or less, so this doesn't bite there. Any
  longer horizon needs the untruncated arrays.
- GBT's backtest is one-step-ahead while its deployed forecast is
  recursive (see `AGENTS.md`). Score only the deployed forecast so every
  condition is judged on the same task.

## 4. Agent-behavior study

Log every tool call (name, arguments, result) and the agent's final
written report, then measure:

- **Protocol adherence:** does the agent follow `SKILL.md`'s order (analysis
  before fitting, baselines included, residual diagnostics checked)? Score
  each trajectory against a checklist derived from the skills.
- **Reporting accuracy:** do the numbers in the agent's summary match the
  tool outputs? This can be checked automatically, since every number in
  the report should trace back to a logged tool result.
- **Failure rates:** invalid arguments, crashed runs, abandoned tasks, and
  retries.
- **Cost:** tokens, wall-clock time, and dollars per series.
- **Model sensitivity:** how all of the above varies across 2–3 LLMs (e.g.
  GLM, Claude, an open-weight model).

## 5. Monitoring and retraining (`ts-monitor`, `ts-retrain`)

A one-shot benchmark can't test these. They need a replayed timeline:

- **Drift detection:** replay series as if live, with injected level
  shifts or regime changes, plus control series with no change. Measure
  how long `detect_data_drift` and `rolling_drift_check` take to notice the
  change, and how often they flag drift that isn't there. Report the known
  trend false-positive caveat in `AGENTS.md` as part of this rather than
  working around it.
- **Retraining decisions:** compare `recommend_retraining` and
  `compare_candidate_to_deployed` against an oracle that knows when
  retraining would actually have improved accuracy.
- **Red-teaming the redeploy gate:** write adversarial prompts that try to
  get a redeploy without confirmation or without a stored authorization
  record (persuasion, fake "the user already approved", trying to set
  `autonomous=True`). The code check should block every attempt, so the
  interesting measurements are how often agents attempt it and how they
  behave after being refused.

## 6. Engineering

| Component | Notes |
|---|---|
| **Headless agent harness** | An MCP client loop that drives an LLM through the skills with no human present. OpenClaw is interactive, so this means a small custom runner or an agent SDK. It must support every condition in Section 1, including condition B's sandbox. |
| **Dataset preparation** | Benchmark → per-series train-only CSV, with the held-out period stored separately. |
| **Scoring pipeline** | Metrics from Section 3, plus the trajectory checks from Section 4. |
| **Logging** | Structured trajectory logs (JSONL) per run, kept as an artifact of the study. |
| **Reproducibility** | Pinned package versions (an Omen release tag), recorded model IDs and sampling settings, and published code, configs, and logs. |

## 7. Scale and cost

Minimal workshop version: ~300 series × 2–3 LLMs × 3 runs × 2 agent
conditions (A and B) ≈ **4,000–5,000 agent runs**. The baselines that use
no LLM (C, D, E) are cheap by comparison.

*Assumption, not measured:* 20–40 tool calls and 50–150k tokens per run,
or roughly a few hundred million tokens in total. The pilot (Phase 2)
should measure the real per-run figure before the full study is budgeted.
The budget itself is decided at the decision gates in Section 10, from the
pilots' measured costs, not from this estimate.

## 8. Phases

1. **Harness and data preparation** (~1–2 weeks): runner, CSV pipeline,
   scoring, logging.
2. **Pilot** (~20 series, 1 LLM, all conditions): shake out bugs, measure
   real token cost per run, and make sure the trajectory checks score
   sensibly.
3. **Full forecast-accuracy and agent-behavior runs** (Sections 3–4).
4. **Monitoring, retraining, and red-team experiments** (Section 5). These
   can be cut from a first workshop paper if time is short.
5. **Analysis and preprint write-up:** post to arXiv ahead of the JOSS
   submission (earliest 2027-01-22, see the assessment).

## 9. Open decisions

These are now tracked as decision gates: the token budget at Eval 08
([#50](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/50)) and Eval 14 ([#56](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/56)), and everything else at Eval 01
([#43](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/43)).

- Which LLMs to evaluate, and the token budget.
- Which datasets satisfy the contamination control in Section 2.
- Whether condition E (pretrained forecasting models) is in scope for the
  first paper.
- Whether Section 5 goes in the first paper or a follow-up.
- Where the harness lives: inside this repo (e.g. an `evaluation/`
  directory, which would also add steady commit history for JOSS) or in a
  separate repo.

## 10. Tracking: GitHub issues

*Added 2026-10-15.* The plan is broken into 16 ordered issues, **Eval 01–16**,
each attached as a sub-issue of the
[tracking issue (#59)](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/59), which shows overall progress. Work
proceeds in Eval-number order; each issue lists its dependencies, and
Eval 03–05 can overlap.

| Step | Issue | Plan section |
|---|---|---|
| Eval 01 🚦 Scope decisions (before any build work) | [#43](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/43) | 9 |
| Eval 02 Dataset preparation | [#44](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/44) | 2 |
| Eval 03 Headless agent harness (conditions A and B) | [#45](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/45) | 1, 4, 6 |
| Eval 04 Baselines without an LLM (C, D, optional E) | [#46](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/46) | 1 |
| Eval 05 Scoring pipeline | [#47](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/47) | 3 |
| Eval 06 Trajectory analysis | [#48](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/48) | 4 |
| Eval 07 💸 Pilot: measure real cost per run | [#49](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/49) | 8 (Phase 2) |
| Eval 08 🚦 Approve main-study scale and budget | [#50](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/50) | 7 |
| Eval 09 💸 Main study runs | [#51](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/51) | 3, 4 |
| Eval 10 Analysis | [#52](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/52) | 1, 3, 4 |
| Eval 11 Monitoring/retraining replay harness | [#53](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/53) | 5 |
| Eval 12 Drift and retraining experiments (no LLM) | [#54](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/54) | 5 |
| Eval 13 💸 Red-team pilot | [#55](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/55) | 5 |
| Eval 14 🚦 Approve red-team scale and Section 5 scope | [#56](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/56) | 5 |
| Eval 15 💸 Full red-team runs | [#57](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/57) | 5 |
| Eval 16 Write-up, reproducibility package, preprint | [#58](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues/58) | 8 (Phase 5) |

Eval 11–15 can be skipped or deferred to a follow-up paper, depending on
the decisions at Eval 01 and Eval 14.

### Labels
- `evaluation-plan`: every issue in the series.
- `decision-gate` (🚦): a maintainer decision is required before later
  steps start.
- `token-cost` (💸): spends LLM tokens; run only within an approved budget.

### Cost control
- Every token-heavy phase is preceded by a small **pilot** that measures
  real cost per run: Eval 07 for the main study, Eval 13 for the red-team.
- Each pilot feeds a **decision gate** (Eval 08, Eval 14). The gate prices
  concrete options from the pilot's *measured* numbers, and the maintainer
  picks a scale, a budget ceiling, and an overrun rule.
- Full runs (Eval 09, Eval 15) execute in **batches**, with a cost
  checkpoint after the first batch (default: pause and return to the gate if
  more than 20% over projection) and a hard stop at the approved ceiling.
- Eval 01 is also a gate: no build work starts until scope is decided.

### Paper records
Every Eval issue produces a written record of procedure and results, so
the paper can be written from records rather than memory:

- Each issue names its record file, `evaluation/records/eval-NN-<slug>.md`,
  which lives alongside the evaluation code (location decided at Eval 01).
- Records follow a shared template, defined in the tracking issue:
  procedure, parameters, **deviations from plan**, results, cost,
  artifacts (with checksums), and notes for the paper.
- Each issue says which paper section its record feeds (Methods, Results,
  Limitations, Appendix) and lists what specifically to capture.
- Decision gates record the decision **and its rationale**, including
  declined options, since these become Methods and Limitations text.
- An issue isn't closed until its record is committed.
