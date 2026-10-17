import importlib.util
import os
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Must be set before ingestion.compat is imported.
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["INGESTION_LLM"] = "off"


@pytest.fixture(scope="session")
def site_url():
    """Serve site-demo/public on a free local port for the whole session."""
    spec = importlib.util.spec_from_file_location("site_serve", ROOT / "site-demo" / "serve.py")
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)
    server = serve.DualStackServer(("::", 0), partial(serve.SiteHandler, directory=str(serve.PUBLIC)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def scanned(site_url):
    from ingestion.catalog import run_scan
    return run_scan(site_url)
