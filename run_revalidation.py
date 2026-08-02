#!/usr/bin/env python3
"""run_revalidation.py -- the daily revalidation runner (Checkable Open).

Runs the reference validator (validate_manifest.py, the ONLY conformance validator;
there is no ported copy anywhere) against every monitored manifest: paying
subscribers, free registry entries from adopters.json, and our own manifest. Applies
standing.py (the ONLY state machine) to each result and posts run records, new
standing, and events to the Checkable Open worker, which stores them and sends any
alert emails. One code path for everyone is the point, not an optimization.

Invocation (GitHub Actions, three passes a day):
  python3 run_revalidation.py                 full pass over every active target
  python3 run_revalidation.py --confirm-only  re-fetch only subjects with an
                                              unconfirmed failure (passes 2 and 3)

Environment:
  WORKER_BASE   base URL of the worker (default https://checkable.clickcoded.com)
  RUNNER_TOKEN  bearer token for POST /open/api/runs (required to post; without it
                the runner prints what it would post and exits 1, which keeps manual
                dry runs safe by default)

Also updates adopters.json status fields in place from the computed standing (the
registry file mirrors the state machine; it never has an opinion of its own). The
Action commits that diff when present.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import standing

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate_manifest.py"
ADOPTERS = HERE / "adopters.json"
WORKER_BASE = os.environ.get("WORKER_BASE", "https://checkable.clickcoded.com").rstrip("/")
RUNNER_TOKEN = os.environ.get("RUNNER_TOKEN", "")
CHECKER = "reference-validator, run by the spec's authors"
UA = {"User-Agent": "checkable-open-runner/1.0 (+https://checkable.clickcoded.com/open/)"}


def validator_version():
    m = re.search(r"receipts-validator/([\d.]+)", VALIDATOR.read_text())
    return m.group(1) if m else "unknown"


def http_json(url, payload=None, token=None):
    headers = dict(UA)
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def slug_for(manifest_url):
    """Subject slug = the manifest's host, lowercased, www stripped. Keep in sync
    with slugFor() in the worker's src/util.ts."""
    host = urllib.parse.urlparse(manifest_url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def manifest_sha256(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return hashlib.sha256(resp.read()).hexdigest()
    except Exception:
        return None


def run_validator(manifest_url):
    """Run the reference validator once. Returns (verdict, failures, stdout)."""
    try:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), manifest_url],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "nonconforming", ["validator timeout after 120s"], ""
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        return "conforming", [], out
    failures = [line for line in out.splitlines() if line.strip()]
    if not failures:
        # The validator crashed rather than reporting: the manifest was unreachable
        # or unparseable. The last raw line of the traceback names the cause.
        tail = err.splitlines()[-1].strip() if err else "validator error with no output"
        failures = [f"manifest fetch or parse failed: {tail}"]
    return "nonconforming", failures, out


def parse_conforming_stats(stdout):
    """Pull claim count and the independence breakdown from a conforming run's output."""
    claims = None
    breakdown = None
    m = re.search(r"CONFORMING: (\d+) claims", stdout)
    if m:
        claims = int(m.group(1))
    m = re.search(r"breakdown \(Hole 2, informational[^)]*\): (.+)", stdout)
    if m:
        breakdown = m.group(1).strip()
    return claims, breakdown


def build_targets(worker_targets):
    """Merge worker subjects (subscribers + self) with adopters.json entries.
    Keyed by SLUG, not manifest_url: an http/https or www variant of the same
    host must collapse to one subject, or two targets would race on one slug's
    state. Subscriber entries win the collision so alerts stay attached."""
    targets = {}
    adopters = json.loads(ADOPTERS.read_text()).get("adopters", [])
    for entry in adopters:
        slug = slug_for(entry["manifest_url"])
        targets[slug] = {
            "slug": slug, "manifest_url": entry["manifest_url"],
            "display_name": entry.get("name", slug), "kind": "adopter"}
    for t in worker_targets:
        targets[t["slug"]] = t
    return list(targets.values())


def update_adopters_file(states, now_date):
    data = json.loads(ADOPTERS.read_text())
    changed = False
    for entry in data.get("adopters", []):
        slug = slug_for(entry["manifest_url"])
        st = states.get(slug)
        if not st:
            continue
        updates = {"status": st["state"], "last_validated": now_date,
                   "last_conforming": st["last_conforming_at"]}
        if st["state"] == "failing":
            updates["failing_since"] = st["failing_since"]
        else:
            entry.pop("failing_since", None)
        if st["state"] == "delisted":
            updates["delisted"] = st["delisted_at"]
        else:
            entry.pop("delisted", None)
        for k, v in updates.items():
            if entry.get(k) != v:
                entry[k] = v
                changed = True
    if changed:
        ADOPTERS.write_text(json.dumps(data, indent=2) + "\n")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-only", action="store_true",
                    help="re-fetch only subjects carrying an unconfirmed failure")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the payload instead of posting it")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    fetched_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    vver = validator_version()

    api = http_json(f"{WORKER_BASE}/open/api/targets")
    current = http_json(f"{WORKER_BASE}/open/api/state")
    targets = build_targets(api.get("targets", []))

    if args.confirm_only:
        targets = [t for t in targets
                   if current.get(t["slug"], {}).get("unconfirmed_fails", 0) > 0]
        if not targets:
            print("confirm-only pass: no unconfirmed failures, nothing to do")
            return 0

    records, states, events = [], {}, []
    for t in targets:
        verdict, failures, out = run_validator(t["manifest_url"])
        prev = current.get(t["slug"]) or standing.fresh_state()
        prev = {k: prev.get(k) if k != "unconfirmed_fails" else prev.get(k, 0)
                for k in standing.fresh_state()}
        new_state, evs = standing.apply_run(prev, verdict, fetched_at, failures)
        record = {
            "subject_slug": t["slug"], "display_name": t.get("display_name", t["slug"]),
            "kind": t.get("kind", "adopter"),
            "manifest_url": t["manifest_url"], "fetched_at": fetched_at,
            "manifest_sha256": manifest_sha256(t["manifest_url"]),
            "validator_version": vver, "verdict": verdict,
            "failures": failures, "checker": CHECKER,
        }
        if verdict == "conforming":
            claims, breakdown = parse_conforming_stats(out)
            record["claim_count"] = claims
            record["independence"] = breakdown
        records.append(record)
        states[t["slug"]] = new_state
        for e in evs:
            events.append({"subject_slug": t["slug"], "at": fetched_at, **e})
        print(f"{t['slug']}: {verdict}" + (f" ({len(failures)} failure(s))" if failures else ""))

    payload = {"records": records, "states": states, "events": events}
    if args.dry_run or not RUNNER_TOKEN:
        print(json.dumps(payload, indent=2))
        if not RUNNER_TOKEN and not args.dry_run:
            print("RUNNER_TOKEN not set: nothing posted", file=sys.stderr)
            return 1
        return 0

    resp = http_json(f"{WORKER_BASE}/open/api/runs", payload, RUNNER_TOKEN)
    print(f"posted: {json.dumps(resp)}")

    # Always mirror computed standing into adopters.json, every mode. A
    # confirm-only pass can flip a state (a confirmed failure, a blip recovery),
    # and the registry file lagging the worker by a day on exactly those runs
    # was the audit finding that removed the mode condition here.
    if update_adopters_file(states, fetched_at[:10]):
        print("adopters.json updated from computed standing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
