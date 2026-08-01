#!/usr/bin/env python3
"""validate_adopters.py -- re-validates every entry in adopters.json against the real
validate_manifest.py, updates status and last_validated in place. Delists (status:"delisted",
never removed -- append-only spirit applies to the registry too) any manifest that stops
validating. Run before trusting the registry's own last_validated timestamps; nothing here
runs automatically yet (registry is dark, zero entries as of 2026-07-31)."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADOPTERS = HERE / "adopters.json"
VALIDATOR = HERE / "validate_manifest.py"


def main():
    data = json.loads(ADOPTERS.read_text())
    today = datetime.now(timezone.utc).date().isoformat()
    changed = False
    for entry in data.get("adopters", []):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), entry["manifest_url"]],
            capture_output=True, text=True, timeout=30,
        )
        conforming = result.returncode == 0
        new_status = "conforming" if conforming else "delisted"
        if entry.get("status") != new_status:
            print(f"{entry['name']}: {entry.get('status', '?')} -> {new_status}")
            changed = True
        entry["status"] = new_status
        entry["last_validated"] = today
        if not conforming:
            print(f"  reason: {result.stdout.strip() or result.stderr.strip()}")
    if changed:
        ADOPTERS.write_text(json.dumps(data, indent=2) + "\n")
        print("adopters.json updated.")
    else:
        print(f"No status changes. {len(data.get('adopters', []))} adopter(s) checked.")


if __name__ == "__main__":
    main()
