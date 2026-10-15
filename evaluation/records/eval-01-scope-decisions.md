# Eval 01: Scope decisions before any build work

- Date(s): 2026-10-15
- Versions: Omen 0.0.5 (`main` at the time of decision); no code run for this step
- AI assistance for this step: Claude Code 2.1.301 with Claude Opus 5.5
  (`claude-opus-5-5`) drafted the option analysis and this record; all
  decisions were made by the maintainer. Logged in
  `scoping-out-a-journal-submission/ai-model-ledger.md`.
- Issue: #43 (tracking issue #59)
- Plan: `scoping-out-a-journal-submission/evaluation-plan.md`, Section 9

## Procedure

The maintainer chose among options presented for each open decision in
Section 9 of the evaluation plan. The token budget is deliberately **not**
decided here: it is set at Eval 08 (#50) and Eval 14 (#56) from the pilots'
measured costs.

## Decisions and rationale

### LLMs evaluated
**Decision:** GLM-5.2 and one Claude model.

- **GLM-5.2** is the pilot model (Eval 07). Omen and its `SKILL.md`
  playbooks were developed against it (via Ollama Cloud), so it is the
  model the skills were tuned on.
- **One Claude model** adds a second major model family. Which one (e.g.
  Sonnet 5.5 at mid cost, or Haiku 5.5 at low cost) is left open until the
  pilot's cost measurements are available at Eval 08.
- **Declined:** an open-weight model, and other hosted models (GPT,
  Gemini). This bounds the study to two model families. Generalization to
  other models is therefore a stated limitation, and a natural follow-up.

### Datasets and contamination control
**Decision:** M4 subsets plus a freshly collected daily contamination-control
set, reported separately.

- **M4** daily, weekly, and monthly subsets, for comparability with the
  forecasting literature (exact subset sizes and sampling are Eval 02's job).
- **Contamination-control set:** freshly collected public **daily** series
  whose held-out test periods fall entirely **after every evaluated model's
  training cutoff**, so the test values cannot have been memorized.
- **Why daily only:** at decision time (2026-10-15) only about 3–4 months
  of data exist after the June 2026 cutoff of the Claude 5 model
  generation. That is enough for daily test horizons but not for monthly
  ones, which would need data that doesn't yet exist.
- **Declined:** GIFT-Eval in place of M4 (less directly comparable to
  classic results), and M4/Monash with no contamination-control set
  (reviewers would likely push back on memorization).

### Scope of the first paper
**Decision:** the core study (Sections 3–4), plus drift/retraining (Eval
11–12), plus the red-team track (Eval 13–15).

- **Drift and retraining (Eval 11–12)** are included. They exercise Omen's
  deterministic monitoring and retraining tools with no LLM calls, so they
  are cheap, and they cover the layers that distinguish Omen from a plain
  forecasting wrapper.
- **The red-team track (Eval 13–15)** stays in the plan. The final
  scope-and-budget call is made at Eval 14, after the red-team pilot
  measures cost.
- **Declined:** condition E (pretrained forecasters such as Chronos and
  TimesFM). It needs GPU compute rather than LLM tokens and isn't needed to
  test Omen's central claim (Section 1, A vs B). It can be added in a
  follow-up.

### Where the evaluation code and records live
**Decision:** an `evaluation/` directory in this repository.

- It keeps the paper records next to the code they describe, and the
  study's development adds steady public commit history, which JOSS's
  pre-review screening checks.
- The PyPI wheel already ships only `src/omen` (`[tool.hatch.build.targets.wheel]`),
  so `evaluation/` won't reach users of the package.
- **Declined:** a separate repository (cleaner separation and its own DOI,
  but none of the JOSS-visible history).

## Deviations from plan

- **Condition E** is dropped from the first paper; Section 1 of the plan
  listed it as optional.
- The plan's example LLM list (GLM, Claude, an open-weight model) is
  narrowed to two families: GLM and Claude.

## Follow-ups created by these decisions

- **Eval 02:** look up and record GLM-5.2's training cutoff. The
  contamination-control test windows must start after the **later** of the
  two models' cutoffs.
- **Eval 02:** choose the public sources for the fresh daily series, and
  record their licenses.
- **Eval 02/03:** exclude `evaluation/` from the sdist (wheel exclusion is
  already in place), and give it its own dependency list rather than adding
  to the package's extras.
- **Eval 08:** choose the specific Claude model, using measured pilot costs.

## Results

Not applicable (decision step).

## Cost

None (no runs).

## Artifacts

- Decisions mirrored on issue #43.

## Notes for the paper

- Feeds **Methods (study design)**: the model selection, dataset selection,
  and contamination-control rationale above.
- Feeds **Limitations**: only two model families are evaluated, and
  contamination control covers only daily series. Pretrained forecasting
  models are out of scope.
