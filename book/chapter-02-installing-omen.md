# Chapter 2: Installing Omen (OpenClaw, Claude Code, Hermes, and Friends)

Before Chapter 3 can put the mojito problem to rest, something more
tedious has to happen first: the actual wiring. This chapter has no
forecasting in it. It has no statistics in it. What it has is a working
connection between an AI agent and five small servers that know how to
talk to it correctly — and, because this is the kind of book that shows
its work, one real installation failure, narrated exactly as it happened,
because you are going to hit some version of it too, and it is much less
alarming once you've seen it coming.

## What You're Actually Installing

Omen is a normal, installable Python package. There is no special
runtime, no proprietary binary, nothing to license. Once installed, it
gives you five **console scripts** — small executable commands, one per
layer — that each start a **FastMCP server**: a lightweight process that
speaks the Model Context Protocol (MCP) over standard input and output
and, when asked, reports exactly which typed tools it exposes.

```bash
pip install -e ".[all]"
```

installs everything: all five layers and their dependencies
(`statsmodels`, `scikit-learn`, and friends). If you only want a subset —
say, you're only planning to explore data with Layer 1 and don't want
`scikit-learn` dragged in for no reason — per-layer extras exist too:
`.[analyst]`, `.[forecaster]`, `.[deploy]`, `.[monitor]`, `.[retrain]`.
This book assumes `.[all]` from here on, since later chapters use every
layer.

Once installed, confirm the five console scripts actually landed on your
`PATH`:

```bash
which ts-analyst-server ts-forecaster-server ts-deploy-server \
      ts-monitor-server ts-retrain-server
```

Each one should resolve to a path inside whatever virtual environment you
installed into. If any of them come back empty, the install didn't
finish cleanly — fix that before going any further, because every
installation problem downstream of this point in the chapter is really
just a variation on "the agent couldn't find the command."

## Understanding the Connection, Not Just Copy-Pasting It

Every agentic platform that can use Omen needs to do the same three
things, however differently they each phrase it in their own
configuration format:

1. **Know the command** that starts each server (`ts-analyst-server`,
   and so on for the other four).
2. **Launch it over stdio** — meaning the platform starts the server as a
   subprocess and talks to it through its standard input/output streams,
   not over a network port.
3. **Discover its tools** by asking the running server what it exposes,
   rather than the platform having them hardcoded anywhere.

Once you understand that this is *all* that's actually happening
underneath any given platform's configuration screen, installing Omen
anywhere stops being platform-specific trivia and becomes "fill in these
three things in whatever format this particular tool wants." The rest of
this chapter walks through that for a few real platforms, and then for
"whatever you're actually using instead," because this book would rather
teach you the pattern than assume you're on the one platform it
screenshots.

### OpenClaw (the primary target platform for this book)

Omen ships a ready-to-merge configuration snippet at the root of the
project, `openclaw.config.snippet.jsonc`. Merge its contents into
`~/.openclaw/openclaw.json`. In outline, it looks like this:

```jsonc
{
  "mcp": {
    "servers": {
      "ts-analyst":    { "command": "ts-analyst-server",    "args": [], "transport": "stdio" },
      "ts-forecaster": { "command": "ts-forecaster-server", "args": [], "transport": "stdio" },
      "ts-deploy":     { "command": "ts-deploy-server",     "args": [], "transport": "stdio" },
      "ts-monitor":    { "command": "ts-monitor-server",    "args": [], "transport": "stdio" },
      "ts-retrain":    { "command": "ts-retrain-server",    "args": [], "transport": "stdio" }
    }
  },
  "agents": {
    "defaults": { "model": { "primary": "ollama-cloud/glm-5.2:cloud" } }
  }
}
```

(That last block is a model default, not a requirement — Omen's design is
deliberately not tied to any one model provider, a claim this book will
back up properly in Chapter 21. Point it at whatever agent model you're
actually using.)

Beyond the MCP server registration, OpenClaw also needs Omen's **skills**
— the Markdown playbooks that tell the agent how to sequence each
layer's tools. Copy them into your OpenClaw workspace:

```bash
cp -r "$(python -c 'import omen as t; print(t.skills_dir())')"/* \
    ~/.openclaw/workspace/skills/
```

Then verify, in order:

```bash
openclaw mcp status --verbose
openclaw mcp doctor --probe
openclaw mcp tools ts-analyst
```

(and the same `mcp tools` check for the other four server names). Each
should report a live connection and a real tool list — not just "no
errors printed," but an actual, populated list of tool names. If you're
using GLM-5.2 on Ollama Cloud as the snippet above suggests, confirm the
exact hosted model ID first with `openclaw models list --provider
ollama-cloud` — these strings drift, and this book would rather tell you
to check than hand you one that's already stale by the time you're
reading this.

### Claude Code

Claude Code (the tool this book itself was drafted with, incidentally)
registers MCP servers through its own configuration — either a project-
level `.mcp.json` file using the same `command`/`args` shape shown above,
or via `claude mcp add` from the command line. Because CLI flags are the
part of any tool most likely to have changed by the time you're reading
this, run `claude mcp add --help` for the exact current syntax rather
than trusting a book to have it memorized correctly forever; the
important, stable fact is that you're giving it the same information as
everywhere else in this chapter — a name, a command, and (empty, here)
arguments.

Omen's `SKILL.md` files are written in a format OpenClaw consumes
natively as a full agentic playbook. Claude Code doesn't necessarily read
them the same way, but they remain genuinely useful reference material —
point your agent at a specific layer's `SKILL.md` when you want it to
follow that layer's documented workflow precisely (the four-step
structure most of Omen's skills use, covered as you reach each layer in
this book).

### Hermes, and Other MCP-Speaking Agent Frameworks

Rather than guess at a specific proprietary configuration format for a
platform this book can't screenshot with confidence, here's the honest
version: **if Hermes — or any other agentic framework you're using — can
launch a subprocess by command and arguments and speak MCP over stdio,
the same three things from earlier in this chapter apply unchanged.**
Register each of the five console scripts the same way you would for any
other client. Consult that platform's own documentation for exactly
where its configuration file lives and what key holds the server list;
the *shape* of what goes in it is what this chapter has already taught
you.

### Generic MCP Clients (Claude Desktop and Others)

Several general-purpose AI assistants beyond the ones named above also
speak MCP directly — Claude Desktop is a common one, configured via a
`claude_desktop_config.json` file (location varies by OS) with an
`mcpServers` key holding the same `command`/`args` shape one more time.
If a pattern is starting to feel repetitive by this point in the
chapter, that's the point: this is a *standard*, and once you've set
Omen up on one MCP client, setting it up on the next one is mostly
finding where that client keeps its config file.

## The Gotcha, Demonstrated Live

Here is a failure this book's own author hit while first wiring up a
real test against a live Omen server — worth narrating exactly as it
happened, because it's the single most common installation problem, and
it looks alarming right up until you know what it is.

The setup: a virtual environment, Omen installed into it with
`pip install -e ".[all]"`, the console script confirmed present with
`which ts-analyst-server`. Then, a client configuration pointing at the
server by its bare command name:

```json
{ "mcpServers": { "ts-analyst": { "command": "ts-analyst-server", "args": [] } } }
```

Connecting produced this:

```
RuntimeError: Client failed to connect: [Errno 2] No such file or
directory: 'ts-analyst-server'
```

Which is deeply confusing the first time you see it, because
`ts-analyst-server` unquestionably *does* exist — `which ts-analyst-server`
just said so, in the same terminal, thirty seconds earlier.

Here's what's actually going on: when your agentic platform launches
Omen's server, it's starting a **new subprocess**, and that subprocess
does not automatically inherit the activated virtual environment's
`PATH` the way your interactive terminal session does. The bare command
name `ts-analyst-server` only resolves if the launching process's `PATH`
includes your venv's `bin/` directory — and depending on exactly how
your agentic platform spawns subprocesses, it may or may not.

The fix is one line: use the **absolute path** to the installed console
script instead of its bare name.

```json
{ "mcpServers": { "ts-analyst": {
    "command": "/path/to/your/venv/bin/ts-analyst-server",
    "args": []
} } }
```

Find that exact path with `which ts-analyst-server` while your venv is
activated, and paste the result in verbatim. This one change resolves
the overwhelming majority of "the tool obviously exists but the client
can't find it" reports you'll run into across every platform in this
chapter — OpenClaw's own configuration notes flag this exact fix for
exactly this reason.

## Proof of Life

Installation isn't actually finished until you've watched a real tool
call succeed — "the install command didn't error" is not the same claim
as "the connection works," and this book isn't going to let the
distinction slide even in the setup chapter. Here's the smoke test,
using a series too small to mean anything statistically on purpose: five
days of the Secret Lab™'s internally tracked "Weekly Grumbling Level"
among the henchman corps, a metric our heroine takes more seriously than
you'd think.

**Prompt:**
> Confirm the `ts-analyst` MCP server is running and list every tool it
> exposes. Then run `basic_stats` on this five-day grumbling-level series
> just to prove the connection works end to end.

**What Comes Back** (a real result, from a real running server):

```
Tools exposed: generate_synthetic_data, basic_stats, check_stationarity,
seasonal_decomposition_summary, detect_seasonality_period,
acf_pacf_summary, detect_anomalies_zscore, detect_anomalies_robust_zscore,
detect_changepoints

basic_stats result:
{
  "n_observations": 5,
  "mean": 4.4,
  "mean_ci_lower": 2.984,
  "mean_ci_upper": 5.816,
  "confidence_level": 0.95,
  "std": 1.14,
  "min": 3.0,
  "max": 6.0
}
```

**What It Means:** The connection works — nine real tools came back from
a real subprocess, and a real number came back for the mean. But look at
that confidence interval: `[2.98, 5.82]`, on a mean of `4.4`. That's not
a narrow, reassuring band. It's most of the entire observed range,
because five data points is nowhere near enough to pin down a population
mean with any real precision, and `basic_stats` is not going to pretend
otherwise just because you asked it nicely. This is the same "never
report a number without also reporting how sure you are" rule from
Chapter 1, showing up for the first time with a real result attached —
and it's the *last* time in this book you'll see a series this small
treated as anything other than a wiring test.

## What's Next

The plumbing works. Chapter 3 puts it to actual use: real data, a real
series with real months of history, and the first genuine statistical
question this book asks — not "does the connection work," but "what does
this data actually look like, and how sure are we?"
