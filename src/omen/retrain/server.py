"""
server.py — FastMCP server for the Layer 5 retrain-cycle tools.

Closes the loop after ts-monitor recommends retrain_now: gives the agent a
place to record what's actually deployed (so there's something to compare
against later) and a deterministic answer to "is a freshly retrained
candidate actually better enough to be worth redeploying."

This layer never calls ts-deploy itself and never redeploys anything on
its own -- it produces a recommendation for a human to act on. See
skills/ts-retrain/SKILL.md for the full workflow.

Run over stdio (how OpenClaw will launch it), after `pip install -e .`:
    ts-retrain-server
    # or: python -m omen.retrain.server
"""

from typing import Optional

from fastmcp import FastMCP

from .retrain_tools import (
    record_deployment as _record_deployment,
    load_deployment_manifest as _load_deployment_manifest,
    compare_candidate_to_deployed as _compare_candidate_to_deployed,
    execute_redeploy as _execute_redeploy,
    authorize_autonomous_mode as _authorize_autonomous_mode,
    revoke_autonomous_mode as _revoke_autonomous_mode,
    check_autonomous_mode as _check_autonomous_mode,
)

mcp = FastMCP("ts-retrain")


@mcp.tool()
def record_deployment(
    csv_path: str,
    model: str,
    params: dict,
    backtest_metrics: dict,
    horizon: int,
    manifest_path: Optional[str] = None,
) -> dict:
    """Persist a record of what's currently deployed: model type, params,
    its backtest metrics from ts-forecaster, and the forecast horizon.
    Call this right after an actual, human-confirmed ts-deploy call -- not
    after every exploratory forecast_* call. Overwrites any existing
    manifest for this series; it always reflects the single
    currently-deployed model, not a history.

    Returns `written_to`: the exact path the manifest was written to --
    useful for confirming where state actually lives, especially if you
    passed a non-default `manifest_path`.

    Args:
        csv_path: Path to the series CSV this model was deployed against.
        model: Model name/type, e.g. "SARIMA", "ETS (Holt-Winters)".
        params: The params dict the deployed forecast_* tool used.
        backtest_metrics: The backtest_metrics dict from the matching
            ts-forecaster fit_* call that justified deploying this model.
        horizon: The forecast horizon (in steps) that was deployed.
        manifest_path: Where to write the manifest. Defaults to
            deployment_manifest.json next to csv_path.
    """
    return _record_deployment(
        csv_path,
        model=model,
        params=params,
        backtest_metrics=backtest_metrics,
        horizon=horizon,
        manifest_path=manifest_path,
    )


@mcp.tool()
def load_deployment_manifest(csv_path: str, manifest_path: Optional[str] = None) -> dict:
    """Read back what's currently recorded as deployed for this series.
    Returns an error dict (not an exception) if nothing has been recorded
    yet -- that's an expected state early in a series' lifecycle, not a bug.

    Args:
        csv_path: Path to the series CSV.
        manifest_path: Where to look. Defaults to deployment_manifest.json
            next to csv_path.
    """
    return _load_deployment_manifest(csv_path, manifest_path=manifest_path)


@mcp.tool()
def compare_candidate_to_deployed(
    candidate_metrics: dict,
    deployed_metrics: dict,
    metric_name: str = "mape_pct",
    improvement_threshold_pct: float = 10.0,
) -> dict:
    """Deterministic decision: does a freshly backtested candidate model
    beat what's currently deployed by enough to be worth redeploying? This
    is intentionally rule-based, not left to model judgment -- same reason
    ts-monitor__recommend_retraining is deterministic. Requires a relative
    improvement of at least improvement_threshold_pct before recommending
    a swap, to avoid churn from noise-level differences. Also echoes back
    `candidate_value`/`deployed_value` -- the exact metric values compared
    (rounded), handy for citing in a report without re-reading your own
    inputs.

    If candidate_metrics also has a bootstrap CI for metric_name (i.e.
    `{metric_name}_ci_lower`/`{metric_name}_ci_upper` -- present on any
    recent ts-forecaster fit_* result), this also reports
    `pct_improvement_ci_lower`/`pct_improvement_ci_upper` (the implied
    improvement range) and flags `redeploy_threshold_within_ci: true` when
    `improvement_threshold_pct` falls inside that range -- meaning
    should_redeploy is sensitive to backtest sampling noise, not a clean
    call. If deployed_metrics ALSO has a CI for metric_name, its
    uncertainty is combined in too via interval arithmetic over both
    ranges at once (`deployed_metrics_ci_used: true`); otherwise the range
    reflects the candidate's own uncertainty alone with deployed_value
    treated as fixed (`deployed_metrics_ci_used: false`).

    Args:
        candidate_metrics: backtest_metrics dict from a fresh
            ts-forecaster fit_* call on the updated series.
        deployed_metrics: backtest_metrics dict from
            load_deployment_manifest's "backtest_metrics" field.
        metric_name: Which key to compare; must be present and
            lower-is-better in both dicts (e.g. "mape_pct", "mae", "rmse").
        improvement_threshold_pct: Minimum relative improvement (%) the
            candidate needs over the deployed model before this
            recommends redeploying.
    """
    return _compare_candidate_to_deployed(
        candidate_metrics,
        deployed_metrics,
        metric_name=metric_name,
        improvement_threshold_pct=improvement_threshold_pct,
    )


@mcp.tool()
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
    """Actually perform a redeploy: retrain model_type on the full series
    with params (delegating to the matching ts-deploy forecast function)
    and record the result as the new deployment manifest.

    Refuses to do anything unless confirmed=True is passed explicitly --
    there is no default that takes action. Only pass confirmed=True in one
    of two situations (see the ts-retrain SKILL.md): a human has approved
    this specific redeploy in the current conversation, or an explicitly
    authorized autonomous-mode instruction covers this series.

    Pass autonomous=True for the second situation specifically. When set,
    this ALSO calls check_autonomous_mode(csv_path) internally and refuses
    to act -- even with confirmed=True -- unless a standing authorization
    record exists for this series (call authorize_autonomous_mode first).
    This is a real code-level check, not just a prose instruction. Leave
    autonomous at its default (False) for ordinary human-confirmed calls.

    On success (`status: "redeployed"`), also returns `forecast_result`
    (the actual new forecast just produced -- same shape as the matching
    ts-deploy `forecast_*` tool's own result) and `manifest` (the deployment
    manifest as just written -- same shape as `load_deployment_manifest`'s
    result). Report both when describing what this call did, not just the
    bare "redeployed successfully" status.

    Also returns `previous_deployment`: whatever the manifest held
    immediately before this call overwrote it, or null if nothing was
    deployed yet for this series -- lets you report what actually changed
    straight from this tool's own output, instead of relying on
    conversation history to reconstruct it. The manifest itself still only
    ever holds the single current deployment, not a history.

    Args:
        csv_path: Path to the series CSV to retrain and forecast on.
        model_type: One of "naive", "ets", "sarima", "gbt".
        params: The params dict a ts-forecaster fit_* call returned for
            the chosen candidate -- pass it through unchanged. For "naive",
            use {"method": ..., "seasonal_period": ...} matching
            forecast_naive's arguments.
        horizon: Forecast horizon in steps.
        backtest_metrics: The chosen candidate's backtest_metrics, to
            record in the new deployment manifest.
        confirmed: Must be explicitly True or this call is a no-op that
            returns an explanatory error.
        autonomous: True only for an unattended autonomous-mode call --
            triggers the check_autonomous_mode authorization check above.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
        manifest_path: Where to write the manifest. Defaults to
            deployment_manifest.json next to csv_path.
        autonomous_mode_path: Where to look for the authorization record.
            Defaults to autonomous_mode.json next to csv_path.
    """
    return _execute_redeploy(
        csv_path,
        model_type=model_type,
        params=params,
        horizon=horizon,
        backtest_metrics=backtest_metrics,
        confirmed=confirmed,
        autonomous=autonomous,
        date_col=date_col,
        value_col=value_col,
        manifest_path=manifest_path,
        autonomous_mode_path=autonomous_mode_path,
    )


@mcp.tool()
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
    this tool performs no judgment of its own about whether that
    authorization is legitimate, it only persists a decision that's
    already been made elsewhere. Overwrites any existing record for this
    series; reflects the CURRENT authorization state, not a history.

    Returns `written_to` (the exact path the record was written to) and
    `record`: the full authorization record as written (`csv_path`,
    `authorized`, `authorized_at`, `authorized_by`, `note`) -- the same
    shape `check_autonomous_mode` returns back later when `authorized` is
    true, so you can cite exactly who authorized this and when in a later
    report instead of just knowing that it happened.

    Args:
        csv_path: Path to the series CSV this authorization applies to.
        authorized_by: Who/what granted this, e.g. "user, in conversation
            on 2026-07-21" or "AGENTS.md standing instruction" -- so the
            record is self-explanatory later, not just a bare boolean.
        note: Optional free-text context.
        autonomous_mode_path: Where to write the record. Defaults to
            autonomous_mode.json next to csv_path.
    """
    return _authorize_autonomous_mode(csv_path, authorized_by=authorized_by, note=note, autonomous_mode_path=autonomous_mode_path)


@mcp.tool()
def revoke_autonomous_mode(csv_path: str, autonomous_mode_path: Optional[str] = None) -> dict:
    """Remove any autonomous-mode authorization record for this series.
    After this, execute_redeploy(..., autonomous=True) calls for this
    series will refuse until authorize_autonomous_mode is called again.
    Safe to call even if no record exists.

    Args:
        csv_path: Path to the series CSV.
        autonomous_mode_path: Where to look. Defaults to
            autonomous_mode.json next to csv_path.
    """
    return _revoke_autonomous_mode(csv_path, autonomous_mode_path=autonomous_mode_path)


@mcp.tool()
def check_autonomous_mode(csv_path: str, autonomous_mode_path: Optional[str] = None) -> dict:
    """Read whatever authorize_autonomous_mode last recorded for this
    series. When authorized, returns the full record: `authorized: true`,
    plus `authorized_at`, `authorized_by`, and `note` -- cite these when
    reporting that autonomous mode applied to a redeploy, not just the
    bare boolean. When nothing has been recorded, returns
    `{"authorized": False, "checked_path": ..., "note": ...}` -- NOT an
    error, since that's the default, expected state; `checked_path` names
    exactly which file was checked, useful if authorization seems to be
    missing unexpectedly (e.g. a mismatched `autonomous_mode_path`).

    Args:
        csv_path: Path to the series CSV.
        autonomous_mode_path: Where to look. Defaults to
            autonomous_mode.json next to csv_path.
    """
    return _check_autonomous_mode(csv_path, autonomous_mode_path=autonomous_mode_path)


def main():
    """Entry point for the `ts-retrain-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
