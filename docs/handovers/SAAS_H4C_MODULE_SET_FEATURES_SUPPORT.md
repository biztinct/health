# SAAS H4c — what a clinic is made of, what can be switched off, and getting into a customer's system honestly

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails R1–R13, design bar,
ledger H1–H88 — H77–H88 are H4b's and include two incidents you must not repeat), then
`docs/SAAS_RUNBOOK.md`, then `SAAS_H4A_TENANT_COCKPIT.md` and `SAAS_H4B_ROLLOUTS_ALERTS_CAPACITY_STATUS.md`.
This phase ports FLEET **P4** (feature switches) and **P6** (support access with a trail), and closes
the module-set decision that blocks rollouts. Binding ledger entries: **F45, F46, F47, F48, F49,
F53, F62, F63, F64, F65, F66, F67**, plus **H77, H78, H83, H85** from H4b and **H62** from H4a.
Source to port (READ-ONLY, rail R10): `gitlocal/pb_tenants` and `gitlocal/pb_tenancy` (their feature
and support-access code).

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H4c's hero: **the feature matrix** — every clinic a column, every part of the product a row,
a click to turn one off, and a **live miniature of that clinic's left menu beside it** redrawing as
you click, so the owner sees what the customer will see before pressing anything. Second: the
**support-access door** — a reason you must type, a time box, one link, a rose bar counting down on
the customer's screen, and a line on their own Access screen that they can read. Zero dead-ends,
plain language, `ic()` icons, no emoji, no gradients. Chrome validation mandatory.

White-label rule (binding): "Odoo" never in a user-visible string — including the support bar, the
switched-off page and every audit line a customer can read.

---

## 0. Owner decisions that shape this phase (2026-09-04/05)

1. **"Care apps only — but some care apps need a few core parts as dependencies; you decide that
   from the dependencies."** So the customer module set is **computed, not listed** (§3.1). Measured
   in the design session: the dependency closure of the product is **117 modules**, and **none** of
   the 22 extra apps on the master is in it. `sale`, `purchase` and `hr_timesheet` ARE in it (pulled
   by `health_invoicing`, `health_fieldservice` and `advanced_pricing`) — the *apps* built on top of
   them (`sale_management`, `stock`, `project`, `sale_timesheet`, …) are not.
2. **New clinics start Vietnamese-ready**: Vietnamese and English both active, and the **Vietnamese
   chart of accounts** (`l10n_vn`) instead of the generic one the template carries today.
3. Carried forward: mail stays dark; alerts to the owner; brand from the setting; the apex is
   `carejiox.com`; `hhh` is the pilot.

## 1. Scope

1. **The customer module set** (§3.1): computed, tested, and the never-list grown to match.
2. **The template made Vietnamese** (§3.2), and **`hhh` re-provisioned from it** — which is also the
   honest proof that decommissioning and provisioning both work.
3. **The `-staging` hole** (§3.3, ledger H85): one nginx line.
4. **Feature switches** (§3.4): the catalogue, per-customer on/off, pushed to the customer, the rail
   gate, the switched-off page, the matrix with the live menu preview.
5. **Support access with a trail** (§3.5): reason, time box, one-time link, the rose bar, the
   customer's own record of it, and their switch to refuse it.
6. Tests (§5), commits (§6), ledger from H89, runbook update, report (§7).

## 2. Binding NON-goals

- **No plans, trials, invoices, seat limits or the paused door** — that is H4d, the last phase.
  Build no model for them.
- Do not connect or create a mail account. The support-access notification is built and dark, like
  every other message (H4b §3.2's pattern — reuse `_send_alert_mail`'s honest degradation, do not
  write a second one).
- Do not run a fleet-wide rollout. Once §3.1 and §3.2 land, a rollout over `hhh` becomes a genuine
  no-op — **prove that it plans as a no-op**, and only then, if it does, run it (that closes H83).
- Do not uninstall anything on the master. The 22 extras stay where they are; they are simply never
  given to a customer.
- Do not touch H4b's alerts, capacity or status page except to add the new alert kinds §3.5 needs.

## 3. Architecture

### 3.1 The customer module set — computed

Add to `biz_tenants` a pure function `customer_module_set(master_installed, manifests, never)`:
the transitive `depends` closure of every module on the master whose name starts with a **product
prefix** (`register_product_prefixes(('health_', 'biz_'))` from the overlay — generic core, product
overlay, exactly like every other registry), minus the never-list and its prefix rail, plus an
explicitly registered `register_extras(('l10n_vn',))` for things a product wants that nothing
depends on. Everything the master has that is NOT in that answer is, by definition, never given to
a customer.

The never-list therefore becomes: `biz_tenants`, `health_migration`, `health_catchment_backfill`,
prefix `biz_platform*` — **plus the 20 the computation exposes**: `stock`, `stock_account`,
`stock_sms`, `purchase_stock`, `sale_management`, `sale_pdf_quote_builder`, `sale_project`,
`sale_project_stock_account`, `sale_purchase_project`, `sale_service`, `sale_timesheet`,
`spreadsheet_dashboard_sale_timesheet`, `project_stock`, `project_purchase_stock`,
`project_stock_account`, `barcodes_gs1_nomenclature`, `base_automation`, `base_iban`,
`account_qr_code_sepa`, `theme_default`. Each row on the "In step with master" screen carries its
reason in one plain sentence (that screen already shows reasons — H4a built it).

⚠ **`account_qr_code_emv` is the one judgement call.** It puts a VietQR payment code on an invoice;
nothing depends on it, so the computation excludes it, but the owner asked for Vietnamese invoicing
and the master has it with six bank accounts configured. **Include it in `register_extras` and say
so plainly in the report** so the owner can reverse it in one line.

A test asserts: the closure contains `sale`, `purchase`, `hr_timesheet` (they are real
dependencies); it contains none of the 20; and — the maintenance tripwire — **it fails if a product
module ever gains a dependency on one of the 20**, naming both modules, so the day somebody makes
Inventory load-bearing it is a failed test and not a surprise on a customer's screen.

### 3.2 The template made Vietnamese, and `hhh` remade

The template today: `generic_coa`, 50 accounts, English only. It must become: **Vietnamese + English
active**, **`l10n_vn` loaded**, and `account_qr_code_emv` present. Swapping a chart of accounts on a
database that has posted entries is not safe; the template has none, so try the cheap route first
and fall back if it is dirty:
1. Install `l10n_vn` (+ `account_qr_code_emv`) on the template; activate `vi_VN`; load the
   Vietnamese chart (`env['account.chart.template'].try_loading('vn', company=…)` — the pattern is
   in `from_payobook/SAAS_RUNBOOK.md`'s template-rebuild section). Verify: the company's
   `chart_template` reads `vn`, the account count is the Vietnamese one, journals exist, and no
   orphan `generic_coa` account is referenced by anything.
2. If step 1 leaves a mess, **rebuild the template from scratch** with the corrected set (H3's
   procedure, now that its 15 packaging faults are fixed) — record which route you took and why.
Either way, afterwards: re-record and disable its crons (**F9/F20** — an upgrade switches them back
on), keep `admin` archived and the recovery account passwordless, and re-assert
`biz_access.topbar_mode` (H4a §3.8's `ensure_topbar_settings`).

Then **re-provision `hhh`**: decommission it through the cockpit (final backup, then removed — it
has 2 users and no clinical data; confirm that from the database before you press anything and say
so in the report), and create it again from the corrected template. Its administrator's password
changes; hand the new one back in the report exactly as H4a did. This is the phase's proof that the
whole provisioning path works twice.

### 3.3 The `-staging` hole (H85)

`<slug>-staging.carejiox.com` resolves through the wildcard and serves a practice copy to the public
internet while one exists. H4b found it; close it here beside H3's underscore guard, in the wildcard
block: refuse any hostname whose first label ends in `-staging` (`if ($host ~ "^[^.]*-staging\.")
{ return 444; }`), and add it to `biz-tenant-cert`'s generated blocks too. Prove it with `curl`
while a practice copy exists. This is an nginx edit — H3 owns those files; make it, `nginx -t`,
reload, and record it in the runbook.

### 3.4 Feature switches

`biz.feature` on the apex: `key`, `name`, `blurb` (what a customer loses if it is off), `sequence`,
`default_on`. Seeded by the overlay (`register_features`) with the owner's ten:
**Care Command, Telehealth, Family (portal + messages), Telemonitoring + Twin, BHYT claims,
Red invoice, Analytics, AI (coding + scribe), Voice, Learn.**

- Per customer: on / off, with an optional reason, stored on the apex and **pushed** to the customer
  as one `biz_tenancy.features` parameter through the single `push_settings` door H4a built.
- **Tenant side** (`biz_tenancy`): a features service; `featureOn(env, key)`; a `feature_key` column
  on the product's rail entries and a clause in the ONE visibility rule — which in this product means
  `health_tenancy` adds `feature_key` to `cms.sidebar.item` and `health_cms_sidebar`'s
  `_sidebar_visible_items` reads it (the same seam H2a used; do not write a second rule).
- **Fail open on absent, closed on unparseable, and say which in the log** — **F53**: a fail-open
  guard that swallows its reason is a door left open silently.
- **The switched-off page**: a surface reached by URL when its feature is off says, in the product's
  own voice, that this part is not switched on for this clinic and who to ask. Never a 404, never a
  traceback.
- **The browser must not out-guess the server**: the rail is drawn by the server, so a switch
  reaches it by the reload event, not by a reactive (**F48**). Watch a **signature string**, not a
  map rebuilt on every poll (**F47** — and `useState`'s return value IS the subscription).
- **`@api.model` is not inherited** (**F46**): the override of `get_sidebar_data` must carry it, and
  a test must assert the marker — forgetting it takes the whole left menu away from everybody and
  no Python test can see it.
- **A `<function>` in a data file with no arguments needs `@api.model` on the method** (**F45**) or
  the upgrade dies naming the XML line, not the method.
- **The matrix** (the hero): customers as columns, features as rows, bulk column actions, and the
  live miniature of that customer's menu beside it. Reuse `biz_access`'s mini-rail component rather
  than writing a second one.

### 3.5 Support access with a trail

- **From the cockpit**: "Open as support" on a customer → a dialog demanding a **reason** (free text,
  required, stored) and a **time box** (15 / 30 / 60 minutes). It mints a one-time token, writes a
  `biz.support.session` on the **customer's** database through `_tenant_env`, and returns a link.
- **The link** signs the operator in on that customer as the recovery account for the time box.
  Route gotchas, all measured on Payobook and all still true on this build:
  - **A route declared `auth='none'` is READ-ONLY by default** (**F62**, `odoo/http.py` — H3 confirmed
    the line on this build). Signing somebody in writes. Say `readonly=False`, and **never wrap
    `authenticate()` in a bare `except Exception`** — the framework recovers from
    `ReadOnlySqlTransaction` by re-running the request, and a blanket catch turns that into "your
    link has expired" and hides the real fault.
  - Build the session the harness's way in tests (**F65**), and remember `HttpCase` owns the cookie.
- **On the customer's screen**: a rose bar with a countdown, naming the platform and the reason, for
  the whole session. Mounted after `//NavBar` beside the notice bar (F18).
- **On the customer's own record**: every session — who, when, why, how long, and **which screens
  were opened**. Only backend addresses count as screens: a page load is thirty requests and a trail
  of `/web/image` is a record of nothing (**F66**). The address is seen before the page has a name,
  so the browser reports the title when it changes and a repeat of the same address fills the name
  in rather than being deduplicated away.
- **The customer can refuse support entirely**: a switch on their own Access/About screen
  (`biz_tenancy.support_allowed`), and the cockpit's door refuses by name when it is off.
- **The alert**: a session is an act, not a fault, so it is announced when the button is pressed —
  not by the fifteen-minute sweep, which would resolve a thirty-minute session that ended in two
  (**F67**). Dark like everything else, recorded on the Alerts screen. `pending` covers a link
  **issued but not yet used** (**F68**).
- Ending: explicit "End session", automatic at the time box, and on sign-out. `_pre_dispatch`
  deliberately re-raises `ReadOnlySqlTransaction` (F62's second half) so the end of a session is
  never silently lost.

## 4. Order of execution

Rehearse on a scratch clone with a throwaway customer (**`--db-filter=^<clone>$` always** — H32),
and **run every test through `systemd-run` on a spare port with the service UP — never
`carejiox-deploy -t`, which stops the live service for the whole run whatever `-D` says** (**H77**:
that took the platform down for 27 minutes). Drop clones promptly and remember a clone's upgrade
creates its new crons **active**, and every database on this box is a job target (**H78**) — disable
them on a clone before letting fifteen minutes pass.

Live order: §3.1 and §3.3 first (they change nothing a user sees); then §3.2 (template, then
`hhh` re-provisioned); then §3.4 and §3.5 deployed to master + template + `hhh`; then the H83 proof
(plan a rollout over `hhh` and confirm it is a genuine no-op).

## 5. Numbered test cases

1. `customer_module_set` (pure): contains `sale`, `purchase`, `hr_timesheet`; contains none of the
   20; the tripwire fails, naming both modules, when a product module is given a dependency on one
   of them; `l10n_vn` and `account_qr_code_emv` arrive via `register_extras`, not via the closure.
2. The never-list is re-asserted on the literal list about to be installed (H4a's rail, re-tested
   with the grown list).
3. Template after §3.2: `chart_template = 'vn'`, the Vietnamese account count, journals present,
   `vi_VN` and `en_US` both active, 0 active crons with the id list recorded, `admin` archived,
   recovery account passwordless, `topbar_mode = admin_only`, 0 skipped modules.
4. `hhh` after re-provisioning: same as 3 plus its own address answering 200, its administrator
   holding the Owner role and not `base.group_system`, and the decommission of the old one having
   taken a final backup first.
5. `-staging` refused: `curl -H 'Host: hhh-staging.carejiox.com'` returns 444 while a practice copy
   exists; the customer's own hostname still answers 200.
6. Features, server: a switched-off feature's rail entries vanish for that customer and no other;
   `get_sidebar_data` keeps `@api.model` (F46 marker test); an unparseable features value fails
   **closed** and logs the reason, an absent one fails **open** (F53); the data-file `<function>`
   carries `@api.model` (F45).
7. Features, browser: the rail redraws within a minute of a switch without a page reload (the bus
   event, F48); the watched signature changes only when the answer changes (F47); the switched-off
   page renders in the product's voice with no framework word.
8. Support access: the door refuses without a reason; refuses when the customer has turned support
   off, by name; the link works once and only once; the session ends at the time box; the route is
   `readonly=False` and `authenticate()` is not inside a bare `except` (source assertion, F62); the
   trail records backend screens only and fills in names (F66); a refused link still leaves its mark
   on the customer's record (**F64** — catch the exception by hand; `assertRaises` takes a savepoint
   and rolls the side effect back); `invalidate_recordset()` is not used where a write must be seen
   (**F63** — use `flush_all()`).
9. The alert fires on the press, is dark, and covers a link issued but not yet used (F67/F68).
10. Full suites over every module touched (F49): `/biz_tenants,/biz_tenancy,/health_tenancy,
    /health_cms_sidebar,/health_access,/biz_access,/biz_kit`.
11. Chrome on live (`docs/handovers/saas_h4c_shots/live_*.png`): the feature matrix with the live
    menu preview; a feature switched off on `hhh` and the entry gone from `hhh`'s own menu within a
    minute, then switched back; the switched-off page reached by URL; "Open as support" with a
    reason, the rose bar with its countdown on `hhh`, the trail on `hhh`'s own screen, the session
    ended; `hhh` signed into by its administrator after the re-provisioning, in Vietnamese.
12. H83: a rollout planned over `hhh` reports **no modules to install** — screenshot it. If it does,
    run it and record the timings (F33). If it does not, stop and report what is still adrift.
13. Live health: master, template and `hhh` all answer throughout; 15-minute watch clean; validation
    alerts **deleted** (F41); memory recorded; clone and throwaway dropped.

## 6. Commits (explicit staging, no push)

1. `feat(biz_tenants): what a customer is made of — the module set computed from the product's own dependencies`
2. `chore(saas): the practice-copy hostname is not public` (nginx + `biz-tenant-cert`)
3. `feat(biz_tenants): feature switches — the matrix, the live menu preview, and the push`
4. `feat(biz_tenancy): a part of the product that is not switched on says so`
5. `feat(biz_tenants): support access — a reason, a time box, one link, and a trail the customer can read`
6. `docs(saas): H4c handover, ledger H89+, runbook update, screenshots`

## 7. Report back

1. **Owner summary (6 lines)** — plus, clearly separated, **`hhh`'s new administrator login and
   one-time password** after the re-provisioning, and the plain statement that no email was sent.
2. Per numbered test with evidence.
3. The `odoo.tests.result` lines; the log ERROR grep.
4. The computed module set: its size, the 20 held back with their reasons as they read on screen,
   and the `account_qr_code_emv` judgement call in one plain sentence the owner can reverse.
5. §3.2: which route you took (swap or rebuild) and why; the template's before/after figures.
6. H83: the rollout plan over `hhh` — no-op or not, with the screenshot.
7. The ten features as seeded, each with the sentence a customer would read if it were off.
8. The support trail for the session you ran, exactly as `hhh`'s administrator sees it.
9. Ledger entries (from H89); commit hashes; clone and throwaway dropped; runbook updated.
10. Decisions the handover did not cover, and what H4d (plans, trial, paused door, seat limits,
    invoices) will need from what you built.
