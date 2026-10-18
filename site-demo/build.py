"""Build the simulated publisher website from truth.json.

Usage: python site-demo/build.py [--base-url https://velstrand-research.vercel.app]

Writes everything into site-demo/public: HTML pages, report PDFs, blurred
report previews, sitemap.xml and robots.txt. Every figure comes from
truth.json.

Humans who click a report land on a product page (reports/<id>.html) that
shows the first page of the PDF blurred under a lock. The PDFs themselves
stay in the sitemap so the onboarding crawler can read them.
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

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap")

LICENSES = [
    ("Single user", "One named user, PDF report", "€2,450"),
    ("Team", "Up to five users, PDF and data tables", "€3,900"),
    ("Enterprise", "Company-wide use and an analyst briefing", "€6,500"),
]
TOPIC_LABELS = {"batteries": "Batteries", "lithium": "Lithium", "gigafactories": "Gigafactories", "sodium-ion": "Sodium-ion"}
COVERAGE_LABELS = {
    "Manufacturer": ("Manufacturers", "Company level"), "Producer": ("Producers", "Producer level"),
    "Country": ("Countries", "Country level"), "Site": ("Sites", "Site level"),
    "Chemistry": ("Chemistries", "By chemistry"), "Segment": ("Segments", "By segment"),
    "Year": (None, "Annual time series"),
}

LOGO = ('<svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="currentColor"/>'
        '<path d="M8 9l8 15 8-15" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M13 9h6" stroke="#5fd0c8" stroke-width="3" stroke-linecap="round"/></svg>')
LOCK = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10.5" width="16" height="11" rx="2.5" fill="currentColor"/>'
        '<path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="2.2"/>'
        '<circle cx="12" cy="16" r="1.6" fill="#fff"/></svg>')
CHECK = ('<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 10.5l3.2 3.2L15 7" fill="none" stroke="currentColor" '
         'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

e = html.escape


# ---------- layout ----------

def page(title, body, t, depth=0, description=""):
    p = "../" * depth
    firm = t["firm"]
    report_links = "".join(
        f'<li><a href="{p}reports/{r["report_id"]}.html">{e(TOPIC_LABELS.get(r["topic"], r["topic"]))}</a></li>'
        for r in t["reports"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | {e(firm['name'])}</title>
<meta name="description" content="{e(description or firm['tagline'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{p}assets/style.css">
</head>
<body>
<div id="agent-banner" hidden></div>
<div class="topbar"><div class="wrap topbar-inner">
  <span>{e(firm['tagline'])}</span>
  <a href="{p}about.html#agents">AI agents can buy our data per figure, in USDC</a>
</div></div>
<header class="site-header"><div class="wrap header-inner">
  <a class="brand" href="{p}index.html">{LOGO}<span>Velstrand <b>Research</b></span></a>
  <nav class="main-nav">
    <a href="{p}index.html#reports">Reports</a>
    <a href="{p}index.html#insights">Insights</a>
    <a href="{p}about.html">About</a>
  </nav>
  <a class="btn btn-outline btn-sm" href="{p}about.html#contact">Talk to an analyst</a>
</div></header>
<main>
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <a class="brand brand-light" href="{p}index.html">{LOGO}<span>Velstrand <b>Research</b></span></a>
      <p>{e(firm['tagline'])}.</p>
    </div>
    <div><h4>Research</h4><ul>{report_links}</ul></div>
    <div><h4>Company</h4><ul>
      <li><a href="{p}about.html">About us</a></li>
      <li><a href="{p}index.html#insights">Insights</a></li>
      <li><a href="{p}about.html#contact">Contact</a></li>
    </ul></div>
    <div><h4>For AI agents</h4>
      <p>{e(firm['name'])} data can be bought by AI agents per figure, per table or per report section, paid in USDC with the x402 protocol. Agents start at <code>/.well-known/ai-data.json</code>.</p>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span>&copy; {date.today().year} {e(firm['name'])}</span>
    <span class="disclaimer">{e(firm['name'])} is a fictional company. All company names and figures on this site are invented for a demo.</span>
  </div>
</footer>
<div class="toast" role="status" aria-live="polite" hidden></div>
<script src="{p}assets/agents.js"></script>
<script src="{p}assets/site.js"></script>
</body>
</html>
"""


def paragraphs(ps):
    return "\n".join(f"<p>{e(x)}</p>" for x in ps)


def topic_label(r):
    return TOPIC_LABELS.get(r["topic"], r["topic"].title())


def breadcrumb(items):
    parts = []
    for label, href in items:
        parts.append(f'<a href="{href}">{e(label)}</a>' if href else f"<span>{e(label)}</span>")
    return f'<nav class="breadcrumb" aria-label="Breadcrumb">{" <span class=sep>/</span> ".join(parts)}</nav>'


def cover(r, small=False):
    return f"""<div class="cover topic-{e(r['topic'])}{' cover-sm' if small else ''}">
  <span class="cover-topic">{e(topic_label(r))}</span>
  <span class="cover-title">{e(r['title'])}</span>
  <span class="cover-foot">Velstrand Research &middot; PDF report</span>
</div>"""


def coverage(r):
    """[(label, sorted names)] and granularity labels, from the first column of each table."""
    groups, granularity = {}, []
    for s in r["sections"]:
        tbl = s.get("table")
        if not tbl:
            continue
        head = tbl["columns"][0]
        label, gran = COVERAGE_LABELS.get(head, (head + "s", head))
        if gran not in granularity:
            granularity.append(gran)
        if label:
            names = {row[0] for row in tbl["rows"] if row[0].lower() != "others"}
            groups.setdefault(label, set()).update(names)
    return [(k, sorted(v)) for k, v in groups.items()], granularity


# ---------- pages ----------

def build_index(t):
    cards = []
    for r in t["reports"]:
        cards.append(f"""<a class="report-card" href="reports/{r['report_id']}.html">
  {cover(r)}
  <div class="report-card-body">
    <span class="meta">{e(r['region'])} &middot; {e(r['period'])} &middot; {len(r['sections'])} sections</span>
    <p>{e(r['article']['paragraphs'][0])}</p>
    <span class="card-foot"><span>Published {e(r['published'])}</span><span class="link-arrow">View report</span></span>
  </div>
</a>""")
    insights = []
    for r in t["reports"]:
        a = r["article"]
        insights.append(f"""<a class="insight" href="articles/{a['slug']}.html">
  <span class="tag topic-text-{e(r['topic'])}">{e(topic_label(r))}</span>
  <h3>{e(a['title'])}</h3>
  <p>{e(a['paragraphs'][1])}</p>
  <span class="link-arrow">Read the analysis</span>
</a>""")
    body = f"""<section class="hero"><div class="wrap hero-inner">
  <div class="hero-copy">
    <p class="eyebrow">Battery value chain intelligence</p>
    <h1>Proprietary data on Europe's battery industry, from lithium to gigafactories.</h1>
    <p class="lede">Market shares, prices, costs and capacity, built bottom-up from plant-level data and expert interviews. Trusted by investors, automakers and utilities.</p>
    <div class="hero-actions">
      <a class="btn btn-cta" href="#reports">Browse reports</a>
      <a class="btn btn-light" href="about.html#agents">Data for AI agents</a>
    </div>
  </div>
  <ul class="hero-panel">
    <li><span class="dot topic-batteries"></span><div><strong>Cell manufacturing</strong><span>Market shares, output, utilisation</span></div></li>
    <li><span class="dot topic-lithium"></span><div><strong>Lithium supply</strong><span>Spot prices and producer cost curves</span></div></li>
    <li><span class="dot topic-gigafactories"></span><div><strong>Gigafactory pipeline</strong><span>Operational and planned capacity</span></div></li>
    <li><span class="dot topic-sodium-ion"></span><div><strong>Next-generation chemistries</strong><span>Sodium-ion costs and adoption</span></div></li>
  </ul>
</div></section>
<section class="trust-strip"><div class="wrap trust-inner">
  <span>Plant-level shipment data</span><span>Customs records</span><span>Expert interviews</span><span>Bottom-up cost models</span>
</div></section>
<section id="reports" class="section"><div class="wrap">
  <div class="section-head">
    <div><p class="eyebrow">Flagship research</p><h2>Latest reports</h2></div>
    <p>Each report is sold as a licensed PDF. Free summaries are available in our insights.</p>
  </div>
  <div class="report-grid">
{chr(10).join(cards)}
  </div>
</div></section>
<section id="insights" class="section section-wash"><div class="wrap">
  <div class="section-head">
    <div><p class="eyebrow">Free analysis</p><h2>Insights</h2></div>
    <p>Short reads from our analysts, without the proprietary numbers.</p>
  </div>
  <div class="insight-grid">
{chr(10).join(insights)}
  </div>
</div></section>
<section class="section"><div class="wrap">
  <div class="agents-box">
    <div>
      <p class="eyebrow eyebrow-light">New</p>
      <h2>Built for AI agents too</h2>
      <p>Your agent does not need a full report to answer one question. It can discover our catalog, prove its identity with a wallet signature and buy exactly the figure, table or section it needs, paid instantly in USDC.</p>
    </div>
    <ol class="agent-steps">
      <li><strong>Discover</strong><span>Read <code>/.well-known/ai-data.json</code></span></li>
      <li><strong>Verify</strong><span>Sign a challenge with the agent wallet</span></li>
      <li><strong>Pay per answer</strong><span>Settle in USDC with x402, get the data</span></li>
    </ol>
  </div>
</div></section>"""
    return page("Research on the European battery value chain", body, t)


def build_about(t):
    firm = t["firm"]
    body = f"""<div class="wrap narrow">
{breadcrumb([("Home", "index.html"), ("About", None)])}
<article class="prose">
  <h1>About {e(firm['name'])}</h1>
  {paragraphs(firm['about'][:2])}
  <h2>Our approach</h2>
  <div class="pillars">
    <div><h3>Plant-level data</h3><p>We track shipments site by site instead of relying on company guidance.</p></div>
    <div><h3>Primary research</h3><p>Every estimate is checked with plant managers, traders and suppliers.</p></div>
    <div><h3>Transparent methods</h3><p>Each report ends with a methodology section that explains our sources.</p></div>
  </div>
  <h2 id="agents">For AI agents</h2>
  <p>Our data is also sold directly to AI agents. An agent reads our manifest at <code>/.well-known/ai-data.json</code>, verifies its identity with a wallet signature, then buys a single figure, a small table or a full section, paid in USDC with the x402 protocol.</p>
  <h2 id="contact">Contact</h2>
  <p>Questions about a report or a custom study: <a href="mailto:research@velstrand.example">research@velstrand.example</a>.</p>
  <p class="note">{e(firm['about'][2])}</p>
</article>
</div>"""
    return page("About", body, t)


def build_article(t, r):
    a = r["article"]
    body = f"""<div class="wrap">
{breadcrumb([("Home", "../index.html"), ("Insights", "../index.html#insights"), (topic_label(r), None)])}
<div class="article-layout">
  <article class="prose">
    <span class="tag topic-text-{e(r['topic'])}">{e(topic_label(r))} &middot; {e(r['region'])} &middot; {e(r['period'])}</span>
    <h1>{e(a['title'])}</h1>
    <p class="byline">By Velstrand Research analysts &middot; {e(r['published'])}</p>
    {paragraphs(a['paragraphs'])}
    <div class="article-cta">
      <div><strong>Get the full data</strong><span>{e(r['title'])}</span></div>
      <a class="btn btn-cta" href="../reports/{r['report_id']}.html">View the full report</a>
    </div>
  </article>
  <aside class="article-side">
    <div class="side-card">
      <p class="eyebrow">Full report</p>
      <a class="mini-preview" href="../reports/{r['report_id']}.html">
        <img src="../reports/previews/{r['report_id']}-head.png" alt="First page of {e(r['title'])}">
        <span class="mini-blur"><img src="../reports/previews/{r['report_id']}-body.png" alt=""></span>
        <span class="mini-lock">{LOCK}</span>
      </a>
      <h3>{e(r['title'])}</h3>
      <a class="btn btn-cta btn-block" href="../reports/{r['report_id']}.html">Unlock the report</a>
    </div>
  </aside>
</div>
</div>"""
    return page(a["title"], body, t, depth=1, description=a["paragraphs"][0])


def build_report(t, r, pages):
    covered, granularity = coverage(r)
    sections = r["sections"]
    toc = "".join(
        f'<li><span class="toc-num">{i}</span><span class="toc-title">{e(s["title"])}</span>'
        f'{"<span class=badge>Data table</span>" if s.get("table") else ""}<span class="toc-lock">{LOCK}</span></li>'
        for i, s in enumerate(sections, 1)
    )
    questions = "".join(f"<li>{CHECK}<span>{e(q)}</span></li>" for q in r["questions"])
    scope = "".join(f"<dt>{e(label)}</dt><dd>{e(', '.join(names))}</dd>" for label, names in covered)
    licenses = "".join(
        f"""<label class="license"><input type="radio" name="license" value="{e(name)}"{' checked' if i == 0 else ''}>
  <span class="license-text"><strong>{e(name)}</strong><span>{e(desc)}</span></span><span class="price">{e(price)}</span></label>"""
        for i, (name, desc, price) in enumerate(LICENSES)
    )
    related = "".join(
        f'<a class="related" href="{o["report_id"]}.html">{cover(o, small=True)}<span>Published {e(o["published"])}</span></a>'
        for o in t["reports"] if o["report_id"] != r["report_id"]
    )
    body = f"""<div class="wrap">
{breadcrumb([("Home", "../index.html"), ("Reports", "../index.html#reports"), (topic_label(r), None)])}
<div class="report-layout">
  <div class="report-main">
    <header class="report-head">
      <span class="tag topic-text-{e(r['topic'])}">{e(topic_label(r))}</span>
      <h1>{e(r['title'])}</h1>
      <p class="lede">{e(r['article']['paragraphs'][0])}</p>
      <ul class="chips">
        <li>PDF report</li><li>{pages} page{'s' if pages > 1 else ''}</li><li>{len(sections)} sections</li><li>Published {e(r['published'])}</li>
      </ul>
    </header>

    <section class="snapshot">
      <h2>Report overview</h2>
      <dl>
        <div><dt>Study period</dt><dd>{e(r['period'])}</dd></div>
        <div><dt>Region</dt><dd>{e(r['region'])}</dd></div>
        <div><dt>Granularity</dt><dd>{e(', '.join(granularity) or 'Narrative')}</dd></div>
        <div><dt>Sources</dt><dd>Plant data, interviews</dd></div>
        <div><dt>Format</dt><dd>PDF with data tables</dd></div>
        <div><dt>Licence</dt><dd>Internal use only</dd></div>
      </dl>
    </section>

    <section class="preview" aria-label="Report preview">
      <div class="preview-doc">
        <img class="preview-head" src="previews/{r['report_id']}-head.png" alt="First page of {e(r['title'])}">
        <div class="preview-body"><img src="previews/{r['report_id']}-body.png" alt="" aria-hidden="true"></div>
        <div class="lock-overlay">
          <div class="lock-card">
            <span class="lock-icon">{LOCK}</span>
            <h3>This report is locked</h3>
            <p>Buy a licence to unlock all {len(sections)} sections, every data table and the full methodology.</p>
            <button type="button" class="btn btn-cta js-buy">Buy the full report</button>
            <p class="fine">Need a single figure? <a href="#agent-card">Buy it as an AI agent</a></p>
          </div>
        </div>
      </div>
    </section>

    <section class="block">
      <h2>Key questions answered</h2>
      <ul class="checks">{questions}</ul>
    </section>

    <section class="block">
      <h2>Table of contents</h2>
      <ol class="toc">{toc}</ol>
    </section>

    <section class="block">
      <h2>Scope of the report</h2>
      <dl class="scope">{scope}</dl>
      {paragraphs(r['article']['paragraphs'][1:])}
    </section>
  </div>

  <aside class="report-side">
    <div class="buy-card">
      <h3>Purchase this report</h3>
      <form class="licenses" onsubmit="return false">{licenses}</form>
      <button type="button" class="btn btn-cta btn-block js-buy">Buy now</button>
      <button type="button" class="btn btn-outline btn-block js-buy">Request a free sample</button>
      <ul class="assurances">
        <li>{CHECK}<span>Instant PDF delivery</span></li>
        <li>{CHECK}<span>Secure payment</span></li>
        <li>{CHECK}<span>Analyst support included</span></li>
      </ul>
    </div>
    <div class="agent-card" id="agent-card">
      <span class="tag tag-light">For AI agents</span>
      <h4>Need one figure, not the whole report?</h4>
      <p>AI agents can buy a single figure, a small table or one section, paid in USDC with x402.</p>
      <code>/.well-known/ai-data.json</code>
    </div>
  </aside>
</div>

<section class="related-wrap">
  <h2>Related reports</h2>
  <div class="related-grid">{related}</div>
</section>
</div>"""
    return page(r["title"], body, t, depth=1, description=r["article"]["paragraphs"][0])


def build_simple(t, item, depth, badge=None):
    home = "../" * depth + "index.html"
    badge_html = f'<span class="badge badge-red">{e(badge)}</span>' if badge else ""
    body = f"""<div class="wrap narrow">
{breadcrumb([("Home", home), (item['title'], None)])}
<article class="prose">
  {badge_html}
  <h1>{e(item['title'])}</h1>
  {paragraphs(item['paragraphs'])}
</article>
</div>"""
    return page(item["title"], body, t, depth=depth)


# ---------- PDF reports and previews ----------

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


def build_previews(r, pdf_path, out_dir):
    """Two images of the first page: the title area, sharp, and the rest,
    rendered at a resolution so low that no figure can be read back, even
    by removing the CSS blur. Returns the page count."""
    doc = pymupdf.open(pdf_path)
    first = doc[0]
    rect = first.rect
    hits = first.search_for(r["sections"][0]["title"])
    split = (hits[0].y0 - 10) if hits else rect.height * 0.22
    head = first.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=pymupdf.Rect(0, 20, rect.width, split))
    head.save(out_dir / f"{r['report_id']}-head.png")
    body = first.get_pixmap(matrix=pymupdf.Matrix(0.22, 0.22), clip=pymupdf.Rect(0, split, rect.width, rect.height - 40))
    body.save(out_dir / f"{r['report_id']}-body.png")
    return doc.page_count


# ---------- main ----------

def build(base_url):
    t = json.loads((ROOT / "truth.json").read_text(encoding="utf-8"))
    base_url = base_url.rstrip("/")
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    for sub in ("articles", "reports/previews", "drafts"):
        (PUBLIC / sub).mkdir(parents=True)
    shutil.copytree(STATIC, PUBLIC / "assets")

    pdfs, page_counts = [], {}
    for r in t["reports"]:
        rel = f"reports/{r['report_id']}.pdf"
        build_pdf(t["firm"], r, PUBLIC / rel)
        page_counts[r["report_id"]] = build_previews(r, PUBLIC / rel, PUBLIC / "reports" / "previews")
        pdfs.append(rel)

    pages = {"index.html": build_index(t), "about.html": build_about(t)}
    for r in t["reports"]:
        pages[f"articles/{r['article']['slug']}.html"] = build_article(t, r)
    pages[t["internal_notes"]["path"]] = build_simple(t, t["internal_notes"], depth=0, badge="Internal")
    pages[t["draft"]["path"]] = build_simple(t, t["draft"], depth=1, badge="Draft")
    product_pages = {f"reports/{r['report_id']}.html": build_report(t, r, page_counts[r["report_id"]]) for r in t["reports"]}
    for rel, content in {**pages, **product_pages}.items():
        (PUBLIC / rel).write_text(content, encoding="utf-8")

    # The sitemap lists the PDFs (the crawler reads them) but not the product
    # pages. The internal notes page is in it on purpose: the publisher exposed
    # it by mistake and the scan must flag it. The draft is listed too but
    # disallowed in robots.txt, so a polite crawler skips it.
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
    print(f"Built {len(pages) + len(product_pages)} pages and {len(pdfs)} PDFs into {PUBLIC} for {base_url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    build(ap.parse_args().base_url)
