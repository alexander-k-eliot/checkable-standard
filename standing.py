#!/usr/bin/env python3
"""standing.py -- the registry standing policy, as running code.

This module IS the published rule the registry doctrine points at. One state machine,
imported by validate_adopters.py (manual runs) and run_revalidation.py (the daily
automated runs), applied identically to paying subscribers, free registry entries, and
our own manifest. There is deliberately no second implementation anywhere: if you want
to know what the clock does, read this file; if we want to change the clock, the diff
is public.

States and clock (the doctrine):
  conforming            the last confirmed validation passed.
  failing (since date)  a failure was CONFIRMED: the initial failed fetch plus
                        CONFIRM_RUNS-1 re-fetches spread over at least
                        CONFIRM_SPAN_HOURS hours all failed. Transient blips never
                        flip public state. Public surfaces keep showing the last
                        confirmed result until confirmation.
  delisted (date)       DELIST_DAYS consecutive days confirmed-failing. The entry is
                        never removed, only marked. Relisting is automatic on the next
                        conforming validation. The lapse stays in the public history.

Two dates, one shown: failing_since drives this clock and is internal. The public
sign and standing page print last_conforming_at in every state (decided 2026-08-02).

Same states, same clock, everyone. A subscription buys detection speed (alert email),
never lenience.
"""

from datetime import datetime, date

CONFIRM_RUNS = 3          # 1 initial failed fetch + 2 re-fetches
CONFIRM_SPAN_HOURS = 5    # the re-fetches span ~6h; a 5h floor tolerates cron jitter
DELIST_DAYS = 14          # consecutive confirmed-failing days before delisting
T3_DAYS = DELIST_DAYS - 3 # reminder fires with 3 days left on the clock

STATES = ("unchecked", "conforming", "failing", "delisted")


def _parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _parse_date(d):
    return date.fromisoformat(d[:10])


def apply_run(prev, verdict, fetched_at, failures=None):
    """Apply one validation run to a subject's standing.

    prev: dict with keys state, last_conforming_at, failing_since, delisted_at,
          unconfirmed_fails, unconfirmed_first_at (all nullable except state).
    verdict: "conforming" | "nonconforming".
    fetched_at: ISO-8601 UTC timestamp of this run's fetch.
    failures: list of validator failure strings (nonconforming runs).

    Returns (new_state_dict, events). Events are dicts {"type": ..., "detail": {...}}.
    Event types: failure_confirmed, t3_reminder, delisted, relisted, recovered.
    t3_reminder may be emitted on several consecutive days of the same failing
    episode; consumers de-duplicate per episode using detail["episode"].
    """
    run_date = fetched_at[:10]
    new = dict(prev)
    events = []

    if verdict == "conforming":
        if prev["state"] == "failing":
            events.append({"type": "recovered", "detail": {
                "failing_since": prev["failing_since"], "conforming_on": run_date}})
        elif prev["state"] == "delisted":
            events.append({"type": "relisted", "detail": {
                "failing_since": prev["failing_since"],
                "delisted_at": prev["delisted_at"], "conforming_on": run_date}})
        new.update(state="conforming", last_conforming_at=run_date,
                   failing_since=None, delisted_at=None,
                   unconfirmed_fails=0, unconfirmed_first_at=None)
        return new, events

    # Nonconforming run.
    failures = failures or []
    if prev["state"] in ("failing", "delisted"):
        days = (_parse_date(run_date) - _parse_date(prev["failing_since"])).days
        if prev["state"] == "failing":
            if days >= DELIST_DAYS:
                new.update(state="delisted", delisted_at=run_date)
                events.append({"type": "delisted", "detail": {
                    "failing_since": prev["failing_since"], "delisted_at": run_date,
                    "failures": failures}})
            elif days >= T3_DAYS:
                events.append({"type": "t3_reminder", "detail": {
                    "episode": prev["failing_since"],
                    "days_failing": days,
                    "delist_on_day": DELIST_DAYS,
                    "failures": failures}})
        return new, events

    # Previously conforming (or never checked): this failure is unconfirmed until
    # CONFIRM_RUNS fetches spanning CONFIRM_SPAN_HOURS have all failed.
    fails = prev["unconfirmed_fails"] + 1
    first_at = prev["unconfirmed_first_at"] or fetched_at
    span_hours = (_parse_ts(fetched_at) - _parse_ts(first_at)).total_seconds() / 3600.0
    if fails >= CONFIRM_RUNS and span_hours >= CONFIRM_SPAN_HOURS:
        new.update(state="failing", failing_since=run_date,
                   unconfirmed_fails=0, unconfirmed_first_at=None)
        events.append({"type": "failure_confirmed", "detail": {
            "failing_since": run_date, "first_failed_fetch": first_at,
            "failed_fetches": fails, "failures": failures}})
    else:
        new.update(unconfirmed_fails=fails, unconfirmed_first_at=first_at)
    return new, events


def fresh_state():
    """The standing of a subject that has never been validated."""
    return {"state": "unchecked", "last_conforming_at": None, "failing_since": None,
            "delisted_at": None, "unconfirmed_fails": 0, "unconfirmed_first_at": None}


if __name__ == "__main__":
    # Self-test: the policy's own examples, runnable by anyone.
    import json as _json

    def run(prev, verdict, at, failures=None):
        return apply_run(prev, verdict, at, failures)

    s = fresh_state()
    s, ev = run(s, "conforming", "2026-08-02T13:00:00Z")
    assert s["state"] == "conforming" and s["last_conforming_at"] == "2026-08-02" and not ev

    # A single blip never flips public state.
    s1, ev = run(s, "nonconforming", "2026-08-03T13:00:00Z", ["evidence fetch 404"])
    assert s1["state"] == "conforming" and s1["unconfirmed_fails"] == 1 and not ev

    # Two more failed fetches inside the confirmation window: confirmed at the third.
    s2, ev = run(s1, "nonconforming", "2026-08-03T16:00:00Z", ["evidence fetch 404"])
    assert s2["state"] == "conforming" and not ev
    s3, ev = run(s2, "nonconforming", "2026-08-03T19:00:00Z", ["evidence fetch 404"])
    assert s3["state"] == "failing" and s3["failing_since"] == "2026-08-03"
    assert [e["type"] for e in ev] == ["failure_confirmed"]

    # A recovery between re-fetches resets the count: blip recorded, nothing confirmed.
    r, ev = run(s1, "conforming", "2026-08-03T16:00:00Z")
    assert r["state"] == "conforming" and r["unconfirmed_fails"] == 0 and not ev

    # The clock: reminder with 3 days left, delist at day 14, relist on recovery.
    f = dict(s3)
    f, ev = run(f, "nonconforming", "2026-08-14T13:00:00Z", ["x"])
    assert [e["type"] for e in ev] == ["t3_reminder"] and ev[0]["detail"]["days_failing"] == 11
    f, ev = run(f, "nonconforming", "2026-08-17T13:00:00Z", ["x"])
    assert f["state"] == "delisted" and [e["type"] for e in ev] == ["delisted"]
    f, ev = run(f, "conforming", "2026-08-20T13:00:00Z")
    assert f["state"] == "conforming" and [e["type"] for e in ev] == ["relisted"]
    assert f["last_conforming_at"] == "2026-08-20" and f["delisted_at"] is None

    # Three failures spread over days with no confirmation passes still confirm
    # (a persistent failure is not a blip just because the retries did not run).
    a = dict(s)
    a, _ = run(a, "nonconforming", "2026-08-05T13:00:00Z", ["x"])
    a, _ = run(a, "nonconforming", "2026-08-06T13:00:00Z", ["x"])
    a, ev = run(a, "nonconforming", "2026-08-07T13:00:00Z", ["x"])
    assert a["state"] == "failing" and [e["type"] for e in ev] == ["failure_confirmed"]

    print(_json.dumps({"standing.py": "self-test passed",
                       "confirm_runs": CONFIRM_RUNS, "confirm_span_hours": CONFIRM_SPAN_HOURS,
                       "delist_days": DELIST_DAYS}))
