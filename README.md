# The Checkable Standard

**An open standard for verifiable operations.** v0.3. Formerly published as The Receipts Standard
(renamed 2026-08-01 — same spec, same manifest, same wire format; see Version history below).

**Don't trust AI. Check it.** Checkable is the payoff: the lived accountability practice of
machine-checkable honesty for AI-operated businesses, codified as an open spec.

The agent economy has standardized identity (signed agents) and payments (x402). Serious projects —
[OVERT](https://overt.is/), [Agent Receipts](https://agentreceipts.ai/),
[Trust Receipts™](https://www.axissystems.io/post/trust-receipts) — are now building cryptographic
attestation that a specific agent took a specific action. As of our 2026-07-31 prior-art check, none
of them cover the layer below: what an AI-operated *business* claims about itself — revenue,
deliveries, mistakes, corrections. An economy of agents that can pay but cannot be audited is an
economy of confident liars with wallets. This is that layer, small enough to adopt in an afternoon,
no keys or infrastructure required. It composes with the projects above rather than competing with
them — an operation could run one of them for action-level attestation and publish `checkable.json`
(a `receipts.json` alias is served forever) for business-level claims.

*(An earlier version of this README claimed nobody had built anything at this layer. A real
prior-art check on 2026-07-31 found the above and proved that claim false — corrected here, and
logged in our own reference manifest as `rcpt-0025`, the same way any other correction is. If we've
missed prior art at this specific layer, tell us — `run@clickcoded.com` — and it gets linked here.)*

## The standard, in five rules

1. Publish a machine-readable manifest (`checkable.json`, with `receipts.json` served forever
   alongside it as an alias) of your material claims.
2. Every claim carries evidence: a fetchable public URL, or a named platform record disclosed to
   any requester. **A claim without evidence is not a claim.**
3. Corrections are **append-only** — a correction is a new claim referencing the claim it corrects.
   Deleting or rewriting history is non-conformance.
4. The manifest states the operator honestly: AI, human, or hybrid — disclosed.
5. Anyone can validate — schema plus evidence reachability — with no permission from the operator.

## What's new in v0.2

v0.1 published its own attack surface — six named holes — and committed to a fix direction for
each. v0.2 ships four new fields addressing four of them (a v0.1 manifest is still conforming),
answers a fifth with no schema change, and deliberately leaves the sixth open:

- **Coverage** (Hole 1, cherry-picking): top-level `coverage: []` declares which claim categories
  this manifest commits to — hand-pin it, don't auto-derive it from whatever categories a given
  build happens to have, or the declaration can never fail its own check. Pair it with
  `rules.materiality`, one line stating what counts as material enough to require a claim. A
  `category: "challenge"` claim logs a third party's "you're missing X" question and the
  operator's answer (or open status) in the same append-only claims array — the public challenge
  mechanism, no new system required.
- **Evidence independence** (Hole 2, self-referential evidence): `evidence.independence` labels
  each claim's evidence `third-party` / `payment-processor` / `own-site`, honestly, not hidden.
  The validator reports a breakdown; it doesn't gate on it.
- **Evidence excerpt** (Hole 4, reachability ≠ meaning): `evidence.excerpt` is a substring the
  validator confirms actually appears on the fetched page — HTTP 200 alone no longer passes if the
  claim also declares what the page should say. Limitation, stated plainly: this is a raw-HTML
  substring match — smart quotes, em dashes, or a page whose content is rendered client-side by
  JavaScript can all cause a false failure on an otherwise-true claim. Use plain-ASCII excerpts
  from static HTML where you can.
- **Confidence** (Hole 6, overstated confidence): an optional `confidence: {level, caveat}` on any
  claim that's true but not certain.
- **Goodharting** (Hole 5) has no schema change — the materiality field above plus the standing
  culture rule ("a manifest with no corrections is a red flag") is the stated answer.

**On migrations:** rule 3 (append-only) governs claim *content* — you can't rewrite what was
claimed or when. Adding v0.2 metadata (independence labels, etc.) to pre-existing claims in place,
as this repo's own reference manifest did, is not a rule-3 violation as long as the change is
itself visible in public git history and archived versions, and doesn't alter what was originally
claimed. If in doubt, log the migration itself as a `disclosure` claim, evidenced by the commit
that made it — that's what the reference manifest does.

**Not in v0.2:** signed/cryptographically-attested manifests (Hole 3). That needs real key
custody, which is a candidate for a future version, not a commitment (see What's next below). The
interim mitigation is unchanged and already live today: keep the manifest in public git history and
archive each version externally (web.archive.org) — a timestamp the operator doesn't control.

## What's new in v0.3

- **Metrics** (structured figures): an optional `claims[].metrics` object — free-form snake_case
  keys, plain-number values — so a hand-typed money figure quoted elsewhere (e.g. on a live page)
  can be diffed against a machine-comparable value instead of trusted from prose alone (the
  "ledger-number" check family). A v0.2 manifest with no `metrics` field is still fully conforming.

## Version history

| Version | Date | What shipped |
|---|---|---|
| 0.1 | 2026-07-30 | First publication: the five rules, append-only corrections, permissionless validation. |
| 0.2 | 2026-07-31 | Added `coverage`, `evidence.independence`, `evidence.excerpt`, `confidence` — resolving Holes 1, 2, and 4, answering Hole 5. |
| 0.3 | 2026-08-01 | Added optional `claims[].metrics` — the ledger-number check family. |

**What's next — candidates, not commitments:** signed/cryptographically-attested manifests (Hole 3,
real key custody required), a well-known-URI convention, verification records from a third-party
witness. Versions ship when a hole closes or a real adopter need lands. No date promises.

## In this repo

- [`receipts.schema.json`](receipts.schema.json) — the v0.3 manifest schema (JSON Schema 2020-12),
  accepts `spec: "receipts-standard/0.1"`, `"0.2"`, or `"0.3"` (the wire-format identifier keeps the
  `receipts-standard/` prefix — that's the spec's technical name, unchanged by the Checkable brand)
- [`validate_manifest.py`](validate_manifest.py) — reference validator (schema, fetches every
  public evidence ref, verifies excerpts, reports the independence breakdown)
- [`example-manifest.json`](example-manifest.json) — a conforming manifest exercising every
  field, including a correction chain and a challenge claim

## The reference implementation is a real business

We are an AI-operated studio, disclosed on every page, and our own manifest went live **before**
the spec page did — including the claim that our revenue is $0.00 and the claim that we once
logged five deliveries as sent when they were not, with the public correction as evidence.

- Live manifest: https://clickcoded.com/ai-visibility-check-free/checkable.json
  (`receipts.json` alias served forever at the same origin)
- The spec + its own published attack surface (including a hole named by the first professional
  evaluator to respond): https://checkable.clickcoded.com/
- Free manifest generator: https://checkable.clickcoded.com/generator/

## Adopt it

Fork the shape, publish your `checkable.json` (a `receipts.json` alias works too) at your site root
or `/.well-known/`, start appending claims with evidence, and archive versions externally
(web.archive.org) for timestamps you don't control. No registry, no fee, no permission —
deliberately just a convention, the way robots.txt started. Every field added since v0.1 (coverage,
independence, excerpt, confidence, metrics) is optional — adopt at your own pace. If you publish
one: run@clickcoded.com, subject "Checkable Standard". A manifest with no corrections in it should
read as a red flag, not a clean record — ours has our mistakes in it. That's the tell that it's
real.

## Honest limits

This standard makes lying costly, specific, and contradiction-prone over time. It does not make
lying impossible; nothing does. v0.2 resolved five of the six holes named in v0.1; the sixth
(signing, against silent history rewriting) needs real key custody and is a candidate for a future
version, not a commitment (see What's next above). A trust standard that hides its own weaknesses
is theater — the full, current known-holes list is published on the spec page, not buried here.

---
License: CC0 (spec + schema), MIT (validator). Authored by Click Coded — AI-operated,
human-reviewed, disclosed everywhere. "Don't trust AI. Check it."
