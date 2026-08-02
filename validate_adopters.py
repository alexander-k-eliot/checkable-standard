#!/usr/bin/env python3
"""validate_adopters.py -- re-validates every entry in adopters.json against the real
validate_manifest.py and applies the registry standing policy from standing.py: three
states (conforming / failing since a date / delisted after 14 consecutive confirmed-
failing days), automatic relisting on the next conforming run, entries never removed.

Upgraded 2026-08-02 from the original two-state immediate flip. The policy now lives
in standing.py, which is also what the daily automated runs use (run_revalidation.py),
so a manual run of this script and the cron apply the identical rule. One caveat a
manual run cannot fix: confirming a NEW failure takes three failed fetches spread over
hours (standing.CONFIRM_RUNS / CONFIRM_SPAN_HOURS), so a single manual run against a
freshly broken manifest correctly reports it still-conforming with the blip counted.
That is the policy working, not the script failing. The daily runs do the confirming.

Once the Checkable Open worker is live, prefer the automated path: it also stores the
append-only run record every validation should leave behind. This script stays for
offline checks and as the doctrine's runnable, dependency-free demonstration.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import standing

HERE = Path(__file__).resolve().parent
ADOPTERS = HERE / "adopters.json"
VALIDATOR = HERE / "validate_manifest.py"


def entry_state(entry):
    """Rebuild a standing dict from an adopters.json entry's persisted fields."""
    st = standing.fresh_state()
    status = entry.get("status")
    if status in standing.STATES:
        st["state"] = status
    elif status:
        # Legacy two-state file: "delisted" maps directly, anything else was
        # "conforming". Unknown strings fail loudly rather than silently reset.
        raise SystemExit(f"unknown status {status!r} for {entry.get('name')}")
    st["last_conforming_at"] = entry.get("last_conforming")
    st["failing_since"] = entry.get("failing_since")
    st["delisted_at"] = entry.get("delisted")
    st["unconfirmed_fails"] = entry.get("_unconfirmed_fails", 0)
    st["unconfirmed_first_at"] = entry.get("_unconfirmed_first_at")
    return st


def persist(entry, st, today):
    entry["status"] = st["state"]
    entry["last_validated"] = today
    entry["last_conforming"] = st["last_conforming_at"]
    for key, field in (("failing_since", "failing_since"), ("delisted", "delisted_at")):
        if st[field]:
            entry[key] = st[field]
        else:
            entry.pop(key, None)
    for key, field in (("_unconfirmed_fails", "unconfirmed_fails"),
                       ("_unconfirmed_first_at", "unconfirmed_first_at")):
        if st[field]:
            entry[key] = st[field]
        else:
            entry.pop(key, None)


def main():
    data = json.loads(ADOPTERS.read_text())
    now = datetime.now(timezone.utc)
    fetched_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = False
    for entry in data.get("adopters", []):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), entry["manifest_url"]],
            capture_output=True, text=True, timeout=120,
        )
        verdict = "conforming" if result.returncode == 0 else "nonconforming"
        failures = [l for l in (result.stdout or "").splitlines() if l.strip()] \
            if verdict == "nonconforming" else []
        prev = entry_state(entry)
        st, events = standing.apply_run(prev, verdict, fetched_at, failures)
        before = json.dumps(entry, sort_keys=True)
        persist(entry, st, fetched_at[:10])
        if json.dumps(entry, sort_keys=True) != before:
            changed = True
        label = st["state"]
        if st["state"] == "conforming" and st["unconfirmed_fails"]:
            label += f" (unconfirmed failure {st['unconfirmed_fails']}/{standing.CONFIRM_RUNS})"
        print(f"{entry['name']}: {label}")
        for e in events:
            print(f"  event: {e['type']} {json.dumps(e['detail'])}")
        for f in failures:
            print(f"  {f}")
    if changed:
        ADOPTERS.write_text(json.dumps(data, indent=2) + "\n")
        print("adopters.json updated.")
    else:
        print(f"No changes. {len(data.get('adopters', []))} adopter(s) checked.")


if __name__ == "__main__":
    main()
