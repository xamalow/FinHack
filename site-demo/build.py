"""Build the simulated publisher website from truth.json.

Usage: python site-demo/build.py [--base-url https://velstrand-research.vercel.app]

Writes everything into site-demo/public: HTML pages, report PDFs,
sitemap.xml and robots.txt. Every figure comes from truth.json.
"""
import argparse
import html
import io
import json
import shutil
from datetime import date
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
STATIC = ROOT / "static"
DEFAULT_BASE_URL = "https://velstrand-research.vercel.app"

e = html.escape


# ---------- HTML pages ----------

def page(title, body, firm, depth=0):
    prefix = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | {e(firm['name'])}</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<div id="agent-banner" hidden></div>
<header class="site-header">
  <a class="brand" href="{prefix}index.html">{e(firm['name'])}</a>
  <nav><a href="{prefix}index.html">Research</a><a href="{prefix}about.html">About</a></nav>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  <p><strong>For AI agents.</strong> {e(firm['name'])} data can be bought by AI agents per figure, per table or per report section, paid in USDC with the x402 protocol. Agents start at <code>/.well-known/ai-data.json</code>.</p>
  <p class="disclaimer">{e(firm['name'])} is a fictional company. All company names and figures on this site are invented for a demo.</p>
</footer>
<script src="{prefix}assets/agents.js"></script>
</body>
</html>
"""


def paragraphs(ps):
    return "\n".join(f"<p>{e(p)}</p>" for p in ps)


def build_index(t):
    firm = t["firm"]
    cards = []
    for r in t["reports"]:
        a = r["article"]
        cards.append(f"""<li class="card">
  <span class="tag">{e(r['topic'])} &middot; {e(r['region'])} &middot; {e(r['period'])}</span>
  <h3><a href="articles/{a['slug']}.html">{e(a['title'])}</a></h3>
  <p>{e(a['paragraphs'][0])}</p>
  <a class="pdf" href="reports/{r['report_id']}.pdf">Full report (PDF): {e(r['title'])}</a>
</li>""")
    body = f"""<section class="hero">
  <h1>{e(firm['name'])}</h1>
  <p>{e(firm['tagline'])}</p>
</section>
<section>
  <h2>Latest research</h2>
  <ul class="cards">
{chr(10).join(cards)}
  </ul>
</section>"""
    return page("Research", body, firm)


def build_about(t):
    firm = t["firm"]
    body = f"<article><h1>About {e(firm['name'])}</h1>\n{paragraphs(firm['about'])}</article>"
    return page("About", body, firm)


def build_article(t, r):
    firm, a = t["firm"], r["article"]
    body = f"""<article>
<span class="tag">{e(r['topic'])} &middot; {e(r['region'])} &middot; {e(r['period'])}</span>
<h1>{e(a['title'])}</h1>
{paragraphs(a['paragraphs'])}
<p><a class="pdf" href="../reports/{r['report_id']}.pdf">Download the full report: {e(r['title'])}</a></p>
</article>"""
    return page(a["title"], body, firm, depth=1)


def build_simple(t, item, depth):
    body = f"<article>\n<h1>{e(item['title'])}</h1>\n{paragraphs(item['paragraphs'])}\n</article>"
    return page(item["title"], body, t["firm"], depth=depth)


# ---------- PDF reports ----------

PDF_CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #1b2430; }
h1 { font-size: 20pt; margin-bottom: 4pt; }
h2 { font-size: 14pt; margin-top: 16pt; margin-bottom: 4pt; }
p.byline { font-size: 9pt; color: #5b6573; }
table { border-collapse: collapse; margin-top: 6pt; }
th, td { border: 1px solid #c8ced6; padding: 3pt 6pt; text-align: left; }
th { background-color: #eef1f5; }
"""


def report_html(firm, r):
    parts = [
        f"<h1>{e(r['title'])}</h1>",
        f"<p class='byline'>{e(firm['name'])}, proprietary research. "
        f"Topic: {e(r['topic'])}. Region: {e(r['region'])}. Period: {e(r['period'])}.</p>",
    ]
    for s in r["sections"]:
        parts.append(f"<h2>{e(s['title'])}</h2>")
        parts.append(paragraphs(s["paragraphs"]))
        tbl = s.get("table")
        if tbl:
            head = "".join(f"<th>{e(c)}</th>" for c in tbl["columns"])
            rows = "".join(
                "<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in tbl["rows"]
            )
            parts.append(f"<table><tr>{head}</tr>{rows}</table>")
    return "\n".join(parts)


def build_pdf(firm, r, path):
    story = pymupdf.Story(html=report_html(firm, r), user_css=PDF_CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (50, 50, -50, -50)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    doc = pymupdf.open("pdf", buf.getvalue())
    doc.set_metadata({"title": r["title"], "author": firm["name"], "subject": r["topic"]})
    doc.save(path, garbage=3, deflate=True)


# ---------- main ----------

def build(base_url):
    t = json.loads((ROOT / "truth.json").read_text(encoding="utf-8"))
    base_url = base_url.rstrip("/")
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "reports").mkdir()
    (PUBLIC / "drafts").mkdir()
    shutil.copytree(STATIC, PUBLIC / "assets")

    pages = {"index.html": build_index(t), "about.html": build_about(t)}
    for r in t["reports"]:
        pages[f"articles/{r['article']['slug']}.html"] = build_article(t, r)
    pages[t["internal_notes"]["path"]] = build_simple(t, t["internal_notes"], depth=0)
    pages[t["draft"]["path"]] = build_simple(t, t["draft"], depth=1)
    for rel, content in pages.items():
        (PUBLIC / rel).write_text(content, encoding="utf-8")

    pdfs = []
    for r in t["reports"]:
        rel = f"reports/{r['report_id']}.pdf"
        build_pdf(t["firm"], r, PUBLIC / rel)
        pdfs.append(rel)

    # The internal notes page is in the sitemap on purpose: the publisher
    # exposed it by mistake and the scan must flag it. The draft is listed
    # too but disallowed in robots.txt, so a polite crawler skips it.
    today = date.today().isoformat()
    urls = "\n".join(
        f"  <url><loc>{base_url}/{rel}</loc><lastmod>{today}</lastmod></url>"
        for rel in list(pages) + pdfs
    )
    (PUBLIC / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )
    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nDisallow: /drafts/\n\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8"
    )
    print(f"Built {len(pages)} pages and {len(pdfs)} PDFs into {PUBLIC} for {base_url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    build(ap.parse_args().base_url)
