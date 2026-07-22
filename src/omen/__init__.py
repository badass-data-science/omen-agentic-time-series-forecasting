"""
omen

Five layers of agentic time series tooling, each exposed as a FastMCP
server, plus companion OpenClaw skills bundled alongside them:

- omen.analyst    -> ts-analyst    (explore & recommend an approach)
- omen.forecaster -> ts-forecaster (fit & backtest candidate models)
- omen.deploy     -> ts-deploy     (retrain on full data, forecast forward)
- omen.monitor    -> ts-monitor    (check deployed forecasts, recommend retraining)
- omen.retrain    -> ts-retrain    (decide whether/how to retrain and redeploy)

See each subpackage's server.py for its MCP tools, and skills_dir() below
for the bundled SKILL.md playbooks.
"""

from importlib.resources import files as _files
from typing import Any

__version__ = "0.1.0"


def skills_dir() -> Any:
    """Return the path to the bundled OpenClaw skill directories
    (ts-analyst/, ts-forecaster/, ts-deploy/, ts-monitor/), so they can be
    copied into an OpenClaw workspace after `pip install`:

        cp -r "$(python -c 'import omen as t; print(t.skills_dir())')"/* \\
            ~/.openclaw/workspace/skills/
    """
    return _files("omen") / "skills"
