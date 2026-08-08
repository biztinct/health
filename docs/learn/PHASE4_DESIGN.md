# Phase 4 — OPS and FINANCE

Module: **`health_learn`** → `19.0.5.0.0` · same engine, new content
Clinical is **excluded on purpose**: those views are being redesigned, and
teaching a screen that is about to change is work thrown away.

---

## 1. What the re-derivation found

Read from the database, not from the XML, for the same reason as Phase 1: role
gating lives in `access_role` rows with no xml-id.

| | CRM (done) | OPS | FINANCE |
|---|---|---|---|
| Leaves | 8 | **9** | **14** (11 + 3 under AR Management) |
| Audience | CRM / Reception | **Operations Manager** | **Accountant** |
| Gating | Owner + CRM | Operations Manager + Owner | Accountant + Owner |
| Exceptions | — | Clients also allows CRM | Invoices also allows Ops Manager |

**OPS:** Dashboard · Bookings · Clients · Time Off · Staff Schedule ·
Collections · Workload · Family Inbox · Route Feasibility

**FINANCE:** Dashboard · Invoices · Account Payment · Cash In Transit ·
Refund / Credit · AR Dashboard · AR Management · Payments · Overdue Clients ·
VAT Log · AR Transactions · BHYT Claims · Service Packages · Red Invoice Log

### Three findings that change the design

**1. The learner is a different person.** Every CRM lesson is written to a
reception operator working a queue. OPS is written to a manager who allocates
people and time; FINANCE to an accountant who moves money. The voice, the
worked example and the risky actions are all different — this is **not** the
CRM content with the nouns swapped.

**2. For most staff these screens are `no_access`, and that is the common
case.** A nurse has neither. The Coach already answers that honestly, and the
Journey already marks a station "not in your sidebar" — so the machinery is
right, but Phase 4 will exercise it far harder than CRM did. **Every outline
must be readable by someone who cannot open the screen**, because that is who
is most likely to be reading it.

**3. The risky actions are in a different league.** CRM's worst case was a
message that cannot be recalled. Here:

| Action | Why it is worse |
|---|---|
| `account_move.action_post` | Locks a legal sequence. Not undoable — only reversible by a credit note, which is itself a document |
| `action_redinvoice_cancel` | A **Viettel V-Invoice**: a Vietnamese tax document. Cancelling and reissuing is a filing event, not an edit |
| `action_create_refund` (×3 paths) | Moves money back. Prepaid, package and transaction refunds are three different routes with three different consequences |
| `action_collect_payment` / Cash In Transit | Cash that exists physically and must reconcile |
| `action_cancel_booking` | A nurse's day, a patient's expectation, and the revenue behind it |
| BHYT Claims | An insurance submission against a patient's entitlement |

**This is where the consequence card earns its place.** In CRM it was a good
habit; in FINANCE it is the difference between an edit and a filing.

---

## 2. Scope, and the recommended sequence

23 leaves against CRM's 8 — roughly **three times the content**, and the
FINANCE half needs facts I should confirm rather than infer (VAT treatment,
when a red invoice may be reissued, what BHYT rejection looks like).

**Recommended: OPS first, complete and reviewed, then FINANCE.** Same reason
the CRM section was worth doing before this one — you review a finished
section and tell me what to change before the pattern is repeated 14 more
times.

### OPS (this phase)

- 9 stations, all with outlines written for someone who cannot open the screen.
- **2 flagship lessons**: **Staff Schedule** (the screen an Ops Manager lives
  in) and **Bookings** (where the risky actions are).
- **1 flagship mission**: reassign a booking when a nurse calls in sick —
  consequence interception on cancel, a seeded anomaly, and an undo.
- Column glossary for all 9.
- Coach intents: ~12, weighted to "why can't I do X" since the gating is tight.

### FINANCE (next phase)

Same shape, but I will want answers on the money questions before writing —
listed in §5.

---

## 3. The worked example

CRM's example was one conversation whose numbers reconciled across four
screens. OPS needs its own: **one day in one catchment area**, where the
booking count on the Dashboard, the rows on Bookings, the assignments on Staff
Schedule and the load on Workload are all the same day seen four ways — and
where one nurse calling in sick moves all four.

That single day is what makes "reassign a booking" teachable, because the
learner can watch the consequence land on the other three screens.

**Fixture, not the tenant** — same rule as CRM (analysis §8), and the same
contract checks: every OPS number the tutorial asserts gets an entry in
`contract.json` pointing at the model that computes it.

---

## 4. What is reused unchanged

Everything structural. `learn.station`, `learn.lesson`, `learn.column`,
`learn.intent`, `learn.mission` are all line-agnostic already — Phase 4 adds
**rows, not columns**. The `section` field on `learn.station` exists for
exactly this and currently only ever holds `crm`.

New work is: content, ~20 practice screens in the replica, anchors for them,
and per-screen entries in `learn.screen` so the Coach can ground.

**The replica is the honest cost.** Nine OPS screens have to be drawn well
enough to be recognisable. That is the bulk of the engineering in this phase,
and it is why the estimate is not "just content".

---

## 5. Open questions — FINANCE only, needed before that half is written

1. **Red Invoice**: under what circumstances may one be cancelled and
   reissued, and who is allowed to? This is the single most consequential
   action in the product and I will not write a consequence card from a guess.
2. **VAT Log**: is it a record of what was filed, or a working document?
3. **BHYT Claims**: what does a rejection look like operationally, and who
   fixes it?
4. **Cash In Transit**: who reconciles it, and what happens when it does not
   balance?
5. **Refunds**: prepaid, package and transaction are three code paths — are
   they three different business situations, or one with three entry points?

None of these block OPS.
