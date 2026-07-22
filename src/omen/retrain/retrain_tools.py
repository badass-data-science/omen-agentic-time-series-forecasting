"""
retrain_tools.py

Layer 5: closes the loop after ts-monitor recommends retrain_now. Most of
this module doesn't refit anything -- Layers 1-3 (ts-analyst,
ts-forecaster, ts-deploy) already do that, driven by the agent as usual.
What's missing without this layer is:

1. Any durable record of what's currently deployed (model, params,
   backtest metrics) to compare a freshly retrained candidate against.
2. A reproducible answer to "is the new candidate actually better enough
   to be worth redeploying," rather than an LLM eyeballing two metric
   dicts and guessing.
3. A single, explicitly-gated action that actually performs a redeploy,
   for the cases where a human (or an explicitly authorized autonomous
   workflow) decides to act on that answer -- see execute_redeploy below.
4. A durable, inspectable record of WHICH series autonomous mode is
   actually authorized for -- see authorize_autonomous_mode below. Before
   this, that fact lived only in the agent's own memory of a conversation.

record_deployment/load_deployment_manifest/compare_candidate_to_deployed/
authorize_autonomous_mode/revoke_autonomous_mode/check_autonomous_mode are
pure diagnostics/record-keeping with no side effects beyond their own
small JSON file. execute_redeploy is the one function in this whole
toolkit that takes a real production action (retrains a model and
overwrites the deployment manifest) -- it refuses to run unless called
with confirmed=True, which is never its default, and if called with
autonomous=True it ALSO refuses unless check_autonomous_mode finds a
standing authorization record for this series. See
skills/ts-retrain/SKILL.md for the two ways that confirmation is meant to
be reached: a human approving in-conversation, or an explicitly
authorized autonomous mode.
"""

import json
import os
from datetime import datetime, timezone
from typing import Callable, Optional

DEFAULT_MANIFEST_FILENAME = "deployment_manifest.json"
DEFAULT_AUTONOMOUS_MODE_FILENAME = "autonomous_mode.json"

_MODEL_TYPES = ("naive", "ets", "sarima", "gbt")


def _manifest_path_for(csv_path: str, manifest_path: Optional[str] = None) -> str:
    """Default manifest location: alongside the series CSV, unless an
    explicit path is given."""
    if manifest_path:
        return manifest_path
    directory = os.path.dirname(os.path.abspath(csv_path))
    return os.path.join(directory, DEFAULT_MANIFEST_FILENAME)


def _autonomous_mode_path_for(csv_path: str, autonomous_mode_path: Optional[str] = None) -> str:
    """Default autonomous-mode-record location: alongside the series CSV,
    unless an explicit path is given. Deliberately a SEPARATE file from
    the deployment manifest, not a field within it -- authorization and
    deployment are different concerns with different lifecycles (an
    authorization can outlive many deployments, or be revoked without
    touching what's currently deployed)."""
    if autonomous_mode_path:
        return autonomous_mode_path
    directory = os.path.dirname(os.path.abspath(csv_path))
    return os.path.join(directory, DEFAULT_AUTONOMOUS_MODE_FILENAME)


def authorize_autonomous_mode(
    csv_path: str,
    authorized_by: str,
    note: Optional[str] = None,
    autonomous_mode_path: Optional[str] = None,
) -> dict:
    """Record that autonomous (unattended) retraining is authorized for
    this specific series. Call this ONLY after a human has explicitly
    granted this in the current conversation, or a standing project-level
    instruction (e.g. in AGENTS.md) unambiguously covers this series --
    this function performs no judgment of its own about whether that
    authorization is legitimate, it only persists a decision that's
    already been made elsewhere, the same way record_deployment persists
    a deployment decision rather than making one.

    `authorized_by` should identify who/what granted this (e.g. "user, in
    conversation on 2026-07-21" or "AGENTS.md standing instruction") so
    the record is self-explanatory to whoever reads it back later, not
    just a bare boolean with no provenance.

    Overwrites any existing record for this series -- like the deployment
    manifest, this reflects the CURRENT authorization state, not a
    history of grants and revocations.
    """
    path = _autonomous_mode_path_for(csv_path, autonomous_mode_path)
    record = {
        "csv_path": os.path.abspath(csv_path),
        "authorized": True,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "authorized_by": authorized_by,
        "note": note,
    }
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return {"status": "ok", "written_to": path, "record": record}


def revoke_autonomous_mode(csv_path: str, autonomous_mode_path: Optional[str] = None) -> dict:
    """Remove any autonomous-mode authorization record for this series.
    After this, execute_redeploy(..., autonomous=True) calls for this
    series will refuse until authorize_autonomous_mode is called again.
    Safe to call even if no record currently exists -- returns "ok"
    either way, not an error, since the end state (not authorized) is the
    same regardless of whether there was anything to remove.
    """
    path = _autonomous_mode_path_for(csv_path, autonomous_mode_path)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "ok", "removed": path}
    return {"status": "ok", "removed": None, "note": "No authorization record existed for this series."}


def check_autonomous_mode(csv_path: str, autonomous_mode_path: Optional[str] = None) -> dict:
    """Read whatever authorize_autonomous_mode last recorded for this
    series. Returns {"authorized": False, ...} -- NOT an error -- when
    nothing has been recorded, since "not authorized" is the default,
    expected state for most series, not a bug to raise on.
    """
    path = _autonomous_mode_path_for(csv_path, autonomous_mode_path)
    if not os.path.exists(path):
        return {
            "authorized": False,
            "checked_path": path,
            "note": "No authorization record found for this series.",
        }
    with open(path) as f:
        record = json.load(f)
    return record


def record_deployment(
    csv_path: str,
    model: str,
    params: dict,
    backtest_metrics: dict,
    horizon: int,
    manifest_path: Optional[str] = None,
) -> dict:
    """Persist a record of what's currently deployed: model type, params,
    the backtest metrics (from ts-forecaster) that justified deploying it,
    and the forecast horizon. Call this right after an actual, confirmed
    ts-deploy call -- not after every exploratory forecast_* call.

    Overwrites any existing manifest at the same path; the manifest always
    reflects the single currently-deployed model, not a history.
    """
    path = _manifest_path_for(csv_path, manifest_path)
    manifest = {
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "params": params,
        "backtest_metrics": backtest_metrics,
        "csv_path": os.path.abspath(csv_path),
        "horizon": horizon,
    }
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    return {"status": "ok", "written_to": path, "manifest": manifest}


def load_deployment_manifest(csv_path: str, manifest_path: Optional[str] = None) -> dict:
    """Read back whatever record_deployment last wrote for this series.
    Returns an explicit error dict (not an exception) if nothing has been
    recorded yet, since "nothing deployed" is an expected, valid state
    early in a series' lifecycle, not a bug to raise on.
    """
    path = _manifest_path_for(csv_path, manifest_path)
    if not os.path.exists(path):
        return {
            "error": (
                f"No deployment manifest found at {path}. Nothing has been "
                "recorded as deployed yet for this series -- call "
                "record_deployment after the first real ts-deploy call."
            )
        }
    with open(path) as f:
        manifest = json.load(f)
    return manifest


def compare_candidate_to_deployed(
    candidate_metrics: dict,
    deployed_metrics: dict,
    metric_name: str = "mape_pct",
    improvement_threshold_pct: float = 10.0,
) -> dict:
    """Deterministic decision: does a freshly backtested candidate model
    beat the currently deployed one by enough to be worth redeploying?
    Intentionally rule-based rather than a judgment call -- same reason
    monitor_tools.recommend_retraining is deterministic: "should we
    redeploy" needs to be reproducible given the same inputs.

    Compares `metric_name` (lower-is-better, e.g. mape_pct/mae/rmse) from
    each metrics dict. Requires a relative improvement of at least
    `improvement_threshold_pct` before recommending a swap, to guard
    against redeploying (and resetting the monitoring clock) over
    noise-level differences between two similar fits.

    If `candidate_metrics` also has a bootstrap confidence interval for
    `metric_name` (i.e. `{metric_name}_ci_lower`/`{metric_name}_ci_upper`
    -- the fields ts-forecaster's compute_metrics_with_ci adds, present on
    any recent fit_* result), this also reports the implied
    `pct_improvement_ci_lower`/`pct_improvement_ci_upper` and flags
    `redeploy_threshold_within_ci: true` when `improvement_threshold_pct`
    falls inside that range -- meaning should_redeploy is sensitive to
    backtest sampling noise, not a clean call. If `deployed_metrics` ALSO
    has a CI for `metric_name` (e.g. the deployed model's manifest was
    recorded from a CI-aware fit_* result), its uncertainty is combined in
    too via interval arithmetic over both ranges at once -- NOT a naive
    "one side fixed" simplification. `deployed_metrics_ci_used` reports
    whether that combination actually happened (true) or the range only
    reflects the candidate's own uncertainty with `deployed_value` treated
    as fixed (false, e.g. an older manifest with no CI recorded).

    pct_improvement = 100*(deployed_value - candidate_value)/deployed_value
    is DECREASING in candidate_value and INCREASING in deployed_value (for
    positive values) -- so the WORST-case improvement uses the candidate's
    highest plausible value paired with the deployed model's LOWEST, and
    the BEST-case uses the candidate's lowest paired with the deployed
    model's HIGHEST. Not a naive lower-bound-in/lower-bound-out mapping on
    either side.

    Args:
        candidate_metrics: backtest_metrics dict from a fresh
            ts-forecaster fit_* call on the updated series.
        deployed_metrics: backtest_metrics dict from the deployment
            manifest (load_deployment_manifest's "backtest_metrics" field).
        metric_name: Which key to compare; must be present and
            lower-is-better in both dicts.
        improvement_threshold_pct: Minimum relative improvement (%) the
            candidate needs over the deployed model before this
            recommends redeploying.
    """
    if metric_name not in candidate_metrics or candidate_metrics[metric_name] is None:
        return {"error": f"candidate_metrics has no usable '{metric_name}' value."}
    if metric_name not in deployed_metrics or deployed_metrics[metric_name] is None:
        return {"error": f"deployed_metrics has no usable '{metric_name}' value."}

    candidate_value = float(candidate_metrics[metric_name])
    deployed_value = float(deployed_metrics[metric_name])

    pct_improvement_ci_lower = pct_improvement_ci_upper = None
    redeploy_threshold_within_ci = None
    deployed_metrics_ci_used = False

    if deployed_value == 0:
        pct_improvement = None
        should_redeploy = candidate_value < deployed_value
    else:
        pct_improvement = round(100 * (deployed_value - candidate_value) / deployed_value, 2)
        should_redeploy = pct_improvement >= improvement_threshold_pct

        candidate_ci_lower = candidate_metrics.get(f"{metric_name}_ci_lower")
        candidate_ci_upper = candidate_metrics.get(f"{metric_name}_ci_upper")
        if candidate_ci_lower is not None and candidate_ci_upper is not None:
            deployed_ci_lower = deployed_metrics.get(f"{metric_name}_ci_lower")
            deployed_ci_upper = deployed_metrics.get(f"{metric_name}_ci_upper")
            if deployed_ci_lower is None or deployed_ci_upper is None:
                # No usable CI on the deployed side -- fall back to treating
                # deployed_value as fixed (both "bounds" collapse to the
                # point value), which reduces exactly to the candidate-only
                # combination.
                deployed_ci_lower = deployed_ci_upper = deployed_value
            else:
                deployed_metrics_ci_used = True
            deployed_ci_lower = float(deployed_ci_lower)
            deployed_ci_upper = float(deployed_ci_upper)

            # pct_improvement(C, D) = 100*(D-C)/D is monotonic in each
            # variable independently (decreasing in C, increasing in D for
            # D > 0), so its extrema over the box
            # [candidate_ci_lower, candidate_ci_upper] x [deployed_ci_lower, deployed_ci_upper]
            # occur at opposite corners -- proper interval arithmetic, not
            # a guess. Guard each bound's own denominator separately in
            # case one side of the deployed CI happens to be exactly 0.
            if deployed_ci_lower != 0:
                pct_improvement_ci_lower = round(
                    100 * (deployed_ci_lower - float(candidate_ci_upper)) / deployed_ci_lower, 2
                )
            if deployed_ci_upper != 0:
                pct_improvement_ci_upper = round(
                    100 * (deployed_ci_upper - float(candidate_ci_lower)) / deployed_ci_upper, 2
                )
            if pct_improvement_ci_lower is not None and pct_improvement_ci_upper is not None:
                redeploy_threshold_within_ci = bool(
                    pct_improvement_ci_lower <= improvement_threshold_pct <= pct_improvement_ci_upper
                )

    if should_redeploy:
        reasoning = (
            f"Candidate's {metric_name} ({candidate_value}) beats the deployed model's "
            f"({deployed_value}) by {pct_improvement}%, at or above the "
            f"{improvement_threshold_pct}% threshold -- worth redeploying."
        )
    elif pct_improvement is not None and pct_improvement > 0:
        reasoning = (
            f"Candidate's {metric_name} ({candidate_value}) is marginally better than "
            f"deployed ({deployed_value}, {pct_improvement}% improvement) but below the "
            f"{improvement_threshold_pct}% threshold -- not enough to justify redeploying "
            "and resetting the monitoring baseline."
        )
    else:
        reasoning = (
            f"Candidate's {metric_name} ({candidate_value}) is not better than the deployed "
            f"model's ({deployed_value}) -- keep the current deployment. Retraining alone "
            "didn't fix whatever ts-monitor flagged; that's worth investigating further (e.g. "
            "a genuine regime change may need a different model family or feature set, not "
            "just refreshed parameters of the same one)."
        )

    if redeploy_threshold_within_ci:
        ci_source = "both the candidate's and the deployed model's" if deployed_metrics_ci_used else "the candidate's own"
        reasoning += (
            f" Note: {ci_source} bootstrap CI implies an improvement range of "
            f"[{pct_improvement_ci_lower}%, {pct_improvement_ci_upper}%], which straddles the "
            f"{improvement_threshold_pct}% threshold -- this should_redeploy verdict is "
            "sensitive to backtest sampling noise, not a clean call."
        )

    return {
        "metric_name": metric_name,
        "candidate_value": round(candidate_value, 4),
        "deployed_value": round(deployed_value, 4),
        "pct_improvement": pct_improvement,
        "pct_improvement_ci_lower": pct_improvement_ci_lower,
        "pct_improvement_ci_upper": pct_improvement_ci_upper,
        "deployed_metrics_ci_used": deployed_metrics_ci_used,
        "redeploy_threshold_within_ci": redeploy_threshold_within_ci,
        "should_redeploy": should_redeploy,
        "reasoning": reasoning,
        "improvement_threshold_pct": improvement_threshold_pct,
    }


def execute_redeploy(
    csv_path: str,
    model_type: str,
    params: dict,
    horizon: int,
    backtest_metrics: dict,
    confirmed: bool = False,
    autonomous: bool = False,
    date_col: str = "date",
    value_col: str = "value",
    manifest_path: Optional[str] = None,
    autonomous_mode_path: Optional[str] = None,
) -> dict:
    """Actually perform a redeploy: retrain `model_type` on the full series
    with `params` (delegating to the matching
    omen.deploy.forecast_tools function) and record the
    result as the new deployment manifest.

    This refuses to do anything unless `confirmed=True` is passed
    explicitly -- there is no default that takes action. Passing
    confirmed=True is meant to happen in exactly two situations (see
    skills/ts-retrain/SKILL.md): a human has approved this specific
    redeploy in the current conversation, or an explicitly authorized
    autonomous-mode instruction covers this series. Don't set it to True
    just to see what happens.

    Pass `autonomous=True` for the second situation specifically -- an
    UNATTENDED call with no human turn in between. When `autonomous=True`,
    this ALSO calls check_autonomous_mode(csv_path) internally and refuses
    to act (even with confirmed=True) unless a standing authorization
    record exists for this series. This is a real, code-level check, not
    just a prose instruction the skill is trusted to follow correctly --
    call authorize_autonomous_mode first if one doesn't exist yet and a
    human or standing project instruction has genuinely granted it. Leave
    `autonomous` at its default (False) for ordinary human-confirmed
    calls; no authorization record is needed or checked in that case,
    since the human's in-conversation approval IS the authorization.

    `params` should be the same `params` dict a ts-forecaster fit_* call
    returned for the chosen candidate (fit_sarima/fit_ets/
    fit_gradient_boosted_trees's `params` fields match forecast_sarima/
    forecast_ets/forecast_gradient_boosted_trees's keyword arguments
    exactly). `model_type` must be one of "naive", "ets", "sarima", "gbt".

    Requires the `deploy` extra installed (statsmodels/scikit-learn)
    regardless of which model_type is used, since it imports
    omen.deploy.forecast_tools as a whole module.

    Returns `previous_deployment`: whatever the manifest held immediately
    before this call overwrote it (read before writing, not reconstructed
    afterward), or `None` if nothing was deployed yet for this series. The
    manifest itself still only ever holds the single current deployment,
    not a history -- this is a one-time snapshot in the ACTION'S OWN
    output, so what just changed is self-documenting from the tool call
    itself rather than something that has to be reconstructed from
    conversation history.
    """
    if not confirmed:
        return {
            "status": "not_executed",
            "error": (
                "confirmed=True was not passed. execute_redeploy performs a real "
                "redeploy (retrains the model and overwrites the deployment "
                "manifest) and refuses to act without an explicit confirmation "
                "flag -- whether that confirmation came from a human in this "
                "conversation or from an explicitly authorized autonomous-mode "
                "instruction. Set confirmed=True only once you actually have that."
            ),
        }

    if autonomous:
        auth = check_autonomous_mode(csv_path, autonomous_mode_path=autonomous_mode_path)
        if not auth.get("authorized"):
            return {
                "status": "not_executed",
                "error": (
                    "autonomous=True was passed, but no standing autonomous-mode "
                    f"authorization record was found for this series (checked "
                    f"{auth.get('checked_path', _autonomous_mode_path_for(csv_path, autonomous_mode_path))}). "
                    "Call authorize_autonomous_mode first -- only after a human or a "
                    "standing project instruction has genuinely and unambiguously "
                    "granted it -- or omit autonomous=True and use human-confirmed "
                    "mode (get an explicit go-ahead in conversation, then call this "
                    "with confirmed=True alone)."
                ),
            }

    if model_type not in _MODEL_TYPES:
        return {"error": f"Unknown model_type '{model_type}'. Must be one of {list(_MODEL_TYPES)}."}

    try:
        from omen.deploy import forecast_tools
    except ImportError as exc:
        return {
            "error": (
                f"execute_redeploy needs the 'deploy' extra installed to retrain "
                f"and forecast ({exc}). Run: pip install -e \".[deploy]\""
            )
        }

    from omen.data_prep import load_series

    df = load_series(csv_path, date_col, value_col)

    dispatch: dict[str, Callable[..., dict]] = {
        "naive": forecast_tools.forecast_naive,
        "ets": forecast_tools.forecast_ets,
        "sarima": forecast_tools.forecast_sarima,
        "gbt": forecast_tools.forecast_gradient_boosted_trees,
    }
    forecast_result = dispatch[model_type](df, horizon=horizon, **params)

    # Snapshot whatever was deployed BEFORE this call overwrites it -- read
    # before record_deployment writes, so the action's own output is
    # self-documenting about what it just replaced, rather than relying on
    # conversation history to reconstruct it. None if nothing was deployed
    # yet (a legitimate first-deployment case, not an error).
    previous = load_deployment_manifest(csv_path, manifest_path)
    previous_deployment = None if "error" in previous else previous

    manifest_result = record_deployment(
        csv_path,
        model=forecast_result["model"],
        params=params,
        backtest_metrics=backtest_metrics,
        horizon=horizon,
        manifest_path=manifest_path,
    )

    return {
        "status": "redeployed",
        "previous_deployment": previous_deployment,
        "forecast_result": forecast_result,
        "manifest": manifest_result["manifest"],
    }
