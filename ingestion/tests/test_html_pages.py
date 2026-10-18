"""HTML pages: split on h2/h3, sell data-rich sections, keep the rest free."""
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ingestion.catalog import is_data_rich, plan_items, split_html
from ingestion.crawl import CrawlResult, _parse_html, crawl

DATA_PAGE = """<html><head><title>Battery market</title></head><body>
<nav><a href="/">Home</a></nav>
<main>
<h1>European battery market 2025</h1>
<p>Our yearly view of the market, written by our analysts.</p>
<h2>Market share by manufacturer</h2>
<table>
<tr><td>Aurelion</td><td>31.4%</td></tr><tr><td>Norvik Cells</td><td>18.2%</td></tr>
<tr><td>Kestrel Power</td><td>12.7%</td></tr><tr><td>Others</td><td>37.7%</td></tr>
</table>
<h2>Outlook</h2>
<p>We expect consolidation to continue as new plants open across the region.</p>
<h2>Endnotes</h2>
<p>1. Revenue of 4,512.3 MEUR, 2,180.9 MEUR and 1,402.6 MEUR from company filings.</p>
</main></body></html>"""

ESSAY_PAGE = """<html><body><main><h1>On writing</h1>
<p>In 2004 I wrote 3 essays. Then 12 more in 2005. Footnote [7] explains why.</p>
<p>""" + "Writing is thinking. " * 40 + """</p></main></body></html>"""


def test_html_is_split_on_headings():
    doc = _parse_html("https://pub.test/market.html", DATA_PAGE.encode())
    assert doc.title == "European battery market 2025"
    assert [h for h, _ in doc.sections] == ["", "Market share by manufacturer", "Outlook", "Endnotes"]
    assert "31.4%" in dict(doc.sections)["Market share by manufacturer"]
    assert "Home" not in doc.text  # navigation is not content


def test_only_data_sections_are_sold():
    doc = _parse_html("https://pub.test/market.html", DATA_PAGE.encode())
    parts = split_html(doc)
    assert [(s, sellable) for s, _, sellable in parts] == [("Market share by manufacturer", True), ("Overview", False)]
    overview = parts[-1][1]
    assert "Outlook" in overview and "Endnotes" in overview  # boilerplate stays free


def test_essays_and_boilerplate_are_not_data():
    assert not is_data_rich("", _parse_html("https://pub.test/e.html", ESSAY_PAGE.encode()).text)
    assert not is_data_rich("Cite this work", "Revenue 4,512.3 MEUR, 2,180.9 MEUR, 1,402.6 MEUR")
    assert not is_data_rich("Media enquiries", "Call +44 20 7946 0958 or +44 20 7946 0123, fax 0207 946 0999")
    assert is_data_rich("Prices", "Lithium 12,450 USD/t, cobalt 33,100 USD/t, nickel 16,870 USD/t")


def test_plan_items_for_a_standalone_data_page():
    doc = _parse_html("https://pub.test/insights/market.html", DATA_PAGE.encode())
    planned = plan_items(CrawlResult("https://pub.test/", [doc], [], []))
    by_id = {p["content_id"]: p for p in planned}
    assert set(by_id) == {"page_insights_market#s1", "page_insights_market#overview"}
    assert by_id["page_insights_market#s1"]["kind"] == "page_section"
    assert by_id["page_insights_market#overview"]["kind"] == "page"


def test_long_page_without_main_is_kept_short_one_skipped():
    long_page = "<html><body><h1>Notes on cells</h1><p>" + "Cell chemistry matters a lot. " * 60 + "</p></body></html>"
    short_page = "<html><body><h1>Hello</h1><p>Short.</p></body></html>"
    docs = [_parse_html("https://pub.test/cells.html", long_page.encode()),
            _parse_html("https://pub.test/hello.html", short_page.encode())]
    planned = plan_items(CrawlResult("https://pub.test/", docs, [], []))
    assert [p["content_id"] for p in planned] == ["page_cells#s1"]


@pytest.fixture
def site_without_sitemap(tmp_path):
    (tmp_path / "index.html").write_text('<html><body><a href="/a.html">A</a></body></html>')
    (tmp_path / "a.html").write_text('<html><body><main><h1>A</h1><a href="/b.html">B</a></main></body></html>')
    (tmp_path / "b.html").write_text(DATA_PAGE)
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_crawl_follows_links_when_there_is_no_sitemap(site_without_sitemap):
    result = crawl(site_without_sitemap)
    found = {d.url.rsplit("/", 1)[-1] for d in result.documents}
    assert {"a.html", "b.html"} <= found  # b.html is two clicks away from the home page
