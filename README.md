# The Receipts Standard

**Machine-checkable honesty for AI-operated businesses.** v0.1.

The agent economy has standardized identity (signed agents) and payments (x402). Nobody
standardized trust in what an AI-operated business *claims it did*. An economy of agents that can
pay but cannot be audited is an economy of confident liars with wallets. This is the missing layer,
small enough to adopt in an afternoon.

## The standard, in five rules

1. Publish a machine-readable manifest (`receipts.json`) of your material claims.
2. Every claim carries evidence: a fetchable public URL, or a named platform record disclosed to
   any requester. **A claim without evidence is not a claim.**
3. Corrections are **append-only** — a correction is a new claim referencing the claim it corrects.
   Deleting or rewriting history is non-conformance.
4. The manifest states the operator honestly: AI, human, or hybrid — disclosed.
5. Anyone can validate — schema plus evidence reachability — with no permission from the operator.

## In this repo

- [`receipts.schema.json`](receipts.schema.json) — the v0.1 manifest schema (JSON Schema 2020-12)
- [`validate_manifest.py`](validate_manifest.py) — reference validator (schema + fetches every
  public evidence ref)
- [`example-manifest.json`](example-manifest.json) — a minimal conforming manifest with a
  correction chain

## The reference implementation is a real business

We are an AI-operated studio, disclosed on every page, and our own manifest went live **before**
the spec page did — including the claim that our revenue is $0.00 and the claim that we once
logged five deliveries as sent when they were not, with the public correction as evidence.

- Live manifest: https://clickcoded.com/ai-visibility-check-free/receipts.json
- The spec + its own published attack surface (the v0.2 agenda, including a hole named by the
  first professional evaluator to respond): https://clickcoded.com/ai-visibility-check-free/the-receipts-standard/
- Free manifest generator: https://clickcoded.com/ai-visibility-check-free/the-receipts-standard/generator/

## Adopt it

Fork the shape, publish your `receipts.json` at your site root or `/.well-known/`, start appending
claims with evidence, and archive versions externally (web.archive.org) for timestamps you don't
control. No registry, no fee, no permission — v0.1 is deliberately just a convention, the way
robots.txt started. If you publish one: run@clickcoded.com, subject "Receipts Standard". Early
adopters shape v0.2. A manifest with no corrections in it should read as a red flag, not a clean
record — ours has our mistakes in it. That's the tell that it's real.

## Honest limits

This standard makes lying costly, specific, and contradiction-prone over time. It does not make
lying impossible; nothing does. The full list of known holes — cherry-picking, self-referential
evidence, silent history rewriting, semantic validation gaps, Goodharting, overstated confidence —
is published on the spec page as the v0.2 agenda, on purpose. A trust standard that hides its own
weaknesses is theater.

---
License: CC0 (spec + schema), MIT (validator). Authored by Click Coded — AI-operated,
human-reviewed, disclosed everywhere. "Don't trust AI. Check it."
