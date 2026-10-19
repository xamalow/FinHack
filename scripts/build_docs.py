"""Build the submission PDFs from docs/*.md: Markdown to styled HTML, then headless Chrome to A4 PDF.

    uv run --no-project --with markdown python scripts/build_docs.py
Writes docs/pdf/TECHNICAL_DOCUMENTATION.pdf and docs/pdf/SECURITY_SELF_ASSESSMENT.pdf.
"""
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = DOCS / "pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NAMES = ["TECHNICAL_DOCUMENTATION", "SECURITY_SELF_ASSESSMENT"]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #111827; font-size: 10pt; line-height: 1.5; }
p.logo { margin: 0 0 10px; }
h1 { font-size: 21pt; letter-spacing: -0.02em; margin: 4px 0 4px; }
h1 + p { color: #6b7280; margin-top: 0; font-size: 9.5pt; }
h2 { font-size: 14pt; letter-spacing: -0.01em; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #2563eb; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 16px 0 6px; color: #1d4ed8; break-after: avoid; }
a { color: #2563eb; text-decoration: none; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 8.6pt; background: #f1f5f9; padding: 0 3px; border-radius: 3px; }
pre { background: #0b1220; color: #e5e7eb; padding: 10px 12px; border-radius: 8px; font-size: 8.2pt; line-height: 1.45; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.6pt; }
th { background: #eff6ff; color: #1e3a8a; text-align: left; font-weight: 600; }
th, td { border: 1px solid #dbe3ee; padding: 4px 6px; vertical-align: top; }
tr { break-inside: avoid; }
td code { font-size: 7.9pt; }
img { max-width: 100%; }
ul, ol { padding-left: 20px; margin: 6px 0; }
li { margin: 2px 0; }
/* The "In one page" introduction stands out as a summary block. */
section.intro { background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb; border-radius: 8px; padding: 2px 14px 6px; margin: 10px 0 6px; }
section.intro h2 { border: none; margin-top: 12px; }
"""


def build(name):
    text = (DOCS / f"{name}.md").read_text()
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # Wrap the "In one page" section (up to the next h2) in a summary block.
    start = html.find("<h2>In one page</h2>")
    if start >= 0:
        end = html.find("<h2>", start + 5)
        html = html[:start] + '<section class="intro">' + html[start:end] + "</section>" + html[end:]
    page = DOCS / f".{name}.html"
    page.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{name.replace("_", " ").title()}</title>'
                    f"<style>{CSS}</style></head><body>{html}</body></html>")
    OUT.mkdir(exist_ok=True)
    pdf = OUT / f"{name}.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    f"--print-to-pdf={pdf}", page.as_uri()], check=True, capture_output=True)
    page.unlink()
    print(pdf.relative_to(ROOT))


if __name__ == "__main__":
    for n in sys.argv[1:] or NAMES:
        build(n)
