#!/usr/bin/env python3
"""validate_manifest.py — Receipts Standard v0.1 validator. Usage: validate_manifest.py <url-or-path>.
Checks schema conformance and fetches every public evidence ref (HTTP 200 = pass)."""
import json, sys, urllib.request
src = sys.argv[1] if len(sys.argv)>1 else 'https://clickcoded.com/ai-visibility-check-free/receipts.json'
UA={'User-Agent':'receipts-validator/0.1 (+https://clickcoded.com/ai-visibility-check-free/the-receipts-standard/)'}
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15)
data = json.load(get(src)) if src.startswith('http') else json.load(open(src))
errs = []
if not str(data.get('spec','')).startswith('receipts-standard/'): errs.append('missing/unknown spec id')
for k in ('operator','generated','claims','rules'):
    if k not in data: errs.append(f'missing top-level: {k}')
ids=set()
for c in data.get('claims',[]):
    for k in ('id','date','category','claim','evidence','verifiability'):
        if k not in c: errs.append(f"{c.get('id','?')}: missing {k}")
    if c['id'] in ids: errs.append(f"duplicate id {c['id']}")
    ids.add(c['id'])
    if c.get('corrects') and c['corrects'] not in ids: errs.append(f"{c['id']}: corrects unknown claim")
    if c.get('verifiability')=='public':
        try:
            code=get(c['evidence']['ref']).status
            if code!=200: errs.append(f"{c['id']}: evidence fetch {code}")
        except Exception as e: errs.append(f"{c['id']}: evidence unreachable ({e})")
print('\n'.join(errs) if errs else f"CONFORMING: {len(ids)} claims, all public evidence reachable.")
sys.exit(1 if errs else 0)
