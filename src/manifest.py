"""
Shared helper: download a file and record it in docs/raw_data_manifest.csv.

Every scripted download goes through here, so each raw file has a download
date and a SHA-256 checksum (see DECISIONS.md D-013).
"""
import csv
import datetime as dt
import hashlib
from pathlib import Path

import requests

import config

MANIFEST = config.ROOT / "docs" / "raw_data_manifest.csv"


def record(path: Path, content: bytes) -> None:
    """Add/replace this file's row in the manifest."""
    rows = list(csv.DictReader(MANIFEST.open())) if MANIFEST.exists() else []
    rows = [r for r in rows if r["file"] != path.name]
    rows.append({"file": path.name, "downloaded": dt.date.today().isoformat(),
                 "sha256": hashlib.sha256(content).hexdigest()})
    with MANIFEST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "downloaded", "sha256"])
        writer.writeheader()
        writer.writerows(rows)


def download(url: str, out: Path, params: dict | None = None) -> bytes:
    """Download url -> out, fail on HTTP errors, and record it in the manifest."""
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()  # never save an error page as if it were data
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    record(out, resp.content)
    print(f"Saved {out.relative_to(config.ROOT)} ({len(resp.content) / 1e6:.1f} MB); manifest updated")
    return resp.content
