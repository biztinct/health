# The platform — closeout (2026-09-05)

**Status: COMPLETE.** Eight phases (H0, H1, H2a, H2b, H3, H4a, H4b, H4c, H4d), all
live on the machine at **https://carejiox.com**. This is the document to read
first in any future session. The document to hand somebody who has to RUN the
machine is `docs/SAAS_RUNBOOK.md`. The engineering record — every decision, every
trap, the whole ledger H1–H111 — is `docs/handovers/SAAS_PORT_PROGRAM.md`.

Written in plain English, for the person who owns the product rather than the
person who wrote it.

---

## 1. What you have now, in one page

**You had one system, running one clinic. You now have a platform.** It makes new
clinics, keeps them apart, keeps them up to date, copies them every night,
watches them, tells you when something is wrong, and — since today — can charge
them for it.

| What you asked for | What the platform does now |
|---|---|
| **A new clinic without a runbook** | Six steps and one button. Type a name, press Create, watch it happen: the blank system is copied, its address is set up and secured, its administrator is made, everything is checked, and you are handed a web address, a sign-in name and a one-time password. About **20 seconds**. Every step has a rehearsal that writes nothing, and every failure says what to do next. |
| **Every clinic separate** | One database per clinic. The first word of the web address IS the clinic. Nobody can reach anybody else's data, and the address of a clinic that does not exist is refused outright. |
| **A blank clinic that is actually usable** | The blank system is Vietnamese and English, with the Vietnamese chart of accounts and 275 accounts, and **175 parts of the product** — computed from what the product itself needs rather than from a list somebody typed. |
| **Nobody gets things they did not buy** | Ten parts of the product can be switched off per clinic — Care Command, Telehealth, Family, Deterioration watch, Insurance claims, Red invoice, Analytics, Assisted notes, Phone system, Training. A switch reaches their screens in **about 20 seconds**, and switching one off deletes nothing. |
| **Updates that do not frighten anybody** | A release is a named photograph of what the master runs. It reaches the fleet in rings — a rehearsal on a copy, then the blank system, then one clinic on its own, then the rest — each inside their own quiet night, in their own clock, with Pause / Continue / Retry / Leave behind / Call it off always one press away. |
| **A copy of everything, every night** | Every live clinic, every night, kept for a fortnight, database and attachments together, both sizes checked. Any copy can be put back into a practice system to prove it is good. |
| **To be told when something is wrong** | Everything is looked at every fifteen minutes. Every problem carries a plain sentence and what to do next. **Nothing is emailed** — there is no mail account yet — so the Alerts screen IS the channel, and every card says so on its own face. |
| **A page the world can read** | https://carejiox.com/status, written by the platform and handed out by the web server off disk, so it stays up when the application does not. It names no clinic, ever. |
| **To go into a clinic's system honestly** | "Open as support" asks for a reason you have to type and a time box. It makes a one-time link, puts a rose bar with a countdown across their screen while you are in, and writes every session — who, when, why, and which screens you opened — on THEIR own record where their people can read it. And they have a switch to refuse support entirely. |
| **To charge for it** | Three plans, six ways to price, a preview that shows what a month would cost before anything is created, an invoice document, mark-as-paid, overdue reminders, a trial, a seat limit and a paused door. All of section 2. |

---

## 2. What you can charge for, and how (this week's work)

**The plans.** Three of them, one of each way of charging. **Every price on them
is an example that nobody has agreed.** They carry an amber "Example price" badge
until you open the plan, type the real number and save it — saving is what takes
the badge off.

| Plan | How it charges | The example figure |
|---|---|---|
| **Starter** | One price a month, whatever the clinic does | 2,000,000 ₫ a month |
| **Growth** | A price for each person in care, every month | 30,000 ₫ each, the first 50 included |
| **Clinic** | One price a month, by how many people are in care | ≤100 → 5,000,000 ₫ · ≤300 → 9,000,000 ₫ · above → 15,000,000 ₫ |

**A plan can charge on any of the four numbers the platform measures** — people
in care, visits completed, staff with a login, invoices issued — plus a flat
price and a price by band. That is six ways to price a clinic. All four numbers
are measured for every clinic every month whatever plan they are on, so you can
change how you sell next year without having lost the history to bill from.

**The reading, kept as history.** On the 1st of each month the platform writes
down last month's four numbers for every clinic. **A month that already has a
reading is never given a second one** — an invoice is worked out from what was
measured at the time, never from a number recomputed today.

**The preview is the point.** Pick a month; see every clinic, the numbers the
platform actually measured, the plan applied to them, and one line explaining the
arithmetic in words — *"236 people in care × 30,000 ₫, 50 included → 5,580,000 ₫"*.
A clinic that would be left out says why. **Nothing on that screen has been
created.** Change a price, look again. Only the button at the bottom writes
anything.

**The document.** Rendered once when the invoice is raised and kept — a document
that changes after it was sent is not a document. Open it, download it, or press
the envelope: the envelope is honest and tells you nothing was sent and why.
Mark it paid with the reference off the bank statement when the transfer arrives.

**Nothing happens on its own.**
* A trial running out **does not lock anybody out**. It raises a note and waits
  for you. The clinic sees a calm bar for the last ten days that says so.
* An overdue invoice **raises a flag**, not a locked door. There IS a switch that
  would pause a clinic automatically after 21 days, and it **ships off and should
  stay off** — the first thing a clinic would know about it is a locked door on a
  Monday morning.
* A clinic scheduled for closing has a 60-day clock. **Nothing removes their data
  when it passes.** The clock raises a note; the button still needs a person and
  takes a final copy first.

**Pausing, when you decide to.** "Shut their door" asks for a reason — which
their own people read, word for word — and for their short name typed out.
Their people then meet a calm page: what has happened, that **nothing has been
deleted**, and who to ask. Letting them back in is **one press and no typing**.

**What a clinic sees of all this.** One card on their own "About" screen: which
plan, what was measured for them, how many people have a login, and when the next
invoice is expected. Read-only.

---

## 3. What to press to see each thing

Everything is on **https://carejiox.com**, left menu → **ADMIN → Customers**.

| To see | Go to |
|---|---|
| Every clinic, and room for another | **Customers** (the screen it opens on) |
| Make a new clinic | **New customer** |
| What a month would cost every clinic | **Plans and invoices → What a month would cost** |
| Every invoice ever raised | **Plans and invoices → Invoices** |
| The three plans, and their real prices | **Plans and invoices → Plans** |
| Your company details for the invoice | **Plans and invoices → Billing settings** |
| One clinic's plan, trial, pause and invoices | a clinic → **Plan** |
| What each clinic has switched on | **What each customer has** |
| Send a release out | **Rollout** |
| What the platform has noticed | **Alerts** |
| Go into a clinic to help | a clinic → **Support access** |
| Close a clinic down | a clinic → **Closing down** |
| What a clinic sees | their own address → **ADMIN → About Viet Uc Care** |

---

## 4. The phases, and what each one left behind

| Phase | What it did | Commits |
|---|---|---|
| **H0** | Checked every assumption against the live machine before a line was written | — |
| **H1** | The shared toolkit and the Access home as product-neutral modules | `SAAS_H1_KIT_ACCESS_CORE.md` |
| **H2a** | The Access home fitted over this product, beside the old one, nothing removed | `SAAS_H2A_HEALTH_ACCESS_OVERLAY.md` |
| **H2b** | The bought-in access app retired: 27 tables dropped, **0 roles lost**, 0 job flags changed across 73 colleagues | `SAAS_H2B_RETIRE_ACCESS_ROLES.md` |
| **H3** | The machine became a platform: one database per address, self-renewing certificates, a blank system built from nothing (which found **13 packaging faults** no existing database could have shown), the master renamed in **26 seconds** | `SAAS_H3_SERVER_PLUMBING.md` |
| **H4a** | The Customers screen: six steps, the fleet, health, copies, releases | `SAAS_H4A_TENANT_COCKPIT.md` |
| **H4b** | Running the fleet safely: rollouts in rings, alerts, the capacity guard, the public page | `SAAS_H4B_ROLLOUTS_ALERTS_CAPACITY_STATUS.md` |
| **H4c** | What a clinic is made of (computed, 175 parts), the blank system made Vietnamese, ten feature switches, and support access with a trail | `SAAS_H4C_MODULE_SET_FEATURES_SUPPORT.md` |
| **H4d** | Plans, the monthly reading, the invoice preview and document, the trial, the seat limit and the paused door | `SAAS_H4D_PLANS_BILLING_PAUSE.md` |

At closeout: `biz_tenants` 19.0.1.2.0 (the master only — no clinic ever has it),
`biz_tenancy` and `health_tenancy` 19.0.1.2.0 (master, blank system and `hhh`).
Release **2026.09.04** on all three. **846 tests green** on the last full run.

---

## 5. What is still yours to decide (nothing below is done without you)

1. **The prices.** All three plans carry example figures. Until you replace
   them, every preview says so in amber and the plan card wears a badge.
2. **Your company details.** The invoice cannot be sent until four things are
   filled in — the company name it comes from, its address, its tax number, and
   the bank details to pay into. **Nothing was invented for you**: the document
   itself prints a red note saying it is not ready to send. Ten minutes on
   **Plans and invoices → Billing settings** and the warning goes.
3. **Tax.** All three plans are at 0 %. If a subscription in this market carries
   VAT, put the rate on the plan and it prints its own line.
4. **Mail.** There is still no outgoing mail account, so **nothing this platform
   builds is ever sent**: not an invoice, not a reminder, not an alert. All of it
   is built, recorded and downloadable; the Alerts screen is the channel until
   you connect one. Settings → Technical → Email → Outgoing Mail Servers, then a
   sender address, then press "Send a test email" on the Alerts screen.
5. **The brand.** Everything says "Viet Uc Care" because that is the setting.
   Change `biz_debranding.brand_name` and every screen, page and invoice follows.
6. **A bigger machine.** The machine holds **about one more clinic** today. The
   gauge is on the Customers screen and provisioning refuses at nought by name.
   `docs/SAAS_RESIZE_RUNBOOK.md` is the procedure; you pick the downtime.
7. **The database manager password.** `admin_passwd` in `/etc/odoo-server.conf`
   is still the shipped default. The database manager is 404 on every address, so
   nothing can reach it — but it should be changed anyway.
8. ~~**A leak that is not ours.**~~ **FIXED 2026-09-05.** Three of them, in
   fact, and one would have started SENDING the day you connect a mail account:
   a periodic digest titled after the software underneath, active on every
   database and set to daily on the blank system. It is renamed and switched
   off (Settings → General Settings → Statistics turns it back on if you ever
   want it). The seeded welcome message, the notification preference label and
   the assistant's own messages are rebranded in both languages, and the word
   is now taken out of every email at the moment it is rendered. Nothing on any
   of the three databases names the software underneath where a person can see
   it. Nobody's own message was edited.
9. **Copies live on the same machine as the clinics.** If the machine is lost,
   the copies go with it. **This is the single most dangerous thing about the
   platform** and it has been true since day one.

---

## 6. Things to know

* **Nothing on this platform ever locks a working clinic out on a timer, and
  nothing ever deletes a clinic's data on a schedule.** Both are deliberate,
  both are said on the screens, and the one switch that could change the first
  ships off with a red paragraph beside it.
* **Nobody is invoiced by a scheduled job.** The preview comes first, always.
* The nightly copy runs at 19:30, the drift check at 21:15, the monthly reading
  at 02:30 and the invoice chase at 07:15.
* A practice copy of a clinic (`<name>-staging`) is refused by the web server, so
  it is never on the public internet — but it is a full copy of that clinic's
  data with their own passwords in it. Drop it when you are done.
* A clinic's screens update themselves within a minute; a browser tab that is
  BEHIND another window does not update until you look at it.
* Every phase's screenshots are in `docs/handovers/saas_h4*_shots/`.
* Everything destructive — pausing, seat limits, trials — was proved on a
  restored practice copy and never on the real clinic.

---

## 7. How to keep working on it

One handover per phase: the design is written down first with the traps named
and the tests numbered, then it is built, tested and reported against that
document, then the ledger is appended. `SAAS_PORT_PROGRAM.md` carries the rails
and 111 ledger entries — every one of them something that cost somebody an hour
once. Read the ledger before changing anything on this platform; most of what
looks like a free choice in it is a scar.
