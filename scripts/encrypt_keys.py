"""Move private keys out of an env file: encrypted keystore files + passwords in the macOS Keychain.

For each key (BUYER_PRIVATE_KEY_*, MCP_BUYER_PRIVATE_KEY, PUBLISHER_SIGNING_KEY found in the env file):
- a random password is stored in the Keychain (service "doubloon", account = the variable name);
- the key is written to keys/<NAME>.json as a Web3 Secret Storage v3 keystore (scrypt), mode 600;
- with --rewrite-env, the plaintext line is replaced by NAME_KEYSTORE=keys/<NAME>.json
  (a backup of the env file is kept next to it, git-ignored, delete it once you checked everything runs).

shared/keys.load_private_key() then reads the keystore and asks the Keychain for the password.
Nothing secret is printed.

    python scripts/encrypt_keys.py                       # dry run: lists what would move
    python scripts/encrypt_keys.py --apply               # keystores + Keychain, env file untouched
    python scripts/encrypt_keys.py --apply --rewrite-env # also removes the plaintext keys from the env file
"""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from eth_account import Account

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared.keys import KEYCHAIN_SERVICE  # noqa: E402

KEY_NAME = re.compile(r"^(BUYER_PRIVATE_KEY_\d+|MCP_BUYER_PRIVATE_KEY|PUBLISHER_SIGNING_KEY)$")


def keychain_store(name, password):
    # -U updates an existing item. The password is passed as an argument, visible to local process listing
    # for the duration of the call only.
    subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", name, "-w", password],
                   check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--out", default=str(ROOT / "keys"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rewrite-env", action="store_true")
    parser.add_argument("--password-store", choices=["keychain", "none"], default="keychain",
                        help="none: use KEYSTORE_PASSWORD for every keystore (machines without a Keychain)")
    args = parser.parse_args()

    env_file, out = Path(args.env_file), Path(args.out)
    lines = env_file.read_text().splitlines()
    found = [(i, *line.split("=", 1)) for i, line in enumerate(lines)
             if "=" in line and not line.lstrip().startswith("#") and KEY_NAME.match(line.split("=", 1)[0].strip())]
    found = [(i, k.strip(), v.strip()) for i, k, v in found if v.strip()]
    if not found:
        print("No plaintext private key in", env_file)
        return
    for _, name, value in found:
        print(f"{name}: {Account.from_key(value).address} -> {out / (name + '.json')}")
    if not args.apply:
        print("Dry run. Add --apply to encrypt.")
        return

    out.mkdir(mode=0o700, exist_ok=True)
    for i, name, value in found:
        if args.password_store == "keychain":
            password = secrets.token_urlsafe(32)
            keychain_store(name, password)
        else:
            password = os.environ["KEYSTORE_PASSWORD"]
        keystore = Account.encrypt(value, password)
        path = out / f"{name}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(keystore, f)
        assert Account.decrypt(json.loads(path.read_text()), password) == Account.from_key(value).key
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        lines[i] = f"{name}_KEYSTORE={rel}"
    print(f"{len(found)} keystore(s) written to {out}")

    if args.rewrite_env:
        backup = env_file.with_name(env_file.name + f".bak-{int(time.time())}")
        shutil.copy2(env_file, backup)
        os.chmod(backup, 0o600)
        env_file.write_text("\n".join(lines) + "\n")
        print(f"{env_file} rewritten (backup {backup.name}, delete it once everything runs)")


if __name__ == "__main__":
    main()
