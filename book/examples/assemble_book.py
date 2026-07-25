"""
assemble_book.py

Concatenates "Agentic Time Series Forecasting for Supervillains" -- front
matter, all 22 chapters, and the three appendices, in reading order -- into
a single Markdown file, then (by default) renders that file to PDF AND
EPUB via pandoc. `outline.md` is deliberately excluded: it's this
project's internal planning document, never reader-facing, and was never
part of the book itself. The PDF's title page shows, top to bottom:
title, author, book/title-page-image.png (if present), then edition. The
EPUB gets the same title/author metadata and that same image as its
cover (if present), but not the PDF's six-part \\part{} divider structure
-- see render_epub()'s docstring for why.

Reading order is: dedication.md, about_the_author.md, about_the_series.md,
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
    python assemble_book.py                  # writes dist/omen-book.{md,pdf,epub}
    python assemble_book.py --out DIR         # writes to a different directory
    python assemble_book.py --skip-pdf        # skip the PDF (still writes EPUB)
    python assemble_book.py --skip-epub       # skip the EPUB (still writes PDF)

Requires nothing extra for the Markdown output. The PDF step requires
pandoc plus a working LaTeX engine (xelatex by default -- pass
--pdf-engine to use a different one); the EPUB step requires only pandoc
itself. If pandoc isn't on PATH, this script says so plainly for
whichever step needed it and still leaves the Markdown file (and any
other output that didn't need pandoc) written, rather than failing the
whole run.
"""

import argparse
import os
import re
import subprocess
import sys

BOOK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TITLE = "Agentic Time Series Forecasting for Supervillains"
EDITION = "0th Edition"
AUTHOR = "Emily Marie Williams"
TITLE_PAGE_IMAGE = os.path.join(BOOK_DIR, "title-page-image.png")

IMAGE_LINK_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")

# The book is organized into six parts (see outline.md's own "## Part N"
# headers -- outline.md itself is excluded from the assembled book, so
# this mapping is the only place that structure is expressed in anything
# reader-facing). Keyed by the chapter filename that OPENS each part;
# assemble() injects a raw-LaTeX \part{...} command immediately before
# that file's own content, which pandoc's `book` documentclass renders as
# a real, distinct part-title page AND a real top-level `--toc` entry --
# neither of which a plain `# Chapter N` heading alone produces.
PART_OPENERS = {
    "chapter-01-introducing-omen-and-agentic-ai.md": "Part I — Meet Your New Henchman",
    "chapter-03-first-contact.md": "Part II — Reading the Series Before You Trust It",
    "chapter-08-the-floor-is-naive.md": "Part III — Building and Judging Candidate Models",
    "chapter-14-deploying-for-real.md": "Part IV — Shipping and Living With a Forecast",
    "chapter-18-should-you-even-redeploy.md": "Part V — The Retrain Decision and Beyond",
    "chapter-20-prompting-omen-like-you-mean-it.md": "Part VI — Becoming a Better Forecasting Villain",
}

# Pandoc's code blocks (Shaded/Highlighting, via fancyvrb) don't wrap long
# lines by default -- a JSON example wider than the page margin just runs
# off the edge and gets cut off. fvextra's breaklines/breakanywhere fixes
# this (see pandoc's own manual on the topic); there's no equivalent
# -M/-V metadata flag for it, so it has to go in via --include-in-header.
_CODE_WRAP_HEADER = (
    "\\usepackage{fvextra}\n\\fvset{breaklines=true,breakanywhere=true}\n"
    "\\usepackage{seqsplit}\n"
    "\\DeclareRobustCommand{\\texttt}[1]{\\seqsplit{#1}}\n"
)


_LATEX_SPECIAL_CHARS = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
}


def _latex_escape(text: str) -> str:
    return "".join(_LATEX_SPECIAL_CHARS.get(c, c) for c in text)


def _custom_title_page_header() -> str:
    """LaTeX that fully replaces \\maketitle with a hand-laid-out title
    page: title, author, TITLE_PAGE_IMAGE, then edition, in that order.

    Pandoc's own default template builds the title page from \\title/
    \\author/\\date plus a \\subtitle hack that APPENDS the subtitle text
    directly onto \\@title (so it always prints wherever \\@title itself
    is used, immediately after the title) -- that structure can't put
    the edition AFTER the author/image without rewriting \\maketitle
    entirely, so this bypasses \\@title/\\@author/\\subtitle altogether
    and hard-codes TITLE/AUTHOR/EDITION as literal (escaped) text
    instead. -M title=/-M author= are still passed to pandoc separately
    for the PDF's pdftitle/pdfauthor metadata, which is unrelated to
    this visual layout.

    An absolute path is used for the image deliberately -- pandoc's CWD
    for the actual build is out_dir, not BOOK_DIR, so a path relative to
    BOOK_DIR would resolve wrong once handed to LaTeX as a raw
    \\includegraphics argument (unlike Markdown image links, which
    _rewrite_image_links() already handles separately).

    The image line is omitted (not a failed build) if TITLE_PAGE_IMAGE
    isn't actually there.
    """
    image_line = ""
    if os.path.isfile(TITLE_PAGE_IMAGE):
        # height capped (not just width) so the image can never claim more
        # than a fixed share of the page regardless of trim size -- at
        # 7in x 9.19in, an image sized purely by width overflowed the page
        # and pushed EDITION onto a second page; keepaspectratio means
        # whichever of width/height is more restrictive wins, no distortion.
        image_line = (
            "    \\includegraphics[width=0.85\\textwidth,height=0.35\\textheight,"
            f"keepaspectratio]{{{TITLE_PAGE_IMAGE}}}\\par\n"
        )
    else:
        print(f"Note: {TITLE_PAGE_IMAGE} not found -- title page will have no image.", file=sys.stderr)

    return (
        "\\usepackage{graphicx}\n"
        "\\usepackage{xcolor}\n"
        "\\makeatletter\n"
        "\\renewcommand{\\maketitle}{%\n"
        "  \\begin{titlepage}\n"
        "  \\pagecolor{black}\n"
        "  \\color{white}\n"
        "  \\begin{center}\n"
        "    \\vspace*{\\fill}\n"
        f"    {{\\LARGE {_latex_escape(TITLE)} \\par}}\n"
        "    \\vspace{2em}\n"
        f"    {{\\large {_latex_escape(AUTHOR)} \\par}}\n"
        "    \\vfill\n"
        f"{image_line}"
        "    \\vfill\n"
        f"    {{\\large {_latex_escape(EDITION)} \\par}}\n"
        "    \\vspace*{\\fill}\n"
        "  \\end{center}\n"
        "  \\end{titlepage}\n"
        "  \\pagecolor{white}\n"
        "  \\color{black}\n"
        "}\n"
        "\\makeatother\n"
    )


def _ordered_source_files():
    """dedication -> about_the_author -> about_the_series -> ai_use_statement ->
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
    return (
        ["dedication.md", "about_the_author.md", "about_the_series.md", "ai_use_statement.md"]
        + chapters
        + appendices
    )


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


def _part_marker(title: str) -> str:
    """A raw-LaTeX block pandoc passes through verbatim to the PDF --
    \\part{} is what actually gets this title its own divider page and
    its own top-level entry in --toc, neither of which a Markdown
    heading (which this book reserves for chapters/sections) can do."""
    return f'```{{=latex}}\n\\part{{{_latex_escape(title)}}}\n```'


def assemble(out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    parts = []
    for filename in _ordered_source_files():
        if filename in PART_OPENERS:
            parts.append(_part_marker(PART_OPENERS[filename]))
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
        f.write(_CODE_WRAP_HEADER)
        f.write(_custom_title_page_header())

    cmd = [
        "pandoc",
        os.path.basename(md_path),
        "-o", pdf_path_abs,
        f"--pdf-engine={pdf_engine}",
        "--toc",
        "--top-level-division=chapter",
        "-V", "documentclass=book",
        # 7in x 9.19in -- O'Reilly's standard "animal book" trim size, not
        # the LaTeX book class's US Letter default. Margin trimmed from
        # the old 1in to 0.75in to keep a reasonable text width at this
        # smaller page size.
        "-V", "geometry:paperwidth=7in,paperheight=9.19in,margin=0.75in",
        "-V", "mainfont=DejaVu Serif",
        "-V", "monofont=DejaVu Sans Mono",
        "-M", f"title={TITLE}",
        "-M", f"author={AUTHOR}",  # PDF pdftitle/pdfauthor metadata only -- the visual title page comes from _custom_title_page_header()
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


def render_epub(md_path: str, out_dir: str) -> bool:
    """Returns True on success, False (with a plain explanation, not a
    traceback) if pandoc isn't available -- same non-fatal-missing-tool
    handling as render_pdf.

    Uses the exact same assembled Markdown as the PDF, run with pandoc's
    CWD set to out_dir for the same reason render_pdf does: image links
    were already rewritten relative to out_dir by assemble(), and the
    cover image path below has to agree with that same CWD.

    KNOWN GAP, not an oversight: this does NOT get the six \\part{...}
    dividers render_pdf's PDF gets (see PART_OPENERS). Those are raw
    LaTeX blocks (` ```{=latex} `) -- pandoc only emits a raw block into
    the OUTPUT if the raw block's own tagged format matches the writer,
    so for EPUB (not LaTeX) they're silently dropped, not an error. The
    EPUB's nav/TOC is therefore chapters-and-sections only, the same
    shape the PDF itself had before this session added \\part{} support.
    Giving EPUB equivalent Part-level nav structure would need a
    different mechanism (e.g. a real Markdown heading one level above
    chapters, built only for this output path) -- not implemented here.
    """
    epub_path_abs = os.path.abspath(os.path.join(out_dir, "omen-book.epub"))

    cmd = [
        "pandoc",
        os.path.basename(md_path),
        "-o", epub_path_abs,
        "--toc",
        "-M", f"title={TITLE}",
        "-M", f"author={AUTHOR}",
    ]
    if os.path.exists(TITLE_PAGE_IMAGE):
        cmd += ["--epub-cover-image", os.path.relpath(TITLE_PAGE_IMAGE, out_dir)]

    try:
        subprocess.run(cmd, check=True, cwd=os.path.abspath(out_dir))
    except FileNotFoundError:
        print(
            "pandoc not found on PATH -- skipping EPUB output. "
            f"The assembled Markdown is still at {md_path}; "
            "install pandoc and re-run to also get an EPUB.",
            file=sys.stderr,
        )
        return False
    except subprocess.CalledProcessError:
        print(
            f"pandoc exited with an error (see above) -- EPUB not written. "
            f"The assembled Markdown is still at {md_path}.",
            file=sys.stderr,
        )
        return False
    print(f"Wrote {epub_path_abs}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Assemble the book into one Markdown file, then PDF/EPUB via pandoc.")
    parser.add_argument("--out", type=str, default="dist", help="Directory to write output into.")
    parser.add_argument("--skip-pdf", action="store_true", help="Don't invoke pandoc for the PDF.")
    parser.add_argument("--skip-epub", action="store_true", help="Don't invoke pandoc for the EPUB.")
    parser.add_argument("--pdf-engine", type=str, default="xelatex", help="pandoc --pdf-engine to use.")
    args = parser.parse_args()

    md_path = assemble(args.out)
    print(f"Wrote {md_path} ({len(_ordered_source_files())} source files)")

    if not args.skip_pdf:
        render_pdf(md_path, args.out, args.pdf_engine)
    if not args.skip_epub:
        render_epub(md_path, args.out)


if __name__ == "__main__":
    main()
