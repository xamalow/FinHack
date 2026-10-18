"""Deploy the simulated site to Vercel (production).

Usage: python site-demo/deploy.py [--gateway https://gateway.example]

Needs VERCEL_TOKEN in the repo .env (or the environment) and Node. The
Vercel CLI is installed once into site-demo/.vercel-cli (git-ignored).
Deploys from a temporary copy holding only public/, vercel.json and the
.vercel project link: outside the git repo, Vercel does not attach commit
metadata (which blocks the deploy for unknown commit authors), and
truth.json and the build scripts are never uploaded.
--gateway sets where /.well-known/ai-data.json is proxied to.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
ENV_FILE = ROOT.parent / ".env"
PROJECT = "velstrand-research"
CLI_DIR = ROOT / ".vercel-cli"
WINDOWS = os.name == "nt"


def token():
    if os.environ.get("VERCEL_TOKEN"):
        return os.environ["VERCEL_TOKEN"]
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERCEL_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("VERCEL_TOKEN missing from .env")


def vercel_cli():
    exe = CLI_DIR / "node_modules" / ".bin" / ("vercel.cmd" if WINDOWS else "vercel")
    if not exe.exists():
        subprocess.run(["npm", "install", "--prefix", str(CLI_DIR), "vercel@64.5.0", "--no-audit", "--no-fund"],
                       check=True, shell=WINDOWS)
    return [str(exe)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway", help="public gateway URL serving /.well-known/ai-data.json")
    args = ap.parse_args()

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    if args.gateway:
        config["rewrites"] = [{
            "source": "/.well-known/ai-data.json",
            "destination": args.gateway.rstrip("/") + "/.well-known/ai-data.json",
        }]
        (ROOT / "vercel.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    vercel = vercel_cli()
    env = dict(os.environ, VERCEL_TOKEN=token())  # the CLI reads it, so it never shows in a command line
    # Windows can keep a file of the copy locked for a moment after the CLI exits.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        shutil.copytree(ROOT / "public", tmp / "public")
        shutil.copy(ROOT / "vercel.json", tmp / "vercel.json")
        if (ROOT / ".vercel").exists():
            shutil.copytree(ROOT / ".vercel", tmp / ".vercel")
        else:
            subprocess.run(vercel + ["link", "--yes", "--project", PROJECT], cwd=tmp, env=env, check=True)
        subprocess.run(vercel + ["deploy", "--prod", "--yes"], cwd=tmp, env=env, check=True)
    print(f"Deployed https://{PROJECT}.vercel.app")


if __name__ == "__main__":
    main()
