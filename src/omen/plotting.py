"""
plotting.py

Shared rendering infrastructure for every plot_* tool across all five
layers. Each layer's own plot_tools.py builds a matplotlib Figure and
hands it to render_plot() here, which returns it as an inline FastMCP
Image content block (always -- real visual feedback in the same turn,
no separate file-open step) plus an optional on-disk PNG (if out_path
is given) and a small structured status dict.

These tools exist purely as a visual complement to the exact numbers
every other tool in this project already returns -- never a
replacement for them. A plot_* tool never reports a finding a JSON
tool doesn't already report on its own; it just makes that finding
easier to see at a glance.
"""

import io
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # headless rendering -- no display backend available or needed
import matplotlib.pyplot as plt  # noqa: E402

from fastmcp.tools.tool import ToolResult  # noqa: E402
from fastmcp.utilities.types import Image  # noqa: E402


def render_plot(fig: "plt.Figure", out_path: Optional[str] = None, **status_extra) -> ToolResult:
    """Render a finished matplotlib Figure to PNG bytes, return it as an
    inline FastMCP Image content block plus a small structured status
    dict (status, written_to, and anything the caller wants surfaced
    alongside the image -- e.g. which points got plotted).

    Always closes the figure after rendering (matplotlib's Agg backend
    keeps every unclosed figure alive in memory, which matters here
    since a long agentic session can call these tools many times).

    Args:
        fig: A fully-built matplotlib Figure, ready to save.
        out_path: If given, also writes the PNG to this path on disk
            (in addition to the inline image every call already
            returns) -- same optional-persistence convention as
            ts-analyst's generate_synthetic_data(out_path=...).
        **status_extra: Extra keys merged into the structured status
            dict returned alongside the image (e.g. n_points_plotted).
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    png_bytes = buf.getvalue()

    written_to = None
    if out_path:
        with open(out_path, "wb") as f:
            f.write(png_bytes)
        written_to = out_path

    structured = {"status": "ok", "written_to": written_to}
    structured.update(status_extra)

    return ToolResult(
        content=[Image(data=png_bytes, format="png")],
        structured_content=structured,
    )
