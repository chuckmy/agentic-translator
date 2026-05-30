#!/usr/bin/env python3
"""Build an arXiv-oriented LaTeX source and a simple HTML preview from the paper draft."""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "system_paper_draft.md"
OUT_DIR = ROOT / "paper"
TEX_OUT = OUT_DIR / "agentic_ai_translate_arxiv.tex"
HTML_OUT = OUT_DIR / "agentic_ai_translate_arxiv_preview.html"


TITLE = "Agentic AI Translate: An Agentic Translator Prototype for Translation as Communication Design"
AUTHOR = "Masaru Yamada"
AFFILIATION = "Rikkyo University; Translation Lab Inc."
KEYWORDS = (
    "agentic translation, translation studies metalanguage, skopos, MQM, "
    "document-level translation, large language models, translation specifications"
)


LATEX_UNICODE_REPLACEMENTS = {
    "\u2014": "---",
    "\u2013": "--",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2192": r"$\rightarrow$",
    "\u2194": r"$\leftrightarrow$",
    "\u00a9": r"\textcopyright{}",
    "\u00d7": r"$\times$",
    "\u00b7": r"$\cdot$",
    "\u2026": r"\ldots{}",
    "\u03b1": r"$\alpha$",
    "\u03b2": r"$\beta$",
    "\u00a7": r"\S{}",
    "\u2212": "-",
    "\u590f\u76ee\u6f31\u77f3": "Natsume Soseki",
    "\u82e6\u6c99\u5f25\u5148\u751f": "Kushami-sensei",
    "\u3060\u30fb\u3067\u3042\u308b\u8abf": "plain da/dearu style",
}


def sanitize_unicode(text: str) -> str:
    replacements = {
        "\u2014": "---",
        "\u2013": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": "``",
        "\u201d": "''",
        "\u2192": r"$\rightarrow$",
        "\u00a9": r"\textcopyright{}",
        "\u00d7": r"$\times$",
        "\u00b7": r"$\cdot$",
        "\u2026": r"\ldots{}",
        "\u2460": "1)",
        "\u2461": "2)",
        "\u2462": "3)",
        "\u2463": "4)",
        "\u250c": "+",
        "\u2510": "+",
        "\u2514": "+",
        "\u2518": "+",
        "\u251c": "+",
        "\u2524": "+",
        "\u2500": "-",
        "\u2502": "|",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def tex_escape_plain(text: str) -> str:
    tokens: list[str] = []

    def stash(match: re.Match[str]) -> str:
        tokens.append(match.group(0))
        return f"@@TOKEN{len(tokens) - 1}@@"

    text = re.sub(r"https?://[^\s,)]+", stash, text)
    for src, dst in LATEX_UNICODE_REPLACEMENTS.items():
        if src in text:
            tokens.append(dst)
            text = text.replace(src, f"@@TOKEN{len(tokens) - 1}@@")
    text = text.replace("\\", r"\textbackslash{}")
    for src, dst in [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]:
        text = text.replace(src, dst)
    for i, token in enumerate(tokens):
        safe = r"\url{" + token + "}" if token.startswith("http") else token
        text = text.replace(f"@@TOKEN{i}@@", safe)
    return text


def inline_tex(text: str) -> str:
    code_tokens: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_tokens.append(match.group(1))
        return f"@@CODE{len(code_tokens) - 1}@@"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    text = tex_escape_plain(text)

    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", text)

    for i, token in enumerate(code_tokens):
        code = sanitize_unicode(token)
        code = code.replace("\\", r"\textbackslash{}")
        code = code.replace("{", r"\{").replace("}", r"\}")
        text = text.replace(f"@@CODE{i}@@", r"\texttt{" + code + "}")
    return text


def extract_body(md: str) -> tuple[str, str, list[str]]:
    md = md.replace("\r\n", "\n")
    abstract_match = re.search(r"## Abstract\n\n(.*?)\n\n\*\*Keywords:\*\* (.*?)\n\n---", md, re.S)
    if not abstract_match:
        raise RuntimeError("Could not find abstract and keywords block.")
    abstract = abstract_match.group(1).strip()
    keywords = abstract_match.group(2).strip().rstrip(".")
    body = md[abstract_match.end() :].strip()
    body = re.sub(r"\n\n---\n\n", "\n\n", body)
    return abstract, keywords, body.splitlines()


def clean_heading(title: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.\s+", "", title.strip())


def convert_lines_to_tex(lines: list[str]) -> str:
    out: list[str] = []
    in_itemize = False
    in_verbatim = False
    in_math = False
    in_bibliography = False
    bib_index = 0

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            out.append(r"\begin{verbatim}" if not in_verbatim else r"\end{verbatim}")
            in_verbatim = not in_verbatim
            continue

        if line.strip() == "$$":
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            out.append(r"\[" if not in_math else r"\]")
            in_math = not in_math
            continue

        if in_math:
            math_line = sanitize_unicode(line)
            math_line = math_line.replace(r"\text{score}", r"\mathrm{score}")
            out.append(math_line)
            continue

        if in_verbatim:
            out.append(sanitize_unicode(line))
            continue

        if not line.strip():
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            out.append("")
            continue

        if line.startswith("## "):
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            title = clean_heading(line[3:])
            if title.lower() == "references":
                out.append(r"\begin{thebibliography}{99}")
                in_bibliography = True
            else:
                out.append(r"\section{" + inline_tex(title) + "}")
            continue

        if line.startswith("### "):
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            out.append(r"\subsection{" + inline_tex(clean_heading(line[4:])) + "}")
            continue

        if line.startswith("- "):
            if not in_itemize:
                out.append(r"\begin{itemize}[leftmargin=*]")
                in_itemize = True
            out.append(r"\item " + inline_tex(line[2:].strip()))
            continue

        if line.startswith("> "):
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            out.append(r"\begin{quote}\itshape " + inline_tex(line[2:].strip()) + r"\end{quote}")
            continue

        if in_bibliography and re.match(r"^[A-Z][A-Za-z' -]+,\s", line):
            if in_itemize:
                out.append(r"\end{itemize}")
                in_itemize = False
            bib_index += 1
            out.append(rf"\bibitem{{ref{bib_index}}} " + inline_tex(line))
            continue

        out.append(inline_tex(line))

    if in_itemize:
        out.append(r"\end{itemize}")
    if out and out[-1] != r"\end{thebibliography}":
        in_bib = any(line == r"\begin{thebibliography}{99}" for line in out)
        if in_bib:
            out.append(r"\end{thebibliography}")
    return "\n".join(out)


def build_tex(abstract: str, keywords: str, body_tex: str) -> str:
    return rf"""\documentclass[11pt]{{article}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{geometry}}
\usepackage{{microtype}}
\usepackage{{enumitem}}
\usepackage{{amsmath}}
\usepackage{{url}}
\usepackage[colorlinks=true,allcolors=blue]{{hyperref}}

\geometry{{margin=1in}}
\setlist{{nosep}}
\urlstyle{{same}}

\title{{{inline_tex(TITLE)}}}
\author{{{inline_tex(AUTHOR)}\\{inline_tex(AFFILIATION)}}}
\date{{Draft for arXiv submission -- May 16, 2026}}

\begin{{document}}
\maketitle

\begin{{abstract}}
{inline_tex(abstract)}
\end{{abstract}}

\noindent\textbf{{Keywords:}} {inline_tex(keywords)}.

{body_tex}

\end{{document}}
"""


def build_html(md: str) -> str:
    escaped = html.escape(md)
    escaped = re.sub(r"^# (.*)$", r"<h1>\1</h1>", escaped, flags=re.M)
    escaped = re.sub(r"^## (.*)$", r"<h2>\1</h2>", escaped, flags=re.M)
    escaped = re.sub(r"^### (.*)$", r"<h3>\1</h3>", escaped, flags=re.M)
    escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.*?)\*", r"<em>\1</em>", escaped)
    paragraphs = "\n".join(f"<p>{p}</p>" if not p.startswith("<h") else p for p in escaped.split("\n\n"))
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(TITLE)}</title>
<style>
body {{ font-family: Helvetica, Arial, sans-serif; line-height: 1.45; max-width: 820px; margin: 48px auto; color: #111; }}
h1 {{ font-size: 28px; line-height: 1.15; }}
h2 {{ margin-top: 32px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
h3 {{ margin-top: 24px; }}
pre {{ white-space: pre-wrap; background: #f6f6f6; padding: 12px; }}
blockquote {{ border-left: 3px solid #aaa; padding-left: 12px; color: #333; }}
</style>
</head>
<body>
{paragraphs}
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = SOURCE.read_text(encoding="utf-8")
    abstract, keywords, lines = extract_body(md)
    body_tex = convert_lines_to_tex(lines)
    TEX_OUT.write_text(build_tex(abstract, keywords, body_tex), encoding="utf-8")
    HTML_OUT.write_text(build_html(md), encoding="utf-8")
    print(TEX_OUT)
    print(HTML_OUT)


if __name__ == "__main__":
    main()
