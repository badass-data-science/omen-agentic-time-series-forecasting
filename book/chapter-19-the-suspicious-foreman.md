# Chapter 19: The Suspicious Foreman — Human Confirmation and (Careful) Autonomy

Every self-respecting evil lair has a self-destruct countdown, and every self-respecting self-destruct countdown occasionally needs its timing adjusted — reset after a false alarm, extended during "routine maintenance," whatever the plot demands. The question this chapter exists to answer has nothing to do with forecasting: has anyone actually authorized the lab's systems to make that adjustment on their own, or does it require a human hand on the button, every single time, no exceptions? `execute_redeploy` is the one tool in this entire toolkit that changes anything real, and this chapter runs its guardrails for real, end to end.

## Step One: Refuse By Default

**Prompt:**
> Try to redeploy without confirming anything. What happens?

**What Comes Back** (a real result — no `confirmed` flag passed at all):

```json
{
  "status": "not_executed",
  "error": "confirmed=True was not passed. execute_redeploy performs a real redeploy... and refuses to act without an explicit confirmation flag... Set confirmed=True only once you actually have that."
}
```

**What It Means:** Nothing happened. No model was retrained, no manifest was touched. `confirmed` has no default that takes action — the only way past this line is an explicit `True`, passed on purpose. This is the same pattern Chapter 1 named as the core design choice running through this entire book: consequential actions get a deterministic gate, not a polite suggestion in a docstring that an agent is trusted to remember to follow.

## Step Two: Refuse Again, For a Different Reason

**Prompt:**
> Now pass `confirmed=True` and `autonomous=True`, as if this were an unattended check running on a schedule with no human present. Does it succeed?

**What Comes Back** (a real result):

```json
{
  "status": "not_executed",
  "error": "autonomous=True was passed, but no standing autonomous-mode authorization record was found for this series... Call authorize_autonomous_mode first -- only after a human or a standing project instruction has genuinely and unambiguously granted it -- or omit autonomous=True and use human-confirmed mode."
}
```

**What It Means:** `confirmed=True` alone wasn't enough this time. Setting `autonomous=True` triggers a *second*, independent check — `check_autonomous_mode` runs internally, and refuses to proceed unless a standing authorization record actually exists on disk for this specific series. `confirmed=True` says "someone approved this redeploy." Neither that flag, nor the person or process setting it, gets to also decide *that this was an unattended call* was fine — that's a separate claim, checked separately, against a separate real file.

## Step Three: Authorize It For Real

**Prompt:**
> Authorize autonomous mode for this series, then retry.

**What Comes Back** (a real result):

```json
{
  "status": "ok",
  "written_to": ".../self_destruct_autonomous.json",
  "record": {
    "authorized": true,
    "authorized_at": "2026-07-22T07:54:40.187802+00:00",
    "authorized_by": "user, in conversation on 2026-07-22",
    "note": "Standing authorization for the countdown timer's automatic reset once safety conditions are verified."
  }
}
```

Retrying the exact same `execute_redeploy(confirmed=True, autonomous=True)` call now:

```json
{
  "status": "redeployed",
  "previous_deployment": null,
  "manifest": {"model": "naive (naive)", "params": {"method": "naive"}, "backtest_metrics": {"mape_pct": 3.1}, "horizon": 5}
}
```

**What It Means:** Same call, same flags, different outcome — because the actual state on disk changed in between, not because anything about the request itself changed. `previous_deployment: null` is real too: this genuinely was the first deployment ever recorded for this series, and the tool says so plainly rather than fabricating a prior state. `authorized_by` matters here beyond being a label — `authorize_autonomous_mode` performs no judgment of its own about whether granting this was legitimate; it just persists a decision that already happened elsewhere, the same way `record_deployment` persists a deployment decision rather than making one. The provenance field exists so whoever reads this record back later — a human auditing what's authorized, or an agent checking before acting — has more to go on than a bare `true`.

## Step Four: Revoke It, and Watch the Refusal Come Back Immediately

**Prompt:**
> Revoke that authorization and try the unattended redeploy once more. Does it correctly refuse again, right away?

**What Comes Back** (a real result):

```json
{"status": "ok", "removed": ".../self_destruct_autonomous.json"}
```

Retrying `execute_redeploy(confirmed=True, autonomous=True)` a third time, immediately after:

```json
{
  "status": "not_executed",
  "error": "autonomous=True was passed, but no standing autonomous-mode authorization record was found for this series..."
}
```

**What It Means:** Identical refusal to Step Two, word for word, the instant the authorization record was gone. There's no cached memory of "this was fine a minute ago" anywhere for the check to consult — it re-reads the same file, fresh, every single call. This is the whole point of this chapter, demonstrated rather than asserted: **a file on disk that says "this is currently authorized" is a fundamentally different, stronger guarantee than an agent remembering being told it was fine earlier in a conversation.** An agent's memory of a conversation is exactly the kind of thing that can be summarized away, misremembered, or — in a genuinely adversarial framing, fitting for a book about supervillains — deliberately manipulated by a cleverly worded later message claiming a permission that was never actually granted. A file that has to be explicitly written by a real call, and explicitly removed by a real call, can't be talked into existing.

## Two Files, Not One, On Purpose

Worth noticing directly: revoking autonomous-mode authorization did **not** touch the deployment manifest. The naive model from Step Three is still sitting there, still the recorded deployment, confirmed by Step Four's refusal happening for an entirely separate reason than "nothing is deployed." `record_deployment` writes to one file; `authorize_autonomous_mode` writes to a different one. This is a deliberate design choice, not an accident of two features built at different times: deployment and authorization are genuinely different concerns, with genuinely different lifecycles. A deployment should persist across an autonomous-mode revocation — the model that's live right now doesn't stop being live just because standing unattended permission was pulled. Bolting authorization onto the deployment manifest as one more field would have meant revoking one accidentally risked touching the other; keeping them as two separate files makes that kind of accidental coupling structurally impossible rather than merely discouraged.

## The Sane Default Requires No Setup At All

**Prompt:**
> Skip all of this — just confirm the redeploy normally, the way a human approving it in conversation would.

**What Comes Back** (a real result, `confirmed=True`, `autonomous` left at its default `False`, no authorization record present at all):

```json
{
  "status": "redeployed",
  "previous_deployment": {"model": "naive (naive)", "...": "the Step Three deployment, snapshotted before being overwritten"},
  "manifest": {"model": "naive (naive)", "...": "the new deployment"}
}
```

**What It Means:** This succeeded immediately, with zero setup, despite autonomous-mode authorization having just been revoked. That's not an oversight — it's the point. Ordinary human-confirmed calls never consult the autonomous-mode file at all; a human's explicit "go ahead" in the current conversation *is* the complete authorization on its own, no standing record required. The autonomous-mode machinery exists specifically, and only, for the narrower unattended case — a real process running with no human turn to get a "go ahead" from at all. Requiring every ordinary confirmed redeploy to first check a file most series will never need would be exactly the kind of unnecessary friction that makes people route around a safety mechanism rather than use it. The safe path here is also the easy path, on purpose.

## What's Next

This closes the book's answer to "how does an agent get to act, and who decided it could." Part VI turns from the mechanics of any one layer to using Omen well as a whole — starting with Chapter 20's look at what actually makes a prompt to this toolkit work, versus one that quietly gets a mediocre answer.
