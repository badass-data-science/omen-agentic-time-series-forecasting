"""
assemble_book.py

Concatenates "Agentic Time Series Forecasting for Supervillains" -- front
matter, all 22 chapters, and the three appendices, in reading order -- into
a single Markdown file, then (by default) renders that file to PDF via
pandoc. `outline.md` is deliberately excluded: it's this project's internal
planning document, never reader-facing, and was never part of the book
itself.

Reading order is: dedication.md, about_the_author.md,
ai_use_statement.md, chapter-01 through chapter-22 (sorted by filename,
which sorts correctly since every chapter number is zero-padded), then
appendix-a, appendix-b, appendix-c (alphabetical, which is also their
intended reading order).

Every chapter links its images with a path relative to this directory's
parent (e.g. `examples/images/ch08_naive_backtest.png`, written as if the
chapter file itself lives directly in book/). Concatenating files from
different directories into one output file breaks that relative path
unless it's rewritten to be relative to the assembled file's own new
location instead -- this script does that rewrite automatically, so the
assembled Markdown's images resolve correctly regardless of --out.

Usage:
    python assemble_book.py                  # writes dist/omen-book.md and dist/omen-book.pdf
    python assemble_book.py --out DIR         # writes to a different directory
    python assemble_book.py --skip-pdf        # Markdown only, no pandoc invocation

Requires nothing extra for the Markdown output. The PDF step requires
pandoc plus a working LaTeX engine (xelatex by default -- pass
--pdf-engine to use a different one); if pandoc isn't on PATH, this script
says so plainly and still leaves the Markdown file written, rather than
failing the whole run.
"""

import argparse
import os
import re
import subprocess
import sys

BOOK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TITLE = "Agentic Time Series Forecasting for Supervillains"
EDITION = "0th Edition"
AUTHOR = "Emily Marie Williams, author of Omen"

IMAGE_LINK_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")

# Pandoc's code blocks (Shaded/Highlighting, via fancyvrb) don't wrap long
# lines by default -- a JSON example wider than the page margin just runs
# off the edge and gets cut off. fvextra's breaklines/breakanywhere fixes
# this (see pandoc's own manual on the topic); there's no equivalent
# -M/-V metadata flag for it, so it has to go in via --include-in-header.
_LATEX_HEADER = "\\usepackage{fvextra}\n\\fvset{breaklines=true,breakanywhere=true}\n"


def _ordered_source_files():
    """dedication -> about_the_author -> ai_use_statement ->
    chapter-01..22 (sorted, zero-padded so this is also numeric order)
    -> the three appendices, alphabetically. outline.md is excluded on
    purpose -- see module docstring."""
    chapters = sorted(
        f for f in os.listdir(BOOK_DIR)
        if f.startswith("chapter-") and f.endswith(".md")
    )
    appendices = sorted(
        f for f in os.listdir(BOOK_DIR)
        if f.startswith("appendix-") and f.endswith(".md")
    )
    return ["dedication.md", "about_the_author.md", "ai_use_statement.md"] + chapters + appendices


def _rewrite_image_links(content: str, out_dir: str) -> str:
    """Rewrite every Markdown image link so it resolves correctly from
    out_dir, instead of from BOOK_DIR (where the source chapter file
    actually lives and where its own relative path is written from)."""

    def _rewrite(match):
        prefix, link, suffix = match.groups()
        if link.startswith(("http://", "https://")):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(BOOK_DIR, link))
        new_link = os.path.relpath(abs_path, out_dir)
        return f"{prefix}{new_link}{suffix}"

    return IMAGE_LINK_RE.sub(_rewrite, content)


def assemble(out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    parts = []
    for filename in _ordered_source_files():
        with open(os.path.join(BOOK_DIR, filename), encoding="utf-8") as f:
            content = f.read()
        parts.append(_rewrite_image_links(content, out_dir).strip())

    md_path = os.path.join(out_dir, "omen-book.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts) + "\n")
    return md_path


def render_pdf(md_path: str, out_dir: str, pdf_engine: str) -> bool:
    """Returns True on success. Prints a plain explanation and returns
    False rather than raising if pandoc (or the PDF engine) isn't
    available -- a missing PDF renderer shouldn't take the Markdown
    output down with it.

    Runs pandoc with its CWD set to out_dir, passing only the basename of
    md_path: pandoc resolves an input file's own relative image links
    against pandoc's CWD, not against the input file's directory, and
    _rewrite_image_links() already rewrote every link to be relative to
    out_dir specifically -- the two have to agree, or every image
    resolves to a wrong (if syntactically valid) path.

    mainfont/monofont are pinned to DejaVu, which (unlike the LaTeX
    default, Latin Modern) actually covers the Greek letters and math
    symbols (e.g. lambda, mu, sigma, the almost-equal sign) this book's
    prose uses inline -- Latin Modern silently drops them from the PDF
    with a "Missing character" warning instead of failing loudly.
    """
    pdf_path_abs = os.path.abspath(os.path.join(out_dir, "omen-book.pdf"))
    header_path = os.path.join(out_dir, "_pandoc-header.tex")
    with open(header_path, "w", encoding="utf-8") as f:
        f.write(_LATEX_HEADER)

    cmd = [
        "pandoc",
        os.path.basename(md_path),
        "-o", pdf_path_abs,
        f"--pdf-engine={pdf_engine}",
        "--toc",
        "--top-level-division=chapter",
        "-V", "documentclass=book",
        "-V", "geometry:margin=1in",
        "-V", "mainfont=DejaVu Serif",
        "-V", "monofont=DejaVu Sans Mono",
        "-M", f"title={TITLE}",
        "-M", f"subtitle={EDITION}",
        "-M", f"author={AUTHOR}",
        "--include-in-header", os.path.basename(header_path),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=os.path.abspath(out_dir))
    except FileNotFoundError:
        print(
            "pandoc not found on PATH -- skipping PDF output. "
            f"The assembled Markdown is still at {md_path}; "
            "install pandoc (and a LaTeX engine, e.g. xelatex) and re-run "
            "to also get a PDF.",
            file=sys.stderr,
        )
        return False
    except subprocess.CalledProcessError:
        print(
            f"pandoc exited with an error (see above) -- PDF not written. "
            f"The assembled Markdown is still at {md_path}.",
            file=sys.stderr,
        )
        return False
    finally:
        os.remove(header_path)
    print(f"Wrote {pdf_path_abs}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Assemble the book into one Markdown file, then PDF via pandoc.")
    parser.add_argument("--out", type=str, default="dist", help="Directory to write output into.")
    parser.add_argument("--skip-pdf", action="store_true", help="Only write the assembled Markdown; don't invoke pandoc.")
    parser.add_argument("--pdf-engine", type=str, default="xelatex", help="pandoc --pdf-engine to use.")
    args = parser.parse_args()

    md_path = assemble(args.out)
    print(f"Wrote {md_path} ({len(_ordered_source_files())} source files)")

    if not args.skip_pdf:
        render_pdf(md_path, args.out, args.pdf_engine)


if __name__ == "__main__":
    main()
