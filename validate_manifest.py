#!/usr/bin/env python3
"""validate_manifest.py — Receipts Standard v0.1/v0.2 validator. Usage: validate_manifest.py <url-or-path>.
Checks schema conformance, fetches every public evidence ref (HTTP 200 = pass), and — v0.2 —
verifies evidence.excerpt substrings and reports an evidence-independence breakdown."""
import json, sys, urllib.request
src = sys.argv[1] if len(sys.argv)>1 else 'https://clickcoded.com/ai-visibility-check-free/receipts.json'
UA={'User-Agent':'receipts-validator/0.2 (+https://clickcoded.com/ai-visibility-check-free/the-receipts-standard/)'}
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15)
data = json.load(get(src)) if src.startswith('http') else json.load(open(src))
errs = []
if not str(data.get('spec','')).startswith('receipts-standard/0.1') and not str(data.get('spec','')).startswith('receipts-standard/0.2'):
    errs.append('missing/unknown spec id')
for k in ('operator','generated','claims','rules'):
    if k not in data: errs.append(f'missing top-level: {k}')
if 'coverage' in data and not isinstance(data['coverage'], list):
    errs.append('coverage must be a list of category strings')
ids=set()
independence_counts = {}
for c in data.get('claims',[]):
    for k in ('id','date','category','claim','evidence','verifiability'):
        if k not in c: errs.append(f"{c.get('id','?')}: missing {k}")
    if c['id'] in ids: errs.append(f"duplicate id {c['id']}")
    ids.add(c['id'])
    if c.get('corrects') and c['corrects'] not in ids: errs.append(f"{c['id']}: corrects unknown claim")
    ev = c.get('evidence', {})
    independence_counts[ev.get('independence', 'unlabeled')] = independence_counts.get(ev.get('independence', 'unlabeled'), 0) + 1
    body = None
    if c.get('verifiability')=='public':
        try:
            resp = get(ev['ref'])
            code = resp.status
            if code!=200: errs.append(f"{c['id']}: evidence fetch {code}")
            elif ev.get('excerpt'):
                body = resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            errs.append(f"{c['id']}: evidence unreachable ({e})")
    if ev.get('excerpt') and c.get('verifiability')=='public' and body is not None:
        if ev['excerpt'] not in body:
            errs.append(f"{c['id']}: evidence.excerpt not found in fetched page (Hole 4 check failed — the ref is reachable but doesn't visibly support the claim)")
    if 'confidence' in c and 'level' not in c['confidence']:
        errs.append(f"{c['id']}: confidence present but missing required 'level'")

if errs:
    print('\n'.join(errs))
    sys.exit(1)
breakdown = ', '.join(f"{k}: {v}" for k, v in sorted(independence_counts.items()))
print(f"CONFORMING: {len(ids)} claims, all public evidence reachable (+ excerpt-verified where declared).")
print(f"Evidence independence breakdown (Hole 2, informational — not a pass/fail): {breakdown}")
sys.exit(0)
