# SAAS H4d — what a clinic pays, what happens when they do not, and the closeout

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails R1–R13, design bar,
ledger H1–H101), then `docs/SAAS_RUNBOOK.md`, then H4a–H4c's handovers and the code they produced.
This phase ports FLEET **P5** and closes the programme. Binding ledger entries: **F23, F24, F40,
F41, F44, F52, F53, F54, F55, F58, F60, F61, F67**, plus **H62** (cloning), **H77** (never
`carejiox-deploy -t`), **H78** (a clone's crons), **H4c's downtime lesson** (rail R3 is one act),
and H4c's own §10 list. Source to port (READ-ONLY, rail R10): `gitlocal/pb_tenants` billing code,
`gitlocal/pb_tenancy`'s plan card, paused door and seat guard.

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H4d's hero: **the invoice preview** — the owner picks a month, and before anything is
created they see, per clinic, the numbers the platform actually measured, the plan applied to them,
and the money that falls out, with one line explaining each figure in words. Nothing is created
until they press the button. Second: the **paused door** — the one screen a locked-out clinic sees,
which must be calm, name the reason, name who to pay, and never look like a fault. Zero dead-ends,
plain language, `ic()` icons, no emoji, no gradients. Chrome validation mandatory.

White-label rule (binding): "Odoo" never in a user-visible string — and this phase produces a **PDF
that goes to a customer**, where the trap is real: a report with no `title` in its context is titled
**"Odoo Report"** in the document's own properties (**F55**). The product name comes from the brand
setting.

---

## 0. Owner decisions that shape this phase

1. **The sold unit is configurable per plan** (2026-09-04). All four of H4a's meters — people in
   care, visits completed, staff with a login, invoices issued — can price a plan, plus a flat price
   and a flat price by size band. The meter already collects every number every month, so a plan can
   be changed without losing history.
2. **Invoices first, card later** (carried from Payobook's ruling 1): the platform raises an invoice
   per clinic per month; the owner marks it paid when the transfer arrives. Overdue → reminder →
   optional suspension. **Auto-suspend ships OFF**: locking a working clinic out without a human
   pressing something is not a default.
3. **Mail stays dark.** Invoices and reminders are built, rendered and recorded; nothing sends until
   an account exists, and every screen says so. The invoice PDF can still be downloaded and sent by
   hand — make that a button.
4. **Prices are placeholders and the owner fills them in.** Seed three plans with obvious
   placeholder figures in **VND**, VAT 0 %, and leave company address, tax number and bank details
   **blank** behind a Billing → Settings screen with a red note saying an invoice is not fit to send
   until they are filled. Do not invent a bank account.

## 1. Scope

1. **Plans** (§3.1): `biz.plan` with the six price structures, bands, and the seeds.
2. **Customer lifecycle** (§3.2): `trial | live | paused | pending_deletion` with a retention clock,
   and the transitions as deliberate acts.
3. **The monthly meter snapshot** (§3.3) — H4a's writer, now scheduled and readable as history.
4. **Invoices** (§3.4): the model, the preview, the PDF, mark paid, overdue, reminders, and the
   auto-suspend switch that ships off.
5. **The tenant side** (§3.5): the seat limit, the trial bar, the "Plan & usage" card, and the
   **paused door**.
6. **The closeout** (§3.6): `docs/handovers/SAAS_CLOSEOUT.md`.
7. Tests (§5), commits (§6), ledger from H102, runbook update, report (§7).

## 2. Binding NON-goals

- No payment provider, no card handling, no bank integration. The invoice model must leave room for
  one later (a `payment_reference` and a `paid_via` are enough) and nothing more.
- Do not connect or create a mail account. Reuse H4b's honest degradation.
- **Do not pause, suspend, seat-limit or delete `hhh`.** Every destructive state is proven on a
  restored practice copy (`hhh-staging`), exactly as FLEET did — its live validation of pausing and
  seat limits ran on `abm-staging` only. `hhh` gets a plan, a preview and an invoice; nothing more.
- Do not enable auto-suspend anywhere, including on the clone.
- No new features beyond this list. The programme ends here.

## 3. Architecture

### 3.1 Plans

`biz.plan`: `name`, `active`, `currency_id` (VND), `price_kind`:
- `flat` — a price per clinic per month;
- `per_patient`, `per_visit`, `per_staff`, `per_invoice` — a price × the meter's number for the
  month, with an optional `included` allowance and an optional `minimum`;
- `flat_tier` — a price per band, bands on `biz.plan.tier` (`meter_key`, `up_to`, `price`).

**A plan priced by band must be created WITH its bands, in one write** (**F60**): the model refuses a
`flat_tier` plan with no bands — correctly — and a data file that creates the plan and then adds
tiers fails the constraint in between and takes the whole upgrade with it. Seed with an inline
`tier_ids` eval; `plan_save` builds `[(5, 0, 0)] + [(0, 0, …)]` into the same write.

Every non-flat plan names a `meter_key` from H4a's registry, and the plan form shows, live, what
that plan would have charged **this clinic last month** — the connection between a price and a
measurement, on the screen where the price is typed.

Seeds (placeholders, VND, the owner overwrites them): **Starter** flat 2,000,000 ₫/month;
**Growth** per_patient 30,000 ₫ with 50 included; **Clinic** flat_tier on `patients`
(≤100 → 5,000,000 ₫, ≤300 → 9,000,000 ₫, above → 15,000,000 ₫). Say on the screen that they are
placeholders.

### 3.2 Lifecycle

`biz.tenant.state` gains `trial` and `paused`; `pending_deletion` joins `decommissioned` (H4c gave
decommissioning a "build their system again" path — keep it working).
- `trial_ends_on`; a trial that ends does **not** pause anything on its own — it raises an alert and
  says so. Nothing locks a clinic out on a timer.
- `paused`: set by a person, or by the auto-suspend cron **only when that switch is on** (it ships
  off, with a red explanation beside it). Pausing pushes `biz_tenancy.paused` + the reason; the
  customer's door (§3.5) reads it. Un-pausing is one press and takes effect within the poll.
- `pending_deletion`: a retention clock (`biz_tenants.retention_days`, default 60) after which the
  cockpit offers deletion; the cron never deletes, it only alerts. **Nothing on this platform ever
  drops a customer's database on a schedule.**
- Every transition writes a `provision_log` line and an alert kind on H4b's open list
  (`trial_ending`, `invoice_overdue`, `suspend_candidate`, `tenant_paused`) — and those go on
  `SELF_MANAGED_KINDS`, which H4c already established, or the 15-minute sweep will resolve them
  minutes after the morning job raises them (**F67**'s family).

### 3.3 The monthly snapshot

A cron on the 1st writes one `biz.tenant.meter` row per customer per meter per month, reading
through H4a's guarded meter registry. **History is the point**: billing must bill from what was
measured at the time, never from a number recomputed later. A month already snapshotted is not
overwritten; a re-run is a no-op that says so. Backfill the months the platform has been running so
the first invoice preview has something to show, and mark backfilled rows as such.

### 3.4 Invoices

`biz.tenant.invoice`: `tenant_id`, `period_start`, `period_end`, `plan_id`, `line_ids` (label,
quantity, unit price, amount — one line per meter used plus any adjustment), `subtotal`, `vat_rate`
(default 0), `total`, `currency_id`, `state` (`draft|issued|paid|cancelled`), `issued_on`,
`due_on`, `paid_on`, `payment_reference`, `paid_via`, `number` (a sequence per year).

- **Preview before create** (the hero): a screen per month showing every clinic, the measured
  numbers, the plan, the arithmetic in words ("236 people in care × 30,000 ₫, 50 included → 5,580,000 ₫")
  and the total. Nothing is written until the button.
- **The PDF.** Two traps, both certain to bite:
  - **`<div class="article">` is what gives a printed document its character set** (**F54**). A
    report with no `article` div falls through to a fallback that hands the printer a bare fragment,
    which is read as Latin-1 — every `₫` becomes `â‚«` and every `—` becomes `â€"`. It renders, it
    looks deliberate, and it goes to the customer. The page div is `class="article page"` with the
    `data-oe-model`/`data-oe-id` attributes the standard layouts set.
  - **Set a `title` in the context** (**F55**) or the PDF's document properties read "Odoo Report" —
    a user-visible string like any other. And a page that prints no header must set
    `data_report_margin_top` / `data_report_header_spacing` or ~35 mm is reserved for a header that
    is not there.
  - Brand, company name, address, tax number and bank details come from settings; the PDF says
    plainly at the foot when they are missing rather than printing an invoice that cannot be paid.
- **Mark paid** (with a reference and a date), **cancel** (with a reason), **download**, and
  **send** — which is dark, says so, and offers the download instead.
- **Overdue → reminder**: a daily cron; reminders are alerts and (dark) emails; the count is on the
  invoice. **Auto-suspend is a platform switch, default OFF**, with a red paragraph explaining what
  it would do. Bind its `aria-pressed` to a **string**, not a boolean (**F58**: `t-att-` bound to
  JavaScript `true` renders an EMPTY attribute, and the switch sat grey beside a paragraph in red
  saying it was on — a control that disagrees with its own explanation is worse than no control).
- **Helper names**: this facade is one model assembled from many files. A helper added to it is
  added to every file that shares it — name this phase's `_billing_*` (**F52**: `_mail_shell`
  collided across two files and broke a button two phases old).

### 3.5 The tenant side

- **Seat limit**: a `create` guard on the model the overlay names
  (`biz_tenancy.seat_model`, default `res.users` for this product — staff with a login is the meter
  the owner is most likely to sell on; the overlay decides and an override in `health_tenancy` is
  simpler and more explicit than a generic hook). Refuses with a plain sentence naming the plan and
  who to contact. Never applies to the recovery account or a support session.
- **The trial bar** and the **"Plan & usage" card** on the About screen H4a built: which plan, what
  the platform has measured this month, and when the next invoice is expected. Read-only.
- **The paused door.** The trap that matters most in this phase (**F53**): `request.env.user` is an
  **empty recordset** on a route declared `auth='none'` even when somebody is signed in, and
  `has_group()` on an empty recordset raises `ValueError: Expected singleton` — which the original
  fail-open handler caught, letting **every request through, silently, on every page**. And `/odoo`
  on this build is exactly such a route (`biz_deroute`'s redirect to `/bizapp`), so the door was
  open on the first hop of every navigation. Read `request.env.uid or request.session.uid` and
  browse the user explicitly. **A fail-open handler must put the reason in its log line**, not only
  in a traceback — the line is the only thing anybody greps, and here a silent failure means an open
  door. The door lets through: the recovery account, an active support session, and the assets a
  door needs to draw itself. The page itself is calm, names the reason and who to contact, and
  offers nothing that looks like a fault.

### 3.6 The closeout

`docs/handovers/SAAS_CLOSEOUT.md`, written the way `from_payobook/FLEET_CLOSEOUT.md` and
`ACCESS_CLOSEOUT.md` are: what is live in the owner's words, what to press to see each thing, the
phase-by-phase table with commits, the open owner decisions (mail, prices, bank details, the brand
name, the resize, `admin_passwd`, the debranding leak H4c found), the debts, and how to keep working
on it. Plain English throughout; it is the document the owner reads.

## 4. Order of execution

Rehearse on a scratch clone with a throwaway customer, tests through `systemd-run` on a spare port
with the service UP (**never `carejiox-deploy -t`** — H77), a **private `--addons-path`** for the
rehearsal so the live tree is untouched (H4c's downtime lesson), clone crons disabled immediately
(H78), clone dropped promptly.

Live: deploy master + template + `hhh` **as one act, finished in one sitting** (rail R3, and H4c's
4-minute lesson). Then: give `hhh` a plan; snapshot and backfill the meters; preview a month;
create, render and download one invoice; mark it paid; **prove the paused door, the seat limit and
the trial bar on a restored practice copy `hhh-staging` only**, then drop it. Delete the validation
alerts (F41). 15-minute watch.

## 5. Numbered test cases

1. Pricing (pure, one test per structure): flat; per-unit with an allowance and a minimum; the four
   meter keys; `flat_tier` band selection at the boundaries (≤, not <) and above the top band;
   a month with no snapshot prices as zero **and says why** rather than guessing.
2. `flat_tier` refuses to exist without bands, and the seed creates plan+bands in one write (F60).
3. Snapshot: one row per customer per meter per month; a re-run does not overwrite and reports a
   no-op; backfilled rows are marked; billing reads the snapshot, never a live recount.
4. Invoice: preview writes nothing (prove no row exists after); create produces the lines the
   preview showed, to the currency's precision; numbering is sequential per year and has no gaps
   under a rollback; mark paid records reference and date; cancel requires a reason.
5. The PDF: contains `₫` and an em dash **as those characters** (render it and assert the bytes —
   F54); its document title is the invoice's, not "Odoo Report" (F55); with company details missing
   it prints the plain warning; no user-visible string contains "Odoo" (F43's assertion over the
   rendered text).
6. Overdue: a reminder is raised once per configured interval, not once per cron run; the count
   increments; `spoken_at` stays empty while mail is dark (F40); auto-suspend does nothing while the
   switch is off, and the switch's `aria-pressed` is the **string** `"true"` (F58).
7. Lifecycle: every transition writes a log line and its alert; the alert kinds are on
   `SELF_MANAGED_KINDS` so the sweep never resolves them (F67); a trial ending pauses nothing;
   `pending_deletion` never deletes on a schedule.
8. The paused door: `request.env.user` is empty on the `auth='none'` route and the door still
   decides correctly (construct the case — F53); the recovery account and an active support session
   pass; a signed-in ordinary user is stopped; the fail-open path logs its reason (assert on the log
   record, not just that it did not raise); `/odoo` is covered.
9. Seat limit: creating past the limit is refused with the plain sentence; the recovery account and
   a support session are exempt; the limit is read from the pushed parameter, and an absent
   parameter means no limit (F24 — distinguish absent from empty).
10. Full suites over every module touched (F49): `/biz_tenants,/biz_tenancy,/health_tenancy,
    /health_access,/biz_access,/biz_kit`.
11. Chrome on live (`docs/handovers/saas_h4d_shots/live_*.png`): the plan form with the "what this
    would have charged" line; the invoice preview for a month; the created invoice and its PDF open
    in the browser; mark paid; the Billing settings screen with its red note; the auto-suspend switch
    showing OFF and agreeing with its own paragraph; `hhh`'s own "Plan & usage" card.
12. Chrome on the practice copy `hhh-staging` only: the paused door as a customer sees it; the trial
    bar; the seat-limit refusal. Then drop the copy and prove `hhh` itself was never paused.
13. Live health: master, template and `hhh` answer throughout; watch clean; validation alerts
    deleted; `hhh` is `live`, not paused, and its seat limit is unset; memory recorded.

## 6. Commits (explicit staging, no push)

1. `feat(biz_tenants): plans — six ways to price a clinic, and the number each one reads`
2. `feat(biz_tenants): the monthly measurement, kept as history`
3. `feat(biz_tenants): invoices — preview, create, the document, and marking one paid`
4. `feat(biz_tenancy): the trial bar, the plan card, the seat limit and the paused door`
5. `docs(saas): H4d handover, ledger H102+, runbook update, screenshots`
6. `docs(saas): the closeout`

## 7. Report back

1. **Owner summary (6 lines)**: what the platform can now charge for and how; that nothing sends and
   nothing suspends on its own; what needs their figures before an invoice can go out.
2. Per numbered test with evidence.
3. The `odoo.tests.result` lines; the log ERROR grep.
4. The three seeded plans as they read on screen, and what each **would have charged `hhh` and the
   master clinic** last month from real measurements.
5. The invoice you created for `hhh`: its numbers, and the PDF attached to the report (say where the
   file is) — with the ₫ proven to render.
6. The paused door, the trial bar and the seat limit as proven on `hhh-staging`, and the proof that
   `hhh` itself was never paused.
7. What is still blank and blocks a real invoice: company address, tax number, bank details, prices,
   VAT — in the owner's words, as a short list they can fill in one sitting.
8. Ledger entries (from H102); commit hashes; the practice copy and clone dropped.
9. `SAAS_CLOSEOUT.md` written — say what is in it.
10. Decisions the handover did not cover, and anything you would not ship without the owner seeing
    it first.
