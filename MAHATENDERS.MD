# MahaTenders — what we have, and how to use it in the pitch

Source: `TENDERS.zip` (PMC procurement export), audited manually — no API, no
scraping, nothing automated. Two summary spreadsheets plus one full example
tender packet. This is reference material for the pitch, not a data source
the matcher reads — MPLADS stays the only thing `app/core/matcher.py` links
against. See `CONTEXT.md` §11 and `Chatgpthandoff.md` §3.4 for why: no free
bulk API, and a tender is evidence a work was planned, not proof it was done.

## The two facts worth having ready

**1. The pipeline number.** `Tender-2024-25.xlsx` (PMC Electrical dept.
summary, FY 2024–25): **262 tenders floated, ₹335 crore**, of which **208
reached a work order** and 7 were cancelled. `Tender-2025-26.xlsx` shows 46
tenders so far this year, mostly still at bid evaluation.

  > *"This isn't just MPLADS — PMC's own tender pipeline shows 262 civic
  > works worth ₹335 crore moving through the system in one year alone.
  > That's the scale WardSentry is built to sit on top of."*

**2. The one real example.** `tenderdocs147/` is a complete tender packet:
electrical work at a PMC school (Zone 4), Work ID `E6_2026_P44939_WVB`,
estimated ₹1.52 crore, 6-month completion window, bids due 14 Aug 2026 — i.e.
**still at the bidding stage**, no work order yet. Good for showing what a
real tender record looks like, and for the point below.

## The point to make if asked "why not use tenders for matching?"

A tender at the bidding stage isn't a completed work — it isn't even a
guaranteed work yet. Answer plainly, no hedging:

  > *"A tender tells us money was allocated, not that the work happened.
  > MPLADS `completed_on` is a real completion date; a tender bid deadline
  > isn't. We treat tenders as future evidence, not a substitute."*

Never call an uncompleted tender a "funded" or "completed" work in the demo —
that's the one thing that would make this claim untrue on stage.

## If there's time before the hackathon

A teammate manually pulling 10–20 *awarded* (not just floated) tenders for
roads/drains/streetlights, each with a ward and a link to the public
MahaTenders page, would let a matched issue show "a tender was also floated
here" as **labelled, linked supporting evidence** — never as a second
completed-work source. Not required for the core demo; MPLADS alone already
delivers the differentiator.
