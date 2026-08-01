#!/usr/bin/env python3
"""validate_manifest.py — Checkable Standard v0.1/v0.2/v0.3 validator (wire-format spec identifier stays 'receipts-standard/0.x'). Usage: validate_manifest.py <url-or-path>.
Checks structural conformance (required fields, category/evidence-type enums, declared coverage
actually has claims), fetches every public evidence ref (HTTP 200 = pass), and — v0.2 — verifies
evidence.excerpt substrings and reports an evidence-independence breakdown. v0.3 validates the
optional per-claim metrics object (numeric values only) if present."""
import json, sys, urllib.request
src = sys.argv[1] if len(sys.argv)>1 else 'https://clickcoded.com/ai-visibility-check-free/receipts.json'
UA={'User-Agent':'receipts-validator/0.3 (+https://receipts.clickcoded.com/)'}
CATEGORIES = {"revenue","delivery","send","correction","grant","infrastructure","disclosure","challenge"}
EVIDENCE_TYPES = {"public-url","platform-record","ledger","git-commit"}
SPEC_PREFIXES = ('receipts-standard/0.1', 'receipts-standard/0.2', 'receipts-standard/0.3')

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15)
data = json.load(get(src)) if src.startswith('http') else json.load(open(src))
errs = []
if not str(data.get('spec','')).startswith(SPEC_PREFIXES):
    errs.append('missing/unknown spec id')
for k in ('operator','generated','claims','rules'):
    if k not in data: errs.append(f'missing top-level: {k}')
operator = data.get('operator') or {}
for k in ('name','url','operator_type','disclosure'):
    if not operator.get(k): errs.append(f"operator: missing or empty required field '{k}'")
coverage = data.get('coverage')
if coverage is not None and not isinstance(coverage, list):
    errs.append('coverage must be a list of category strings')
    coverage = None

ids=set()
independence_counts = {}
categories_seen = set()
for c in data.get('claims',[]):
    for k in ('id','date','category','claim','evidence','verifiability'):
        if k not in c: errs.append(f"{c.get('id','?')}: missing {k}")
    cid = c.get('id')
    if cid is not None:
        if cid in ids: errs.append(f"duplicate id {cid}")
        ids.add(cid)
    if c.get('corrects') and c['corrects'] not in ids:
        errs.append(f"{c.get('id','?')}: corrects unknown claim")
    if c.get('category') and c['category'] not in CATEGORIES:
        errs.append(f"{c.get('id','?')}: unknown category '{c['category']}'")
    else:
        categories_seen.add(c.get('category'))
    if c.get('category') == 'correction' and not c.get('corrects'):
        errs.append(f"{c.get('id','?')}: category is 'correction' but 'corrects' is missing — a correction with nothing named to correct isn't append-only, it's just a claim")
    ev = c.get('evidence') or {}
    if ev.get('type') and ev['type'] not in EVIDENCE_TYPES:
        errs.append(f"{c.get('id','?')}: unknown evidence.type '{ev['type']}'")
    independence_counts[ev.get('independence', 'unlabeled')] = independence_counts.get(ev.get('independence', 'unlabeled'), 0) + 1
    body = None
    if c.get('verifiability')=='public' and ev.get('ref'):
        try:
            resp = get(ev['ref'])
            code = resp.status
            if code!=200: errs.append(f"{c.get('id','?')}: evidence fetch {code}")
            elif ev.get('excerpt'):
                body = resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            errs.append(f"{c.get('id','?')}: evidence unreachable ({e})")
    if ev.get('excerpt') and c.get('verifiability')=='public' and body is not None:
        if ev['excerpt'] not in body:
            errs.append(f"{c.get('id','?')}: evidence.excerpt not found in fetched page (Hole 4 check failed — the ref is reachable but doesn't visibly support the claim)")
    if 'confidence' in c and 'level' not in (c['confidence'] or {}):
        errs.append(f"{c.get('id','?')}: confidence present but missing required 'level'")
    if 'metrics' in c:
        metrics = c['metrics']
        if not isinstance(metrics, dict):
            errs.append(f"{c.get('id','?')}: metrics must be an object")
        else:
            for mk, mv in metrics.items():
                if isinstance(mv, bool) or not isinstance(mv, (int, float)):
                    errs.append(f"{c.get('id','?')}: metrics.{mk} must be a number, got {mv!r}")

if coverage:
    for declared in coverage:
        if declared not in categories_seen:
            errs.append(f"coverage declares '{declared}' but no claim of that category exists (Hole 1: a manifest silent on a declared category is non-conforming)")

if errs:
    print('\n'.join(errs))
    sys.exit(1)
breakdown = ', '.join(f"{k}: {v}" for k, v in sorted(independence_counts.items()))
print(f"CONFORMING: {len(ids)} claims, all public evidence reachable (+ excerpt-verified where declared).")
print(f"Evidence independence breakdown (Hole 2, informational — not a pass/fail): {breakdown}")
sys.exit(0)
