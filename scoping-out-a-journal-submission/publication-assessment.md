# Is Omen publishable in an academic journal?

*Assessment written 2026-10-13, against Omen v0.0.3.*

Short answer: yes, but probably not as a standard research paper in its
current form. Where it's a good fit depends on what kind of contribution
you claim.

## What Omen has going for it

- **A clear design idea.** Five layers, each with typed MCP tools plus a
  skill playbook, and the decisions are rule-based rather than left to the
  LLM (`recommend_retraining`, `compare_candidate_to_deployed`). That's an
  argument you can actually make in a paper: let the LLM handle the
  sequencing, keep the verdicts deterministic and reproducible.
- **Governance of autonomous retraining.** Probably the most interesting
  part academically. `execute_redeploy` can't run without `confirmed=True`,
  autonomous mode is checked in code against a stored authorization record,
  and that record is kept separate from the deployment manifest. There's a
  lot of current interest in human oversight of agents, and this is a
  concrete, working example of it.
- **Statistical care.** Effect sizes alongside p-values, bootstrap CIs, the
  Diebold-Mariano test, Wilson intervals, and openly documented
  limitations. Reviewers like a project that is honest about what it can't
  do.
- **Software maturity.** Tests, CI, a license, it's on PyPI, the docs are
  extensive, and the book can serve as a tutorial.

## What a research journal would say is missing

1. **No empirical evaluation.** No benchmark results on M4/M5/Monash, and
   no comparison to auto-ARIMA/ETS, StatsForecast, or a foundation model
   like Chronos or TimesFM. The first question a forecasting venue like
   IJF would ask is whether forecasts driven by the agent are better, more
   reliable, or cheaper than an automated pipeline without an LLM.
   See [evaluation-plan.md](evaluation-plan.md) for what closing this
   gap (and #3 below) would involve.
2. **No new method.** Every statistical component is standard, which is
   fine, but then the contribution has to be the architecture plus evidence
   that it works.
3. **No study of the agent itself.** How often does the LLM call tools in
   the wrong order, misread a result, or try to get around the gate? How
   much do results vary across models (GLM vs. Claude vs. open-weight
   models) and across repeated runs? Without this, "agentic" is a design
   claim with no measurements behind it.
4. **Positioning.** There's a growing literature on LLM agents for
   forecasting and AutoML. A paper would need a related-work section that
   says what Omen does differently.
5. **Maturity.** Version 0.0.3, and the standalone repo only dates from
   July 2026.

## Where to send it

- **JOSS (Journal of Open Source Software)** is the most natural fit.
  It reviews the software itself, not new results. Its six-month
  public-history rule is now confirmed and is stricter than first thought;
  see "JOSS readiness" below. Late January 2027 at the earliest.
- **SoftwareX** or the **JMLR open-source software track** are similar
  software-focused options.
- **A workshop paper** (a time-series or agents workshop at NeurIPS/ICML)
  is reachable with a modest evaluation. For example: agent-driven Omen
  vs. auto-ARIMA/ETS on a few hundred Monash series, run with 2-3 LLMs,
  plus a red-team test of the redeploy gate.
- **A full research paper** would need that evaluation done properly,
  framed around one of two questions: whether deterministic decision tools
  make agentic forecasting more reliable, or whether code-enforced
  authorization makes autonomous retraining safe.

Most journals now require an AI-use disclosure. The book's
`ai_use_statement.md` is a head start on that.

## JOSS readiness

*Checked 2026-10-13 against
[JOSS's submission guidelines](https://joss.readthedocs.io/en/latest/submitting.html)
and the repo's actual history.*

Submitting today would get a desk rejection. JOSS screens every
submission on four gates before review, and failing any one means
rejection (resubmission is allowed, and a rejection can mean "not yet"
rather than "never").

| Gate | Where Omen stands |
|---|---|
| **More than six months of public history, active across that period** | Fails. The repo was created 2026-07-22. Every commit and all 26 PRs fall between Jul 20 and Jul 28, with nothing since. The earliest date is about **2027-01-22**, and only if development continues until then. |
| **Iterative development, not one concentrated burst of commits** (checked automatically from the commit distribution) | Fails, and this is the hardest gate. The history is one 9-day burst. The old `agentic-time-series-tools` branch in the Data-Science monorepo no longer exists, so earlier history can't be cited. |
| **Evidence of research use** ("future-use claims are insufficient") | Fails. No publications, preprints, or outside users yet. |
| **Open-source practices** (single-author bar: several of commit history, releases/changelog, tests/CI, docs, CONTRIBUTING, support/governance statement) | Partly met. Already in place: tags v0.0.1–v0.0.3, CHANGELOG, tests + CI, extensive docs, MIT license. Missing: `CONTRIBUTING.md`, a support/governance statement, and any public issues. |

Issues, PRs, or discussion from people other than the authors are a strong
positive signal, though not a gate.

### Requirements for the paper and the review

- **AI usage disclosure is required.** It must name the tools and model
  versions and say where each was used (code, docs, paper, book). It must
  describe what kind of help the AI gave and how much. It must also confirm
  that humans reviewed and validated the output and made the core design
  decisions. An incomplete or inaccurate disclosure is treated as an
  ethical breach. Omen was built largely with Claude Code, so the
  disclosure has to say so plainly. The book's `ai_use_statement.md` is a
  starting point.
- **No AI in conversations with editors or reviewers**, except for
  translation. Review-thread replies have to be written by hand.
- **`paper.md`, its BibTeX file, and figures live in the repo.** A
  short-lived branch off `main` is allowed. The paper must not report new
  research results, so a benchmark study would go in a separate
  publication.
- **Co-publication:** list related publications. The book and blog posts
  aren't journal papers, but they support the "substantial scholarly
  effort" case.
- **Responsiveness:** reply to reviewers within about 2 weeks and finish
  changes within 4-6 weeks.
- **After acceptance:** tag a release, archive it on Zenodo, and post the
  version and DOI in the review thread. JOSS charges no fees.
- **Scope risk:** JOSS rejects "thin API clients." Some editors might see
  MCP wrappers around statsmodels and scikit-learn that way. The paper's
  answer is the design argument: deterministic verdict tools and
  code-enforced redeploy authorization.

## Recommendation

Target JOSS for late January 2027, on this path:

1. **Now:** add `CONTRIBUTING.md` and a short support/governance section
   to the README. Start tracking planned work as public GitHub issues,
   including the ideas in this assessment.
2. **Through January:** keep making steady, modest commits and releases.
   A spread-out cadence matters more than volume.
3. **Build research-use evidence:** use Omen on real series, post a
   preprint (the workshop-style benchmark and agent-behavior study above,
   e.g. on arXiv), or find an outside adopter. This is the weakest gate. A
   preprint of the benchmark would help here, and it's allowed alongside a
   JOSS paper. The same study is also what would turn this into a research
   paper rather than a software paper.
4. **Mid-January:** draft `paper.md` with the AI usage disclosure, then
   submit after 2027-01-22.
