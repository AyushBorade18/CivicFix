# DEMO.md — the 90 seconds we are building toward

Everything in the repo serves this script. If a feature does not appear here,
it does not get built today.

---

## The script

**[0:00 — the pile]**
"This is Kothrud ward. 214 complaints over four months, as a municipal system
would hold them — one row each, no structure."

*Screen: raw complaint table, deliberately messy.*

**[0:15 — the collapse]**
"Our clustering runs on text, distance and time. 214 reports become 31 issues."

*Screen: click Run. Table collapses. Counter updates live.*

**[0:30 — the recurring one]**
"This one is a drainage failure on <street>. It has been reported 14 times,
across three separate months. It was marked resolved twice."

*Screen: open the issue. Show the 14 linked reports and the two prior closures.*

**[0:50 — the link — THIS IS THE DEMO]**
"So we asked a question the brief doesn't ask. Was public money already spent
here? This is a real MPLADS record: a sanctioned drainage work at this location,
completed <date>, <amount>, implementing agency <name>."

*Screen: the work record beside the issue. Match reason and confidence visible.*

**[1:10 — the restraint]**
"We do not call this fraud. We produce a verification case: the issue, the work,
the dates, the records. A human decides. Priority is a published formula, not a
model — here are the weights, and here is why this issue ranked where it did."

*Screen: priority breakdown expanded.*

**[1:25 — the close]**
"Others manage complaints. We connect a complaint to the public work already
funded to prevent it."

---

## What is real vs seeded vs out of scope — say this if asked, don't wait to be caught

- **Real:** MPLADS records, the classifier's training data (NYC 311), the
  clustering and matching logic, the priority formula, all computed live.
- **Seeded, labelled as such:** ~400 synthetic Pune complaints, deliberately
  placed near real MPLADS locations so links are findable. The UI marks these.
- **Built since this script was written (verify against `CONTEXT.md` before
  the demo, this file is stale on scope):** multilingual intake (Hindi/Marathi,
  romanized and code-mixed, via the fine-tuned encoder — no translation
  step needed for classification).
- **Not built today, shown only in the deck:** WhatsApp/call-centre intake,
  confirm-before-dispatch, reviewer console, SLA tracking. If asked, say
  plainly: "that's architecture, not built in this prototype — here's what we
  prioritised instead and why."
- **MahaTenders:** audited manually, not wired into matching — see
  `MAHATENDERS.MD` for the two numbers worth citing and why a tender isn't
  treated as a completed work.

---

## What must be true for this to work

- [ ] MPLADS loaded with geometry, queryable by location
- [ ] ~200 synthetic complaints seeded **near real MPLADS work locations**
      so that links are genuinely findable
- [ ] Clustering runs live on button press, not precomputed
- [ ] At least 3 convincing issue→work matches exist (not 1 — you need spares)
- [ ] One unseen complaint can be added live and clustered correctly
- [ ] Priority breakdown renders per issue

## The question we will be asked

"Run it again with something I choose."

Keep a second ward, or a held-out complaint, ready. Being able to do this once,
live, is worth more than any additional feature.

## The sentence we say before they ask

"Matching is right on roughly <N> of our <M> test cases. Here is one it gets
wrong, and why."