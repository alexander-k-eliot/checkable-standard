#!/usr/bin/env python3
"""
Build the Checkable Open sign — canonical copy, moved here from ops/design/ on
Brandon's sign-off 2026-08-02. Full design rationale, usage rules and prior-art check:
ops/DESIGN-checkable-open-sign-2026-08-02.md (that file is now historical background;
this script plus the design doc's rulings are what's binding).

Public copy calls this artifact "the sign", never "the badge" — see the design doc §11
(escalation: the phrase "Open Badges" is a real, findable standard in this category;
"the sign" sidesteps the collision for free). "Badge" stays fine in code/paths/dev-facing
copy (variable names below, the embed snippet's filename), just not in anything a reader
sees.

One geometry, one source of truth. Emits:
  out/open-<state>.svg              sign scale (260x62), concrete date, for review
  out/open-<state>.template.svg     same, with {{DATE}} for the Worker
  out/hero-<state>.svg              hero scale (600x180), the /open/ page hero
  out/mark-<state>.svg              64px square mark (the O + check alone)
  out/direction-<x>.svg             exploration sketches — regenerate on demand,
                                     not meant to live checked in here; see the ops/
                                     copy for the full contact sheet with all four.

States: lit | failing | ended (internal keys, unchanged from the registry's 3-state
enum). Printed labels are VALIDATED / NOT VALIDATED SINCE / NOT CHECKED SINCE.

DATE SEMANTICS — decided 2026-08-02, binds whoever wires this to real data: every
state prints the LAST-CONFORMING date, never the date a failure was confirmed. That is
the only way "NOT VALIDATED SINCE <date>" is a true sentence, and it is also the more
useful number for a reader (how stale is this proof). The internal 14-day delisting
clock runs on its own separate confirmed-failure timestamp and is unaffected — this
only governs what date gets interpolated into {{DATE}} on the public sign/page.

The neon word is drawn as STROKED PATHS, never <text>. Two reasons: a neon tube is a
bent glass tube (uniform width, round caps, continuous glyph) and text can't be that;
and an SVG served to a third-party page can't load a webfont, so the one brand-critical
element must not depend on one. Only the dated readout uses <text>, on the generic
monospace stack the house already declares as its fallback.

Run: python3 build_open_sign.py
"""

import os
import re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ── Palette (from ventures/agentready/receipts-standard/assets/system.css) ──────
INK      = "#f4eee1"
DIM      = "#9fbcba"
MINT     = "#2ee6a8"
AMBER    = "#f5b942"
PANEL    = "#08323b"   # badge body
GLASS    = "#04222a"   # the window pane
LINE     = "rgba(238,246,244,.14)"
LINE_SFT = "rgba(238,246,244,.08)"
TUBE_OFF = "#3c5f68"   # unlit glass tube
TUBE_END = "#33525a"   # unlit, monitoring ended (a touch dimmer)
CORE     = "#d9fff1"   # the hot centre of a lit tube

MONO = "ui-monospace,'IBM Plex Mono',SFMono-Regular,Menlo,Consolas,monospace"

# ── The letterforms ────────────────────────────────────────────────────────────
# "OPEN" on a 26-unit cap height, block 0..91.5 wide. Drawn the way a sign shop
# bends it: one tube per letter, uniform stroke, round caps.
TUBE_PATHS = (
    '<rect x="0" y="0" width="23" height="26" rx="11.5"/>'
    '<path d="M30 26 V0 H39 A6.5 6.5 0 0 1 39 13 H30"/>'
    '<path d="M68.5 0 H52.5 V26 H68.5"/>'
    '<path d="M52.5 13 H65"/>'
    '<path d="M75.5 26 V0 L94.5 26 V0"/>'
)
# The check, held inside the O the way the dot is held between the chevrons of the house
# mark: centred, contained, never touching the walls. Bent from thinner tube, which is
# what a real sign shop does for detail work inside a letter.
#
# TICK_FIT is the clearance ratio, and it is the whole design of this element. The house
# mark leaves ~28% of the bracket gap clear on each side of its dot; a check needs more
# width than a dot to read, so this lands at ~25% and reads with the same air. Anything
# larger crowds the ring, which shows up first and worst on an unlit sign, where there is
# no glow to separate the two tubes.
TICK_FIT = 0.77
TICK_PATH = ('<g transform="translate(11.5,13) scale(%.2f) translate(-11.5,-13)">'
             '<path d="M7 12.9 L10.3 16.3 L15.6 9.7"/></g>' % TICK_FIT)
TUBE_W, TUBE_H = 94.5, 26.0

# The house mark: two chevrons and a dot. Never changes between states — it is the
# attester, not the fact. Drawn on its native 64-unit grid, scaled at the call site.
def chevron(x, y, size, colour, weight=5):
    # weight is on the 64-unit grid. Small renders need a heavier tube or the mark
    # dissolves; the house's own small-size mask uses 7 for exactly this reason.
    s = size / 64.0
    return (
        f'<g transform="translate({x:g},{y:g}) scale({s:g})" fill="none" stroke="{colour}" '
        f'stroke-width="{weight:g}" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M24 18 L12 32 L24 46"/><path d="M40 18 L52 32 L40 46"/>'
        f'<circle cx="32" cy="32" r="3.5" fill="{colour}" stroke="none"/></g>'
    )

# The tube block's true bounding box, stroke included. Every placement below is derived
# from this rather than nudged by eye: at scale S the block occupies
#   (tx - 2.6S, ty - 2.6S) .. (tx + 97.1S, ty + 28.6S)
# so centring it in a box is one line of arithmetic, and it stays correct if the
# letterforms ever change.
TUBE_PAD = 2.6                       # half the 5.2 stroke
TUBE_BOX = (TUBE_W + 5.2, TUBE_H + 5.2)     # 99.7 x 31.2
O_BOX    = (23 + 5.2, TUBE_H + 5.2)         # 28.2 x 31.2, the O on its own


def centre(box_w, box_h, x0, y0, w, h, scale):
    """Top-left translate that centres a `box` of local size (w,h) inside the rect
    (x0,y0,box_w,box_h) at `scale`. Returns the translate for the path origin."""
    return (x0 + (box_w - w * scale) / 2 + TUBE_PAD * scale,
            y0 + (box_h - h * scale) / 2 + TUBE_PAD * scale)


# ── State table ────────────────────────────────────────────────────────────────
# Only three things change between states: the tube, the pilot lamp, the readout.
# The mark and the wordmark are identical in all three, deliberately.
STATES = {
    "lit": {
        "label": "VALIDATED",
        "label_colour": MINT,
        "date_colour": INK,
        "pilot": "solid",
        "pilot_colour": MINT,
        "aria": "Checkable Open: validated {date}.",
        "mark_aria": "Checkable Open, lit",
        "title": "Checkable Open: validated {date}",
    },
    "failing": {
        "label": "NOT VALIDATED SINCE",
        "label_colour": AMBER,
        "date_colour": INK,
        "pilot": "ring",
        "pilot_colour": AMBER,
        "aria": "Checkable Open: not validated since {date}.",
        "mark_aria": "Checkable Open, dark: not validated",
        "title": "Checkable Open: not validated since {date}",
    },
    "ended": {
        "label": "NOT CHECKED SINCE",
        "label_colour": DIM,
        "date_colour": DIM,
        "pilot": "dash",
        "pilot_colour": DIM,
        "aria": "Checkable Open: not checked since {date}.",
        "mark_aria": "Checkable Open, dark: not checked",
        "title": "Checkable Open: not checked since {date}",
    },
}


def pilot(kind, cx, cy, r, colour, glow=False):
    """Pilot lamp. Three distinct silhouettes so the state survives grayscale:
    filled (lit) / hollow ring (failing, powered but not lit) / dash (ended)."""
    g = f' filter="url(#bloom)"' if glow else ""
    if kind == "solid":
        return (f'<circle cx="{cx:g}" cy="{cy:g}" r="{r*1.7:g}" fill="{colour}" opacity=".22"{g}/>'
                f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{colour}"/>')
    if kind == "ring":
        return (f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" '
                f'stroke="{colour}" stroke-width="{r*0.46:g}"/>')
    return (f'<rect x="{cx-r:g}" y="{cy-r*0.24:g}" width="{r*2:g}" height="{r*0.48:g}" '
            f'rx="{r*0.24:g}" fill="{colour}"/>')


def tube(state, x, y, scale, detail=False):
    """The sign itself, in two gauges: the letters on a 5.2 tube, the check inside the O
    on a 2.6 tube. Lit = stacked strokes (halo, bloom, tube, hot core). Dark = one flat
    stroke, no glow, no colour. The difference is luminance plus the presence of a blur
    field, so it holds in grayscale as well as in colour.

    The check gets no wide halo. At badge size that halo would fill the O's cavity and
    the letter would stop reading as an O."""
    sw = 5.2 * scale
    tw = 2.3 * scale
    xf = f'transform="translate({x:g},{y:g}) scale({scale:g})"'
    d = (f'<defs>'
         f'<filter id="tg{state}" x="-90%" y="-90%" width="280%" height="280%">'
         f'<feGaussianBlur stdDeviation="{tw*0.4:g}"/></filter>'
         f'<g id="tube{state}" fill="none" stroke-linecap="round" stroke-linejoin="round">'
         f'<g {xf}>{TUBE_PATHS}</g></g>'
         f'<g id="tick{state}" fill="none" stroke-linecap="round" stroke-linejoin="round">'
         f'<g {xf}>{TICK_PATH}</g></g>'
         f'</defs>')
    u = lambda i, c, w, o, f="": (f'<use href="#{i}{state}" xlink:href="#{i}{state}" stroke="{c}" '
                                  f'stroke-width="{w:g}" opacity="{o}"{f}/>')
    if state == "lit":
        body = (u("tube", MINT, sw * 1.55, ".28", ' filter="url(#halo)"')
                + u("tube", MINT, sw * 1.08, ".8", ' filter="url(#bloom)"')
                + u("tube", MINT, sw, "1")
                + u("tube", CORE, sw * 0.42, "1")
                + u("tick", MINT, tw * 1.5, ".55", f' filter="url(#tg{state})"')
                + u("tick", MINT, tw, "1")
                + u("tick", CORE, tw * 0.4, "1"))
        if detail:
            body += u("tube", CORE, sw * 0.18, ".9")
        return d + body
    off = TUBE_OFF if state == "failing" else TUBE_END
    # A hint of glass thickness down the middle of the tube, so an unlit sign reads as
    # unlit GLASS rather than as grey lettering. Kept faint enough to disappear rather
    # than muddy at small sizes.
    hi = sw * (0.2 if detail else 0.26)
    body = (u("tube", off, sw, "1") + u("tube", "#5c848d", hi, ".45")
            + u("tick", off, tw, "1"))
    return d + body


# ── The mark: the O and its check, alone, in a square ──────────────────────────
def mark(state, size=64):
    """Brandon's call: the O with the check inside is a complete mark on its own. Same
    object, same three states, same two tube gauges — just the one letter, in a square
    pane. Favicon, registry row, avatar, OG element. The badge stays the full lockup."""
    lit = state == "lit"
    s_ = STATES[state]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{size}" height="{size}" viewBox="0 0 64 64" role="img" '
         f'aria-label="{s_["mark_aria"]}">',
         f'<title>{s_["mark_aria"]}</title>',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%">'
         '<feGaussianBlur stdDeviation="3.4"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
         '<feGaussianBlur stdDeviation="1.3"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="48%" r="52%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".2"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         '<clipPath id="sq"><rect x="0" y="0" width="64" height="64" rx="14"/></clipPath>'
         '</defs>',
         f'<rect x=".6" y=".6" width="62.8" height="62.8" rx="13.4" fill="{GLASS}" stroke="{LINE}"/>',
         '<g clip-path="url(#sq)">']
    if lit:
        o.append('<ellipse cx="32" cy="30" rx="34" ry="32" fill="url(#spill)"/>')
    # only the O and its check, from the same source geometry
    mx, my = centre(64, 64, 0, 0, *O_BOX, 1.35)
    o.append(_one_letter(state, mx, my, 1.35))
    o.append('</g></svg>')
    return "".join(o)


def _one_letter(state, x, y, scale):
    """The O plus its check, sharing tube()'s layer stack but with the other letters
    dropped. Same defs shape so the two files can never drift apart."""
    full = tube(state, x, y, scale)
    only_o = ('<rect x="0" y="0" width="23" height="26" rx="11.5"/>')
    return full.replace(TUBE_PATHS, only_o)


# ── Direction A: "The Window Pane" — the recommendation ────────────────────────
def badge(state, date, template=False):
    s = STATES[state]
    W, H = 260, 62
    lit = state == "lit"
    date_txt = "{{DATE}}" if template else date
    aria = s["aria"].format(date="{{DATE}}" if template else date)
    title = s["title"].format(date="{{DATE}}" if template else date)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{aria}">',
         f'<title>{title}</title>',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%">'
         '<feGaussianBlur stdDeviation="5.5"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
         '<feGaussianBlur stdDeviation="2"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="50%" r="50%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".17"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="body"><rect x="0" y="0" width="{W}" height="{H}" rx="9"/></clipPath>'
         '</defs>']

    # badge body
    o.append(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="8.5" fill="{PANEL}" stroke="{LINE}"/>')

    # the glass
    o.append(f'<g clip-path="url(#body)">')
    o.append(f'<rect x="8" y="7" width="112" height="48" rx="6" fill="{GLASS}" stroke="{LINE_SFT}"/>')
    if lit:
        o.append('<ellipse cx="64" cy="30" rx="60" ry="27" fill="url(#spill)"/>')
    tx, ty = centre(112, 48, 8, 7, *TUBE_BOX, 0.94)
    o.append(tube(state, tx, ty, 0.94))
    o.append('</g>')

    # mullion between glass and plaque
    o.append(f'<path d="M131.5 12 V50" stroke="{LINE_SFT}" stroke-width="1"/>')

    # the plaque: who says so, and the dated fact.
    # Same two-column rule as hero() — see the long note there. The wordmark used to
    # sit at 162 while the label and date sat at 155, three left edges in a block of
    # three lines. 155 is the one that survives: "NOT VALIDATED SINCE" runs 96 units
    # at this size, so aligning on 162 would leave under 2 units of panel edge in the
    # failing state. The marks move left to open a gap the wordmark no longer fills.
    TEXT_X, MARK_X = 155.0, 140.3
    CHEV_SIZE, CHEV_W, PILOT_R = 14, 6.6, 3.1
    chev_x = MARK_X - (12 - CHEV_W / 2) * (CHEV_SIZE / 64.0)
    pilot_cx = MARK_X + PILOT_R

    o.append(chevron(chev_x, 11.4, CHEV_SIZE, MINT, weight=CHEV_W))
    o.append(f'<text x="{TEXT_X:g}" y="21.5" font-family="{MONO}" font-size="8.6" letter-spacing=".07em" '
             f'fill="{INK}" font-weight="600">CHECKABLE OPEN</text>')
    o.append(pilot(s["pilot"], pilot_cx, 31, PILOT_R, s["pilot_colour"], glow=lit))
    o.append(f'<text x="{TEXT_X:g}" y="33.7" font-family="{MONO}" font-size="7.4" letter-spacing=".085em" '
             f'fill="{s["label_colour"]}" font-weight="600">{s["label"]}</text>')
    o.append(f'<text x="{TEXT_X:g}" y="46.8" font-family="{MONO}" font-size="10.2" letter-spacing=".02em" '
             f'fill="{s["date_colour"]}">{date_txt}</text>')
    o.append('</svg>')
    return "".join(o)


# ── Direction A at hero scale ──────────────────────────────────────────────────
def hero(state, date):
    s = STATES[state]
    W, H = 600, 180
    lit = state == "lit"
    aria = s["aria"].format(date=date)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{aria}">',
         f'<title>{s["title"].format(date=date)}</title>',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%">'
         '<feGaussianBlur stdDeviation="14"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
         '<feGaussianBlur stdDeviation="5"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="46%" r="52%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".2"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="pane"><rect x="22" y="26" width="300" height="128" rx="16"/></clipPath>'
         f'<clipPath id="body"><rect x="0" y="0" width="{W}" height="{H}" rx="16"/></clipPath>'
         '</defs>']

    # The SIGN is a true scale of the badge's sign: k = 300/112, applied to the pane,
    # the tube, and the sill alike, so the object is identical and only bigger. The
    # PLAQUE is re-set, because a hero's text block has different proportions than a
    # 260px strip. That is the honest version of "one design, two scales".
    k = 300 / 112.0
    px = lambda v: 22 + (v - 8) * k     # badge pane x -> hero x
    py = lambda v: 26 + (v - 7) * k     # badge pane y -> hero y

    o.append(f'<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="15.25" fill="{PANEL}" stroke="{LINE}"/>')
    o.append('<g clip-path="url(#body)">')
    o.append(f'<rect x="22" y="26" width="300" height="128" rx="16" fill="{GLASS}" stroke="{LINE_SFT}"/>')
    # glass thickness: an inner reveal, invisible at badge size, right at hero size
    o.append(f'<rect x="29" y="33" width="286" height="114" rx="10" fill="none" stroke="{LINE_SFT}"/>')
    if lit:
        o.append('<ellipse cx="172" cy="90" rx="158" ry="70" fill="url(#spill)"/>')
    bx, by = centre(112, 48, 8, 7, *TUBE_BOX, 0.94)
    o.append(tube(state, px(bx), py(by), 0.94 * k, detail=True))
    o.append('<g clip-path="url(#pane)">')
    # a faint sheen across the glass
    o.append('<path d="M22 128 L134 26 L190 26 L22 154 Z" fill="#eef6f4" opacity=".03"/>')
    o.append('</g></g>')

    # The plaque is a two-column lockup, and both columns are computed, not eyeballed
    # (Brandon, 2026-08-02: the three text lines must left-align perfectly). Before
    # this, the wordmark sat at 406.7 while the label and date sat at 388.7, so the
    # block had three different left edges and read as drift rather than structure.
    #
    #   TEXT_X  every line of type starts here. All three. No exceptions.
    #   MARK_X  the visible left edge of the leading marks (chevron, pilot lamp),
    #           which hang in the gutter to the left of the type.
    #
    # The marks have different widths, so their right-hand gaps differ. That is
    # correct: what the eye reads in a lockup is the two vertical edges, not the
    # gaps. Both marks are placed from their own true geometry so the alignment
    # survives any future change to the glyphs.
    # TEXT_X is the LEFT of the old three, not the right, and that is load-bearing.
    # The longest string any state prints is "NOT VALIDATED SINCE" at 189.3 units
    # wide. Aligning the block on the old wordmark position (406.7) put that label
    # 4 units from the panel edge in the failing state. At 388.7 it clears by 22,
    # which is also the glass pane's left inset, so the plaque breathes the same on
    # both sides. Check this if the labels are ever reworded: a longer string moves
    # this number, and the dark states are where it bites.
    TEXT_X, MARK_X = 388.7, 361.0
    CHEV_SIZE, PILOT_R = 24, 7
    # chevron: the 64-unit artwork's visible left edge sits at 9.5 (path x=12 minus
    # half the 5-unit stroke), so the translate origin is offset back by that much.
    chev_x = MARK_X - 9.5 * (CHEV_SIZE / 64.0)
    pilot_cx = MARK_X + PILOT_R

    o.append(f'<path d="M347 40 V140" stroke="{LINE_SFT}" stroke-width="1"/>')
    o.append(chevron(chev_x, 41, CHEV_SIZE, MINT))
    o.append(f'<text x="{TEXT_X:g}" y="59" font-family="{MONO}" font-size="16.5" letter-spacing=".07em" '
             f'fill="{INK}" font-weight="600">CHECKABLE OPEN</text>')
    o.append(pilot(s["pilot"], pilot_cx, 89.3, PILOT_R, s["pilot_colour"], glow=lit))
    o.append(f'<text x="{TEXT_X:g}" y="94.5" font-family="{MONO}" font-size="14.5" letter-spacing=".085em" '
             f'fill="{s["label_colour"]}" font-weight="600">{s["label"]}</text>')
    o.append(f'<text x="{TEXT_X:g}" y="132.5" font-family="{MONO}" font-size="27" letter-spacing=".01em" '
             f'fill="{s["date_colour"]}">{date}</text>')
    o.append('</svg>')
    return "".join(o)


# ── The alternates, lit state only, for the contact sheet ──────────────────────
def direction_b(date):
    """B — One Pane. Everything inside the glass: the mark and the readout are
    printed on the glass, only OPEN glows. Tests whether the attribution belongs
    inside or outside the window."""
    W, H = 260, 62
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Direction B sketch: one pane">',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="5.5"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="42%" r="52%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".16"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="bodyb"><rect x="0" y="0" width="{W}" height="{H}" rx="9"/></clipPath></defs>',
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="8.5" fill="{GLASS}" stroke="{LINE}"/>',
         '<g clip-path="url(#bodyb)">',
         '<ellipse cx="130" cy="26" rx="120" ry="30" fill="url(#spill)"/>',
         tube("lit", 82.75, 8.5, 1.0),
         '</g>',
         f'<path d="M14 44 H246" stroke="{LINE_SFT}" stroke-width="1"/>',
         chevron(14, 47, 11, MINT),
         f'<text x="29" y="55.5" font-family="{MONO}" font-size="7" letter-spacing=".07em" '
         f'fill="{DIM}" font-weight="600">CHECKABLE OPEN</text>',
         f'<text x="246" y="55.5" text-anchor="end" font-family="{MONO}" font-size="7.6" '
         f'letter-spacing=".03em" fill="{DIM}">VALIDATED {date}</text>',
         '</svg>']
    return "".join(o)


def direction_b2(date):
    """B2 — Full Neon Wordmark. The whole lockup inside the tube. Sketch fidelity:
    CHECKABLE is <text> with a glow filter, not real tube geometry, because the
    point of the test is the LOCKUP, not the letterforms."""
    W, H = 260, 62
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Direction B2 sketch: full neon wordmark">',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="5.5"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>'
         '<filter id="tglow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.4"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="46%" r="52%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".16"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="bodyc"><rect x="0" y="0" width="{W}" height="{H}" rx="9"/></clipPath></defs>',
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="8.5" fill="{GLASS}" stroke="{LINE}"/>',
         '<g clip-path="url(#bodyc)">',
         '<ellipse cx="130" cy="26" rx="120" ry="30" fill="url(#spill)"/>',
         f'<text x="130" y="20" text-anchor="middle" font-family="{MONO}" font-size="11.5" '
         f'letter-spacing=".22em" fill="{MINT}" font-weight="700" filter="url(#tglow)">CHECKABLE</text>',
         f'<text x="130" y="20" text-anchor="middle" font-family="{MONO}" font-size="11.5" '
         f'letter-spacing=".22em" fill="{CORE}" font-weight="700">CHECKABLE</text>',
         tube("lit", 95.97, 24, 0.72),
         '</g>',
         f'<text x="130" y="57" text-anchor="middle" font-family="{MONO}" font-size="6.8" '
         f'letter-spacing=".08em" fill="{DIM}">VALIDATED {date}</text>',
         '</svg>']
    return "".join(o)


def direction_c(date):
    """C — Hanging Sign. The sign as a suspended object: rail, cords, hooks."""
    W, H = 260, 78
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Direction C sketch: hanging sign">',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="5.5"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="50%" r="50%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".17"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="bodyd"><rect x="0" y="0" width="{W}" height="{H}" rx="9"/></clipPath></defs>',
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="8.5" fill="{PANEL}" stroke="{LINE}"/>',
         # the rail it hangs from
         f'<path d="M10 12 H250" stroke="{LINE}" stroke-width="1.6" stroke-linecap="round"/>',
         chevron(12, 3, 17, MINT),
         f'<text x="34" y="9.5" font-family="{MONO}" font-size="7" letter-spacing=".09em" '
         f'fill="{DIM}" font-weight="600">CHECKABLE OPEN</text>',
         # cords
         f'<path d="M46 12 V22" stroke="{LINE}" stroke-width="1.2"/>',
         f'<path d="M110 12 V22" stroke="{LINE}" stroke-width="1.2"/>',
         '<g clip-path="url(#bodyd)">',
         f'<rect x="24" y="22" width="108" height="44" rx="6" fill="{GLASS}" stroke="{LINE_SFT}"/>',
         '<ellipse cx="78" cy="44" rx="58" ry="25" fill="url(#spill)"/>',
         tube("lit", 33.59, 31, 0.94),
         '</g>',
         pilot("solid", 152, 38, 3.1, MINT, glow=True),
         f'<text x="160" y="41.3" font-family="{MONO}" font-size="7" letter-spacing=".11em" '
         f'fill="{MINT}" font-weight="600">VALIDATED</text>',
         f'<text x="160" y="55" font-family="{MONO}" font-size="9.5" letter-spacing=".02em" '
         f'fill="{INK}">{date}</text>',
         '</svg>']
    return "".join(o)


def direction_d(date):
    """D — The Sill. Vertical: the tube rests on a sill, the fact engraved below."""
    W, H = 190, 120
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Direction D sketch: the sill">',
         '<defs>'
         '<filter id="halo" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="5.5"/></filter>'
         '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>'
         '<radialGradient id="spill" cx="50%" cy="50%" r="50%">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".18"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></radialGradient>'
         '<linearGradient id="sd" x1="0" y1="0" x2="0" y2="1">'
         f'<stop offset="0" stop-color="{MINT}" stop-opacity=".2"/>'
         f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/></linearGradient>'
         f'<clipPath id="bodye"><rect x="0" y="0" width="{W}" height="{H}" rx="9"/></clipPath></defs>',
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="8.5" fill="{PANEL}" stroke="{LINE}"/>',
         '<g clip-path="url(#bodye)">',
         '<ellipse cx="95" cy="40" rx="86" ry="34" fill="url(#spill)"/>',
         tube("lit", 47.75, 26, 1.0),
         '<rect x="0" y="64" width="190" height="14" fill="url(#sd)"/>',
         f'<path d="M20 64 H170" stroke="{MINT}" stroke-width="1.6" stroke-linecap="round" opacity=".55"/>',
         '</g>',
         chevron(20, 78, 13, MINT),
         f'<text x="37" y="88" font-family="{MONO}" font-size="7" letter-spacing=".08em" '
         f'fill="{INK}" font-weight="600">CHECKABLE OPEN</text>',
         pilot("solid", 23.5, 100, 3.1, MINT, glow=True),
         f'<text x="32" y="103.3" font-family="{MONO}" font-size="7" letter-spacing=".11em" '
         f'fill="{MINT}" font-weight="600">VALIDATED</text>',
         f'<text x="170" y="103.6" text-anchor="end" font-family="{MONO}" font-size="9.5" '
         f'letter-spacing=".02em" fill="{INK}">{date}</text>',
         '</svg>']
    return "".join(o)


def main():
    os.makedirs(OUT, exist_ok=True)
    demo = {"lit": "2026-08-02", "failing": "2026-07-29", "ended": "2026-07-29"}
    written = []

    for st, d in demo.items():
        for name, svg in (
            (f"open-{st}.svg", badge(st, d)),
            (f"open-{st}.template.svg", badge(st, d, template=True)),
            (f"hero-{st}.svg", hero(st, d)),
            # Worker-ready hero, added 2026-08-02 launch audit: the offer page
            # hero is served live from /open/clickcoded.com/hero.svg rather than
            # as a baked-date file, because a monitoring product whose own hero
            # shows a stale "validated" date is the exact failure it warns about.
            (f"hero-{st}.template.svg", hero(st, "{{DATE}}")),
        ):
            p = os.path.join(OUT, name)
            with open(p, "w") as f:
                f.write(svg + "\n")
            written.append(name)

    for st in demo:
        p = os.path.join(OUT, f"mark-{st}.svg")
        with open(p, "w") as f:
            f.write(mark(st) + "\n")
        written.append(f"mark-{st}.svg")

    for name, svg in (
        ("direction-a.svg", badge("lit", "2026-08-02")),
        ("direction-b.svg", direction_b("2026-08-02")),
        ("direction-b2.svg", direction_b2("2026-08-02")),
        ("direction-c.svg", direction_c("2026-08-02")),
        ("direction-d.svg", direction_d("2026-08-02")),
    ):
        p = os.path.join(OUT, name)
        with open(p, "w") as f:
            f.write(svg + "\n")
        written.append(name)

    # Templates must carry the placeholders and nothing stale.
    for st in demo:
        t = open(os.path.join(OUT, f"open-{st}.template.svg")).read()
        assert "{{DATE}}" in t, f"{st} template lost its placeholder"
        assert not re.search(r"20\d\d-\d\d-\d\d", t), f"{st} template still carries a literal date"

    print(f"wrote {len(written)} files to {OUT}")
    for n in sorted(written):
        print("  ", n)


if __name__ == "__main__":
    main()
