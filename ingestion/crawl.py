"""Crawler for a publisher website.

crawl(base_url) reads robots.txt and sitemap.xml, fetches every allowed
same-host URL, and extracts text from HTML pages and PDF reports.
Everything fetched is untrusted data: it is only parsed, never executed
or followed as instructions.
"""
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import pymupdf
from bs4 import BeautifulSoup

USER_AGENT = "AgentDataCrawler/0.1 (+publisher onboarding scan)"
MAX_URLS = 200
MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 10.0
PDF_TEXT_FLAGS = pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES


@dataclass
class Document:
    url: str
    kind: str                      # "html" or "pdf"
    title: str
    text: str
    links: list = field(default_factory=list)   # absolute same-host links (HTML only)
    content_links: list = field(default_factory=list)  # same-host links inside the article or main body
    lines: list = field(default_factory=list)   # [(font_size, bold, text)] (PDF only)
    has_article: bool = False      # HTML page with an <article> or <main> body


@dataclass
class CrawlResult:
    base_url: str
    documents: list
    blocked_by_robots: list
    errors: list


def _clean(text):
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"[ \t]+", " ", text).strip()


def _same_host(url, base):
    return urlparse(url).netloc == urlparse(base).netloc


def _robots(client, base_url):
    rp = RobotFileParser()
    try:
        res = client.get(urljoin(base_url, "/robots.txt"))
        rp.parse(res.text.splitlines() if res.status_code == 200 else [])
    except httpx.HTTPError:
        rp.parse([])
    return rp


def _sitemap_urls(client, base_url, robots):
    sitemaps = robots.site_maps() or [urljoin(base_url, "/sitemap.xml")]
    urls, seen = [], set()
    while sitemaps and len(urls) < MAX_URLS:
        sm = sitemaps.pop(0)
        if sm in seen or not _same_host(sm, base_url):
            continue
        seen.add(sm)
        try:
            res = client.get(sm)
            res.raise_for_status()
            root = ET.fromstring(res.content)
        except (httpx.HTTPError, ET.ParseError):
            continue
        for loc in root.iter():
            if not loc.tag.endswith("loc") or not loc.text:
                continue
            url = loc.text.strip()
            if root.tag.endswith("sitemapindex"):
                sitemaps.append(url)
            elif url not in urls:
                urls.append(url)
    return urls


def _parse_html(url, body):
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    def same_host_links(node):
        found = []
        for a in node.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#", 1)[0]
            if _same_host(href, url) and href not in found:
                found.append(href)
        return found

    links = same_host_links(soup)
    for tag in soup(["nav", "header", "footer"]):
        tag.decompose()
    body_tag = soup.find("article") or soup.find("main")
    content_links = same_host_links(body_tag or soup)
    h1 = (body_tag or soup).find("h1")
    title = _clean(h1.get_text(" ") if h1 else (soup.title.string if soup.title else url))
    text = _clean((body_tag or soup.body or soup).get_text("\n"))
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return Document(url=url, kind="html", title=title, text=text, links=links, content_links=content_links,
                    has_article=body_tag is not None)


def _parse_pdf(url, body):
    doc = pymupdf.open(stream=io.BytesIO(body), filetype="pdf")
    lines = []
    for page in doc:
        for block in page.get_text("dict", flags=PDF_TEXT_FLAGS)["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = _clean(" ".join(s["text"] for s in spans))
                size = round(max(s["size"] for s in spans), 1)
                bold = all(s["flags"] & 16 for s in spans)
                lines.append((size, bold, text))
    title = _clean(doc.metadata.get("title") or "") or (lines[0][2] if lines else url)
    return Document(url=url, kind="pdf", title=title, text="\n".join(t for _, _, t in lines), lines=lines)


def _fetch(client, url):
    with client.stream("GET", url) as res:
        res.raise_for_status()
        ctype = res.headers.get("content-type", "").split(";")[0].strip().lower()
        chunks, size = [], 0
        for chunk in res.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError(f"{url} is larger than {MAX_BYTES} bytes")
            chunks.append(chunk)
    return ctype, b"".join(chunks)


def crawl(base_url, on_document=None):
    """Crawl a site. on_document(doc) is called after each document is
    extracted, so the caller can emit live events."""
    base_url = base_url.rstrip("/") + "/"
    docs, blocked, errors = [], [], []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        robots = _robots(client, base_url)
        urls = _sitemap_urls(client, base_url, robots)
        if not urls:
            # No sitemap: fall back to the links on the home page.
            urls = [base_url]
        queue, done = list(urls), set()
        while queue and len(done) < MAX_URLS:
            url = queue.pop(0)
            if url in done or not _same_host(url, base_url):
                continue
            done.add(url)
            if not robots.can_fetch(USER_AGENT, url):
                blocked.append(url)
                continue
            try:
                ctype, body = _fetch(client, url)
                if ctype == "application/pdf" or url.lower().endswith(".pdf"):
                    doc = _parse_pdf(url, body)
                elif ctype in ("text/html", "application/xhtml+xml"):
                    doc = _parse_html(url, body)
                else:
                    continue
            except Exception as err:  # one bad document must not stop the scan
                errors.append({"url": url, "error": str(err)[:200]})
                continue
            docs.append(doc)
            if url == base_url and len(urls) == 1:
                queue.extend(link for link in doc.links if link not in done)
            if on_document:
                on_document(doc)
    return CrawlResult(base_url=base_url, documents=docs, blocked_by_robots=blocked, errors=errors)
