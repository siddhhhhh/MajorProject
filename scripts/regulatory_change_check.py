#!/usr/bin/env python3
"""Regulatory framework change-detection script.

Fetches each framework's `source_url` from data/regulatory_frameworks.json,
hashes the relevant content, and compares against the last known hash
stored in data/regulatory_frameworks_hashes.json.

Output:
- Console: human-readable diff of CHANGED / NEW / UNREACHABLE / UNCHANGED
- Exit code: 0 if nothing changed, 1 if at least one framework changed,
  2 if at least one source was unreachable (operational signal)
- Side effect: refreshes the hash file when --commit is passed

Run cadence: monthly (or before any demo / report batch run).
LLM auto-drafting of rule updates is intentionally NOT included — the
hash mismatch is the trigger; humans review and edit
data/regulatory_frameworks.json by hand.

Usage:
    python scripts/regulatory_change_check.py              # report only
    python scripts/regulatory_change_check.py --commit     # also refresh hashes
    python scripts/regulatory_change_check.py --json       # machine-readable output
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("reg_change_check")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "regulatory_frameworks.json"
HASHES_PATH = ROOT / "data" / "regulatory_frameworks_hashes.json"

USER_AGENT = "ESGLens-RegChange/1.0 (compliance monitoring; non-commercial)"
FETCH_TIMEOUT_SECS = 12
SLEEP_BETWEEN_REQUESTS = 1.5  # Be polite to regulator sites.


# ── Fetch + normalise ───────────────────────────────────────────────────────

def _fetch(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (text, error_message). text is None on failure."""
    if not url or not url.startswith(("http://", "https://")):
        return None, "invalid URL"
    try:
        import httpx
    except ImportError:
        return None, "httpx not installed"

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_SECS,
            follow_redirects=True,
        ) as client:
            r = client.get(url)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        ctype = (r.headers.get("content-type") or "").lower()
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            # PDFs etc. — hash the raw bytes since we can't normalise text.
            return f"binary:sha256:{hashlib.sha256(r.content).hexdigest()}", None
        return r.text, None
    except Exception as exc:
        return None, str(exc)[:160]


def _normalise(text: str) -> str:
    """Strip whitespace + dynamic content (CSRF tokens, timestamps, session
    IDs) before hashing. Goal: stable hash across HTTP runs of the same
    page, sensitive only to substantive content changes."""
    if not text:
        return ""
    if text.startswith("binary:sha256:"):
        return text  # already a stable digest
    # Strip script + style blocks (highly dynamic).
    out = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.S | re.I)
    out = re.sub(r"<style\b[^>]*>.*?</style>", "", out, flags=re.S | re.I)
    # Drop HTML comments.
    out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    # Strip common dynamic attrs.
    out = re.sub(r'\s(?:nonce|csrf|csrf-token|data-csrf|data-timestamp)="[^"]*"', "", out, flags=re.I)
    # Collapse whitespace.
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


# ── Hash store ──────────────────────────────────────────────────────────────

def _load_hashes() -> Dict[str, Any]:
    if not HASHES_PATH.exists():
        return {}
    try:
        with open(HASHES_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_hashes(hashes: Dict[str, Any]) -> None:
    tmp = str(HASHES_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
    os.replace(tmp, HASHES_PATH)


# ── Main check loop ─────────────────────────────────────────────────────────

def check(commit: bool = False) -> Dict[str, Any]:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f) or {}

    frameworks = registry.get("frameworks") or []
    old_hashes = _load_hashes()
    new_hashes: Dict[str, Any] = dict(old_hashes)  # carry over so we don't lose info

    results: Dict[str, Any] = {
        "checked_at":   datetime.utcnow().isoformat() + "Z",
        "registry_version": registry.get("registry_version"),
        "changed":      [],
        "new":          [],
        "unreachable":  [],
        "unchanged":    [],
    }

    for fw in frameworks:
        fid = fw.get("framework_id") or fw.get("name")
        url = fw.get("source_url")
        if not (fid and url):
            continue

        text, err = _fetch(url)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if text is None:
            results["unreachable"].append({
                "framework_id": fid,
                "name":         fw.get("name"),
                "url":          url,
                "error":        err,
            })
            continue

        h = _hash(_normalise(text))
        prev = old_hashes.get(fid)
        if prev is None:
            results["new"].append({
                "framework_id": fid,
                "name":         fw.get("name"),
                "current_hash": h,
            })
            new_hashes[fid] = {
                "hash":          h,
                "url":           url,
                "last_checked":  results["checked_at"],
                "last_changed":  results["checked_at"],
            }
        elif prev.get("hash") != h:
            results["changed"].append({
                "framework_id": fid,
                "name":         fw.get("name"),
                "url":          url,
                "previous_hash": prev.get("hash"),
                "current_hash":  h,
                "previous_checked": prev.get("last_checked"),
                "previous_changed": prev.get("last_changed"),
            })
            new_hashes[fid] = {
                "hash":          h,
                "url":           url,
                "last_checked":  results["checked_at"],
                "last_changed":  results["checked_at"],
            }
        else:
            results["unchanged"].append({
                "framework_id": fid,
                "name":         fw.get("name"),
            })
            new_hashes[fid] = {
                **prev,
                "last_checked": results["checked_at"],
            }

    if commit:
        _save_hashes(new_hashes)

    return results


def _print_human(results: Dict[str, Any]) -> None:
    print(f"\nRegulatory change check @ {results['checked_at']}")
    print(f"Registry version: {results.get('registry_version')}\n")

    if results["changed"]:
        print(f"⚠️  CHANGED: {len(results['changed'])}")
        for c in results["changed"]:
            print(f"  - [{c['framework_id']}] {c['name']}")
            print(f"      url:   {c['url']}")
            print(f"      hash:  {c['previous_hash'][:12]}  →  {c['current_hash'][:12]}")
            print(f"      since: {c.get('previous_changed', '?')}")
        print("    Action: review the source URL, decide if the registry needs a version bump.")
        print()

    if results["new"]:
        print(f"+ NEW (first seen): {len(results['new'])}")
        for n in results["new"]:
            print(f"  - [{n['framework_id']}] {n['name']}  hash={n['current_hash'][:12]}")
        print()

    if results["unreachable"]:
        print(f"✗ UNREACHABLE: {len(results['unreachable'])}")
        for u in results["unreachable"]:
            print(f"  - [{u['framework_id']}] {u['name']}  ({u['error']})")
        print()

    print(f"= UNCHANGED: {len(results['unchanged'])}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Regulatory framework change detector.")
    ap.add_argument("--commit", action="store_true",
                    help="Refresh the hash file (otherwise read-only check).")
    ap.add_argument("--json", action="store_true",
                    help="Machine-readable JSON output to stdout.")
    args = ap.parse_args()

    results = check(commit=args.commit)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_human(results)

    if results["changed"]:
        return 1
    if results["unreachable"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
