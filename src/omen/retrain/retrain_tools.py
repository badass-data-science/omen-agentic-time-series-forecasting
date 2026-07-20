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

record_deployment/load_deployment_manifest/compare_candidate_to_deployed
are pure diagnostics with no side effects beyond the manifest file itself.
execute_redeploy is the one function in this whole toolkit that takes a
real production action (retrains a model and overwrites the deployment
manifest) -- it refuses to run unless called with confirmed=True, which is
never its default. See skills/ts-retrain/SKILL.md for the two ways that
confirmation is meant to be reached: a human approving in-conversation, or
an explicitly authorized autonomous mode.
"""

import json
import os
from datetime import datetime, timezone

DEFAULT_MANIFEST_FILENAME = "deployment_manifest.json"

_MODEL_TYPES = ("naive", "ets", "sarima", "gbt")


def _manifest_path_for(csv_path: str, manifest_path: str = None) -> str:
    """Default manifest location: alongside the series CSV, unless an
    explicit path is given."""
    if manifest_path:
        return manifest_path
    directory = os.path.dirname(os.path.abspath(csv_path))
    return os.path.join(directory, DEFAULT_MANIFEST_FILENAME)


def record_deployment(
    csv_path: str,
    model: str,
    params: dict,
    backtest_metrics: dict,
    horizon: int,
    manifest_path: str = None,
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


def load_deployment_manifest(csv_path: str, manifest_path: str = None) -> dict:
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

    if deployed_value == 0:
        pct_improvement = None
        should_redeploy = candidate_value < deployed_value
    else:
        pct_improvement = round(100 * (deployed_value - candidate_value) / deployed_value, 2)
        should_redeploy = pct_improvement >= improvement_threshold_pct

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

    return {
        "metric_name": metric_name,
        "candidate_value": round(candidate_value, 4),
        "deployed_value": round(deployed_value, 4),
        "pct_improvement": pct_improvement,
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
    date_col: str = "date",
    value_col: str = "value",
    manifest_path: str = None,
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

    `params` should be the same `params` dict a ts-forecaster fit_* call
    returned for the chosen candidate (fit_sarima/fit_ets/
    fit_gradient_boosted_trees's `params` fields match forecast_sarima/
    forecast_ets/forecast_gradient_boosted_trees's keyword arguments
    exactly). `model_type` must be one of "naive", "ets", "sarima", "gbt".

    Requires the `deploy` extra installed (statsmodels/scikit-learn)
    regardless of which model_type is used, since it imports
    omen.deploy.forecast_tools as a whole module.
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

    dispatch = {
        "naive": forecast_tools.forecast_naive,
        "ets": forecast_tools.forecast_ets,
        "sarima": forecast_tools.forecast_sarima,
        "gbt": forecast_tools.forecast_gradient_boosted_trees,
    }
    forecast_result = dispatch[model_type](df, horizon=horizon, **params)

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
        "forecast_result": forecast_result,
        "manifest": manifest_result["manifest"],
    }
