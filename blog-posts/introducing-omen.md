# Introducing Omen (or, How Our Heroine Built a Forecasting Assembly Line With a Very Suspicious Foreman at the End of It)

*Five layers, one Secret Lab™, and a robot that refuses to redeploy anything without being asked twice.*

Our heroine the data scientist has, over the course of her various schemes, accumulated an inconvenient number of things that need forecasting. Mojito inventory for the Secret Lab™. Strut material budgets for [her forthcoming geodesic hideout](https://badassdatascience.substack.com/p/introducing-pydome-or-how-our-heroine). The VIX, for [the Risk Desk](https://badassdatascience.substack.com/p/ai-method-mashup-expert-systems-crash), which currently only tells her how nervous the market is *right now*, not next week, which is a real gap when your entire operating model depends on staying two steps ahead of the Powers That Be™.

Every one of these problems could, in principle, be solved by writing a fresh forecasting script each time: load some data, eyeball a chart, fit whatever model comes to mind first, ship it, forget about it until it's embarrassingly wrong. Our heroine has done this. It works right up until it doesn't, and by then the mojitos have run out.

So instead, she built **Omen**: a general-purpose, reusable, five-layer pipeline for exploring a time series, fitting and honestly comparing candidate forecasting models, deploying the winner, watching it in production, and — this is the new part — deciding, on paper, whether it's worth retraining and redeploying when reality drifts. An AI agent drives all five layers. A very small number of the more consequential decisions are, deliberately, *not* left to that agent's judgment at all.

## Why Bother?

Off-the-shelf AutoML forecasting tools already exist. They will happily fit forty models, pick the one with the lowest error, and hand it back to you with zero explanation. Our heroine finds this deeply unsatisfying, for the same reason she finds it deeply unsatisfying when the Risk Desk's LLM agent tries to freelance a risk decision: a number without reasoning behind it is not something you can defend later, and "the error was lowest" is not reasoning, it's a coin flip with extra steps.

What she actually wants is an agent that explores a series the way a competent analyst would — checking stationarity, sniffing out seasonality, flagging anomalies — and *then* fits candidates and argues about which one deserves to go into production, citing actual numbers instead of vibes. That's a job for agentic AI, and Omen hands an LLM exactly the typed tools it needs to do it properly, via [FastMCP](https://gofastmcp.com) servers and matching [OpenClaw](https://openclaw.dev) skills (playbooks in Markdown telling the agent how to sequence the tools and what to actually report).

But — and this will sound familiar if you read the Risk Desk post — there is a short list of decisions in this pipeline that our heroine does not want re-litigated by an LLM every single time, phrased three subtly different ways depending on its mood: *should this model replace the one currently deployed?* and, even more pointedly, *should anything actually get redeployed right now?* Those get answered by small, boring, deterministic functions instead. More on that below.

## The Five Layers

Omen is organized as five sequential layers, each its own FastMCP server plus companion skill, installable together or separately depending on how much of the pipeline a given project actually needs.

**Layer 1 — `ts-analyst`: look before leaping.** This layer explores a series and recommends an approach, and it deliberately fits nothing. Its tools run an Augmented Dickey-Fuller stationarity test, a seasonal decomposition, ACF/PACF autocorrelation checks, and a rolling z-score anomaly detector, then hand the agent enough evidence to write up findings, a recommended forecasting approach, an alternative it ruled out, and caveats — not a verdict pulled out of thin air.

**Layer 2 — `ts-forecaster`: fit candidates and argue about it.** Naive and seasonal-naive baselines (which every fancier model must actually beat, not just gesture at beating), ETS/Holt-Winters, SARIMA, and gradient-boosted trees on lag and calendar features, all backtested against the *same* held-out window so the comparison is fair. The gradient-boosted-trees backtest is evaluated one-step-ahead using true lagged values — an easier evaluation setting than ETS/SARIMA's genuine multi-step forecast — and the tool result says so explicitly, so the agent can't quietly declare it the winner on a technicality.

**Layer 3 — `ts-deploy`: retrain for real, forecast forward.** Once a model's been chosen, this layer retrains it on the *entire* series (no more holding out data — Layer 2 already did that job) and produces an actual forecast past the end of the data, with prediction intervals where the model supports them. The gradient-boosted-trees forecast here is *recursive* — each prediction feeds back in as a lag for the next step — which is a materially riskier setup than Layer 2's evaluation of the same model type, and again, the tool doesn't let that fact go unmentioned.

**Layer 4 — `ts-monitor`: come back later and check your work.** Once real observations exist for at least part of the forecast horizon, this layer compares the deployed forecast against what actually happened, checks for data drift with a t-test and a KS test, and combines both signals into a recommendation: `retrain_now`, `investigate`, `monitor_closely`, or `no_action_needed`. Amusingly, the drift detector cannot tell the difference between a genuine regime change and a series that just... has a trend, which our heroine confirmed directly by running it against her own synthetic demand data and watching it cry "drift!" at nothing more sinister than the number going up over time. The tool says so in its own output rather than let that surprise anyone later.

**Layer 5 — `ts-retrain`: the suspicious foreman.** This is the newest layer, and the one our heroine is proudest of, mostly because of everything it refuses to do. When Layer 4 says `retrain_now`, `ts-retrain` re-runs Layers 1 and 2 on the updated series — same agentic judgment as before, nothing is rubber-stamped — and then hands the resulting candidate to a small deterministic function, `compare_candidate_to_deployed`, which checks whether the new model beats whatever's currently live by more than a configurable threshold (10% by default) before it will even entertain the idea of a swap. Marginal improvements get rejected on principle, because redeploying and resetting the monitoring clock over noise is how you end up chasing your own tail.

And then — the actual point of this layer — there is exactly one tool that can change what's deployed: `execute_redeploy`. It refuses to run unless called with `confirmed=True`. There is no default that takes action. Confirmation arrives one of two ways: a human explicitly saying "go ahead," in the moment, which is the default; or an *optional* autonomous mode, opted into per series, per explicit instruction, that lets the skill call `execute_redeploy(confirmed=True, autonomous=True)` itself the instant the numbers clear the bar — and even then, it's required to say out loud that it just did that, rather than let an unattended action pass without being visibly reported. Our heroine considered letting the agent redeploy freely whenever it felt confident. She then remembered how the Risk Desk post ends, and did not do that. (An earlier draft of this layer left "is autonomous mode actually authorized for this series" as something the agent had to remember correctly. It no longer does — see the deep-dive links below.)

## How It Actually Works, Mechanically

Underneath the fanfare, this is a normal installable Python package (`pip install -e ".[all]"`, or per-layer extras if you don't want, say, `scikit-learn` dragged in just to run Layer 1). Each layer follows the same split: plain functions that take a DataFrame and return a small JSON-safe dict — so the tool logic is unit-testable without spinning up MCP at all — and a thin `server.py` that wraps those functions as `@mcp.tool()` and handles CSV loading. One shared `data_prep.py` generates synthetic demand data (trend, weekly and yearly seasonality, a few injected anomalies) or loads your own CSV, so nobody had to write the same loader four times.

The durable state in the entire toolkit lives in two small JSON files, both written next to the series CSV, both deliberately kept separate from each other: a deployment manifest (model type, params, backtest metrics, timestamp) written whenever something actually gets deployed, and — added since this post first went up — a standing autonomous-mode authorization record, written only when a human or a standing project instruction explicitly grants unattended retraining for a specific series. Every other tool in every other layer is a pure function of its explicit inputs. This was a deliberate choice: the fewer places state can quietly live, the fewer places it can quietly go stale.

It's worth noting the whole thing was originally developed and hardened against **GLM-5.2 running on Ollama Cloud**, not against Claude at all — nothing about the design is model-specific, which our heroine confirmed the honest way, by later bringing in an entirely different AI (Claude Code, yes, hello) to design and build Layer 5 on top of the existing four without anything falling over. She collects AI assistants the way some people collect passport stamps.

## The Deep Dives

This post was written to introduce the pipeline at cruising altitude. Every layer has since gotten its own dedicated post walking through what changed when our heroine went back and made each one defend its numbers properly — effect sizes, confidence intervals, a couple of real bugs caught in the process, and (for Layer 5 specifically) the thing this post's own Next Steps used to list as unfinished:

- [`ts-analyst` Gets a Statistics Degree](ts-analyst-gets-a-statistics-degree.md)
- [`ts-forecaster` Shows Its Work](ts-forecaster-shows-its-work.md)
- [`ts-deploy` Ships It](ts-deploy-ships-it.md)
- [`ts-monitor` Learns Not to Trust a Clean Bill of Health](ts-monitor-learns-to-doubt-good-news.md)
- [`ts-retrain` Checks Its Papers](ts-retrain-checks-its-papers.md)

## Next Steps

- ~~Make autonomous-mode authorization inspectable, not just conversational.~~ **Done.** Whether autonomous mode applies to a given series no longer lives solely in the agent's memory of a conversation — a standing, per-series authorization record now exists, and `execute_redeploy` checks it in code before acting unattended, not just in prose. See the `ts-retrain` deep dive above for the details.
- **Add a real CI pipeline and some linting.** The test suite is solid (137 tests now, up from 35 at this post's original writing, `pytest.importorskip` guards so the core install doesn't drag in `statsmodels`/`scikit-learn` unnecessarily) but nothing runs it automatically yet, and there's no type-checking despite type hints sprinkled throughout.
- **Actually publish it.** The package layout is PyPI-ready as-is — `pyproject.toml`, console scripts, the works — but the metadata still says `"Your Name" <you@example.com>`. Somebody has to confirm `omen` is actually free on PyPI before claiming it — it's a short, generic word, so don't assume it isn't already taken.
- **No expiry on autonomous-mode grants.** A standing authorization persists until someone explicitly revokes it — there's no time-boxing yet, so a "for the next month" grant isn't currently expressible, only "until revoked."

## Conclusion

Our heroine now has an agent that will explore a series, argue honestly about which model deserves to go live, ship a real forecast, watch that forecast for signs of trouble, and — when trouble shows up — go check whether a fresh model actually fixes it before touching production, and even then, only with someone's explicit say-so. That's five layers of judgment stacked on top of one very stubborn gatekeeper, which is, frankly, more oversight than most of her human collaborators get.

The mojito forecast, for the record, remains bullish.

## Code

Code is available at [badass-data-science/Data-Science](https://github.com/badass-data-science/Data-Science/tree/agentic-time-series-tools/Forecasting/omen), on the `agentic-time-series-tools` branch.

## AI Use Statement

This article's prose was drafted by Claude Code based on our heroine's explicit instructions and a review of five of her prior posts to match voice and structure; she will review and edit before publishing. Layers 1 through 4 of the toolkit predate this collaboration and were originally developed against GLM-5.2 on Ollama Cloud. Layer 5 (`ts-retrain`) — including the deterministic redeploy-comparison logic, the `confirmed=True` gate on `execute_redeploy`, the optional autonomous mode, and the accompanying documentation and tests — was designed and built collaboratively with Claude Code. This post has since been lightly revised (the autonomous-mode durable-state description, the Next Steps section, and the addition of the Deep Dives section above) to stay accurate as that collaboration continued across all five layers; the five linked posts each carry their own AI Use Statement covering that layer-specific work in full.
