# P1, publisher data

Simulated publisher site (`/site-demo`), crawler, catalog, leak filter and the `/publisher/*` scan endpoints.

## Run it

```bash
pip install -r ingestion/requirements.txt
python site-demo/build.py                  # regenerate the site from truth.json (only after editing it)
python site-demo/serve.py --port 8001      # simulated site on http://localhost:8001
python -m ingestion.dev_server --port 8010 # P1 endpoints alone, until the gateway registers the router
python -m pytest ingestion/tests -q
```

`INGESTION_LLM=off` skips the LLM and uses heuristic metadata. `INGESTION_MODEL` overrides the model (default `claude-opus-5-5`).
`python -m ingestion.dev_server --mock` loads the hand-written catalog (`ingestion/mock_catalog.json`) without a scan.

## For P2 (gateway, Sales agent)

- Register the router: `from gateway.routers.publisher_scan import router` then `app.include_router(router)`.
- `ingestion.store.get_catalog(status=None)` returns metadata only (section 6.2 fields), never raw text.
- `ingestion.leak_filter.contains_paid_figures(text) -> bool`. `find_paid_figures(text)` returns the matching numbers, useful in event payloads.
- `suggested_tier` is `null` for free and excluded items.
- `ingestion/compat.py` imports `shared.events.log_event` and `shared.db.get_connection` once they exist, otherwise falls back to a local SQLite file and printed events. If `shared.db` exposes a different name, tell P1.
- Please add the `scan_failed` event type (actor `publisher`) to `/shared/events.py`.

## For P3 (payments)

`ingestion.store.get_content(content_ids) -> {content_id: raw_text}`. It raises `ContentNotAvailable` if any id is unknown or excluded, so an excluded item can never be delivered.

## For P4 (frontend)

- `POST /publisher/scan {"url": "..."}` returns 202 at once. Progress arrives as events: `scan_started`, `scan_extracting` (one per document), `scan_indexing` (one per catalog item), `scan_ready` (summary in the payload).
- `GET /publisher/catalog` returns the list of items.
- `PATCH /publisher/catalog/{content_id} {"status": "sellable" | "free" | "excluded"}`. The `#` in ids must be URL-encoded (`rpt_battery_2025%23s2`). An item flagged internal returns 409 if you try to make it sellable or free.
- The simulated site shows a "Now selling data to AI agents" banner as soon as `/.well-known/ai-data.json` answers, which happens after Activate.

## The simulated site

Velstrand Research, a fictional firm (company names and figures are invented). 4 free articles, 4 PDF reports of 4 sections each, an "Internal notes" page listed in the sitemap by mistake (the scan flags it), and a draft page blocked by `robots.txt` (the scan skips it). All figures come from `site-demo/truth.json` and are precise (31.4, 17,340) so any leak is obvious.

Vercel: deploy `site-demo` as a static project and replace `GATEWAY_PUBLIC_URL` in `site-demo/vercel.json`. Rebuild with `--base-url https://<vercel-url>` so the sitemap points to the right host.
