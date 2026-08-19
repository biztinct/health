# Open platform remediation tickets

Standing defects that pre-date and out-scope the feature phases that keep
rediscovering them. Each is deliberately NOT fixed inside a feature phase —
both touch platform-wide security surfaces and deserve their own tested,
reviewed change. Close a ticket by striking it through with the fixing
commit; a feature-phase report that hits one of these should cite the ticket
instead of re-describing it.

---

## ~~T-001~~ — inverted group implication: every internal user carries healthcare-base ACLs — **CLOSED 2026-08-03, commit afdc9206**

**Closed by phase SH-2.** `health_base/migrations/19.0.1.3.8/post-migrate.py`
grants `group_healthcare_doctor` (350) to `access.role` "Doctor", then deletes
the single `(gid=1, hid=346)` row through the ORM, then archives the seven
accounts §5.5a authorised. Verified independently at review: `gid=1` now
implies `{6,7,14,20,37,57,393,394,395,399,537}` — 346 absent, `1 → 7`
(`base.group_no_one`) intact. 18 ACLs and 7 menus withdrawn from ~60 internal
users; the 10 Doctor-role clinicians keep access explicitly. Rollback is one
INSERT. **Not closed by this ticket:** the 21 `health.*` ACLs granted
*directly* to `group_id=1`, which the handover put out of scope and which the
edge deletion does not touch — see T-011.

*Original ticket text follows.*

**Found:** Phase W2 (2026-07-29). **Ledger:** §5.88.

`health_base/security/health_security.xml:23` declares
`group_healthcare_base → base.group_user`, but the live
`res_groups_implied_rel` on vietuat ALSO holds the reverse edge
(`gid=1 → hid=346`), which no module's XML asks for. Every internal user
therefore inherits the healthcare-base ACL set — including `health.ews.score`
read — and no narrowing of any service group's own implications can undo it.

**Fix shape:** delete the reverse edge in the live table, then re-run the
recursive closure query (§5.88 rules a–c) to prove the closure matches the
XML; check how the edge got there (a historical module or a manual grant)
so an upgrade does not resurrect it. Test: a `base.group_user`-only user
must NOT reach `health.ews.score`.

**Interim mitigations already shipped:** W2.5/W3 tests pre-check the live
closure before asserting denials (`_live_closure`), so the suites fail
loudly rather than vacuously if the edge spreads.

**ASSIGNED 2026-08-03 → phase SH-2**, specified at §5 of
`docs/strategy/handovers/platform-security-hardening.md`. The design
investigation found the fix is **not** a lone row deletion: `access.role`
id 6 "Doctor" grants no healthcare group at all, so ten clinicians reach
clinical data only through this edge and deleting it alone locks out 21
users. The role repair is part of the fix, and §5.5 carries a user decision
that must be answered before the phase runs.

---

## T-002 — core mail reads `base.partner_root` unsudo'd: every chatter throws AccessError for ops personas — **PARTIALLY CLOSED 2026-08-03**

**Found:** Phase W2.5 (2026-07-29); reproduced again in W3 — third phase in
a row.

Core Odoo `addons/mail/models/models.py:557`
(`_message_get_suggested_recipients_batch`) builds
`ban_emails = [self.env.ref('base.partner_root').email_normalized]` without
`sudo()`. This database's `res.partner` record rules deny uid 40 (`crm`,
the live ops persona) partner id 1, so every `mail.thread` chatter and the
CMS Contacts list raise an `AccessError` dialog for ops users. Reproduced
live on vietuat (W2.5 review; W3 evidence README "Pre-existing, not ours").

**Fix shape (pick one):**
1. A narrow `res.partner` read rule granting all internal users partner
   id 1 (smallest change, lives in `health_base` security XML — but see
   T-001 before reasoning about who "internal users" are); or
2. a targeted core patch module sudo'ing that one `env.ref` (survives core
   upgrades badly — prefer 1).

Test: drive a chatter render as a real ops persona (§5.4 — uid-1 tests hid
this for months).

**ASSIGNED 2026-08-03 → phase SH-1**, specified at §6 of
`docs/strategy/handovers/platform-security-hardening.md`, which takes fix 1.
Two corrections to this ticket, both verified live: **the partner is id 2**
(`base.partner_root` = "Viet Uc Care"), not id 1 — a fix hard-coding 1 does
nothing; and **the repo's `addons/mail` is a stale Odoo 18 snapshot that
does not contain the offending code and must never be deployed** (the live
server runs mail 1.19; the cited line 557 is correct for the SERVER file
only). There are two unsudo'd reads, `models.py:406` and `:557`. 16 active
internal users are affected. The "CMS Contacts list" half is **unverified**
and is being split into its own ticket.

**The `base.partner_root` CAUSE is closed 2026-08-03** by SH-1 §6:
`health_base.rule_internal_read_root_partner` (`ir.rule` id 4700) on
`res.partner`, bound to `base.group_user`, `perm_read` only, domain
`[('id','=',2)]` with the id baked at XML load. Verified live before (ops
persona: `AccessError` on both the partner read and
`_message_get_suggested_recipients_batch`) and after (both succeed, in a real
browser session as a persona carrying uid 40's exact group set). The widening
is exactly one record, asserted by T6.2.

**The TICKET IS NOT CLOSED: SH-1 found a SECOND, independent cause on the
same method.** `_message_get_suggested_recipients_batch` reads
`record.message_partner_ids` at `mail/models/models.py:548` — **nine lines
BEFORE** the `base.partner_root` read at :557 — and that triggers
`_compute_message_partner_ids`, which writes the field from
`message_follower_ids.mapped('partner_id')` and therefore needs **read on
every follower partner**. On `crm.lead` 1952 the followers include partner 3
(Mitchell Admin), which rules 340/618 deny an ops persona, so the chatter
still raises — with the new rule listed among the applicable ones, i.e. the
fix is live and simply does not govern this read. Measured live 2026-08-03
via `/mail/thread/recipients/get_suggested_recipients` in an authenticated
browser session. Because :548 runs first, this cause **masks** the
`partner_root` one on any record with an unreadable follower.

**Remaining fix shape:** decide which partners an ops/CRM persona may read
(rule 618's scope) — the same product question as T-004 — or sudo the
follower recompute. A `partner_root`-shaped point fix will not do it: the
follower set is unbounded. Do NOT widen `rule_internal_read_root_partner`;
it is deliberately one record.

**The CMS Contacts half is NOT closed** — see T-004, and note SH-1 reproduced
a sibling of it live: opening a client profile as the ops persona raises
`Failed to write field res.partner.allowed_main_contact_ids` on partner 1272,
blamed on rules 340/618. Same root question.

---

## ~~T-003~~ — `/website/snippet/filters` renders caller-supplied `res_model`/`res_id` through sudo — **CLOSED 2026-08-04, module `health_website_security`**

**Closed by a dedicated override module** (not a health phase). New addon
`health_website_security` (`depends: ['website']`) overrides
`website.snippet.filter._render` to refuse any **caller-supplied** `res_model`
not on an explicit allow-list (`product.product`, `product.template` — the only
models with a `dynamic_filter_template_*` view on this platform), returning `[]`
before super() reaches the sudo browse. Admin-configured `filter_id` /
`action_server_id` rendering is untouched — that path is not caller-controlled.

Verified live and **unauthenticated**: `POST /website/snippet/filters` with
`res_model=res.users, res_id=2` → `{"result": []}`. **Positive control** proved
selectivity: the same request with `res_model=product.product` is NOT
short-circuited — the stack trace shows it passing through the override into
core `_prepare_values`, where it hits a pre-existing core `KeyError` on a
`filter_id=0` single-record request (unchanged core behaviour, no leak, no
regression). 8 module tests (unit + `HttpCase` route probes for `res.users` and
a live `health.clinical.note`), 0 failed. Fix lives in an override module, never
a vendored core copy (ledger §5.109).

*Original ticket text follows.*

**Found:** SH-1 design investigation (2026-08-03). **Not** closed by SH-1 §3
— it is independent of the `base.group_public` ACL rows and survives their
deletion.

`addons/website/controllers/main.py:417-426` →
`website_snippet_filter.py:61-84` accepts a caller-supplied `res_model` /
`res_id` and renders the result through a **sudo** recordset, guarded only by
`assert '.dynamic_filter_template_' in template_key`. The template-key assert
constrains the RENDERER, not the model — so the reachable surface is
"whatever a dynamic-filter template chooses to print about an arbitrary
record", on a public route.

**Fix shape:** an allow-list of models the snippet filter may resolve, applied
before the sudo, plus a test that a health model is refused. Needs its own
phase: `website` is a core addon, so the fix belongs in an override module,
not in a vendored copy (see §6.0(a) / ledger §5.109 — never deploy the repo's
`addons/mail`-style stale core snapshots).

---

## T-004 — CMS Contacts list AccessError for ops personas (split from T-002)

**Found:** SH-1 (2026-08-03), split out of T-002 because it was never
verified.

T-002 claimed both the chatter AND the CMS Contacts list raise for ops
personas. Only the chatter/composer path was reproduced. A plain `res.partner`
list does **not** traverse `mail/models/models.py`, so if Contacts really
raises, the cause is different — most likely rule 618 (`Healthcare CRM
Partner: User Access`) denying non-patient partners to a CRM-grouped user.
SH-1's fix does not address it and deliberately did not widen to chase it.

**Fix shape:** reproduce as a real CMS persona first; if rule 618 is the
cause, the question is which partners a CRM user is *meant* to see, which is
a product decision, not a security patch.

---

## T-005 — six remaining `base.group_public` / `base.group_portal` ACL rows in health_fieldservice

**Found:** SH-1 §3 sweep (2026-08-03). Deliberately left alone by SH-1 —
each needs its own "does a public website page actually use this?" check, and
an unrequested ACL edit is indistinguishable from a mistake at review time.

Remaining rows in `addons/health_fieldservice/security/ir.model.access.csv`
after SH-1 deleted the four PHI-bearing ones:

| Model | Group | Plausible legitimate use |
|---|---|---|
| `health.portable.equipment` | `base.group_public` | none obvious |
| `health.clinical.protocol` | `base.group_public` | none obvious |
| `health.staff.skill` | `base.group_public` | a public "our services" page |
| `health.service.area` | `base.group_public` | a public coverage map |
| `health.staff.assignment` | `base.group_portal` | none obvious |
| `health.staff.availability.matrix` | `base.group_portal` | none obvious |

None of them is narrowed by an `ir.rule`, so each is a full-table read for the
anonymous or portal user. `health.staff.assignment` in particular joins staff
to visits.

**Fix shape:** for each row, find the public/portal surface that needs it
(grep the website + portal controllers for the model, and drive the page); if
none exists, delete the row. Same deletion mechanics as SH-1 §3 — the xmlids
carry `ir_model_data.noupdate = false`, so removing the CSV line deletes the
row on upgrade.

---

## T-006 — `health_base.group_healthcare_admin` ↔ `health_cms_sidebar.group_cms_sidebar_admin` imply each other

**Found:** SH-1 §3 sweep (2026-08-03). Report-only; unrelated to F1.

Each group implies the other, so the two are effectively one group: granting
either grants both, and no closure computed from one direction is meaningful.
Related to §5.88 (compute closures from `res_groups_implied_rel`, not from
XML). Worth resolving alongside SH-2, which is already in the implication
table.

---

## T-007 — the Unsigned Clinical Notes worklist is Admin-role-only in the CMS sidebar

**Found:** SH-1 §3.4 verification (2026-08-03). Report-only; fixing it is a
sidebar-seed change SH-1 is not sanctioned to make.

SH-1 §3.2 granted `health_base.group_healthcare_doctor` read/write/create on
`health.clinical.note` precisely so the EMR sign-off worklist works for the
clinicians it exists for. Server-side that now works: as a doctor-grouped
user, `search_count` returns 57, the list view's `web_search_read` returns
all 57, and the note form's `web_read` (including the `order_id` many2one)
succeeds — **even though the doctor still has no `health.fieldservice.order`
ACL at all**.

It is still unreachable in the shell a doctor actually logs into.
`cms.sidebar.item` id 93 "Unsigned Notes" (and 54 "Clinical Forms", 94 "Voice
Notes") are bound to the **Admin** role only, so a user on `access.role` 6
"Doctor" sees none of them — the §5.69 trap on the exact surface §3.2 exists
to serve. Verified by driving `/bizapp` as a Doctor-role persona.

**Fix shape:** add the Doctor (and probably Head Nurse / Manager) roles to
those `cms.sidebar.item` rows. The binding lives in
`access_role_cms_sidebar_item_rel` in the DB, not in XML, so it needs a data
change or a seed cutover (see the noupdate-seed-cutover note), not an addon
edit alone.

---

## T-008 — abandoned QA probe accounts on the live UAT database

**Found:** SH-1 browser QA (2026-08-03). Housekeeping, but they are real
logins on a system carrying PHI.

The `/web/login` user picker on `care.biztinct.com` offers `qa_crm_probe`,
`qa_theme_probe`, `qa_tenant_probe` and `qa_zalo_probe`, all named
"… (temporary)", left behind by earlier phases; `res.partner` 1272 "DS QA
Rep" is another. Conventions §8.5 requires QA fixtures to be deleted and
fresh-cursor verified; these were not. SH-1's own two personas
(`sh1_qa_ops`, `sh1_qa_doctor`) were deleted and verified in a fresh cursor
the same day.

**Precise state, measured by the SH-1 review (2026-08-03):** all four named
accounts are **archived, not deleted** — `qa_tenant_probe` 6373,
`qa_theme_probe` 6374, `qa_zalo_probe` 6363, `qa_crm_probe` 6375, every one
`active = f`. Two more the ticket omitted: `gc3_smoke_probe` 6453 (GC-3) and
`qa_pwa_nurse` 1210. `res.partner` 1272 "DS QA Rep" is `active = t`, as
claimed. So six user rows, five archived and one partner live. Archived
users still appear in some pickers and still own audit rows, which is why
this is worth closing rather than shrugging at.

**Fix shape:** audit `res.users` for probe/temporary logins, confirm with
whoever created them, archive or delete. Cheap, and it shrinks the login
surface.

---

## T-009 — `health.clinical.note` has NO record rule, so every clinical grant is unnarrowed — **SCOPING CLOSED 2026-08-20, commit `f297d18c`; consent question still open**

**Closed by the catchment phase**, not by a security phase —
`health_fieldservice/security/catchment_gap_rules.xml` ships the pair
`clinical_note_catchment_rule` ("Clinical Notes: staff see their own
catchment", bound to nurse + doctor + operations_manager + manager, `r/w/c`,
no unlink) and `clinical_note_catchment_owner_rule` (`[(1,'=',1)]`, owner
only). Live on vietuat as ids **4823** and **4824**, both active. The owner
twin is load-bearing, not decoration: group rules OR together and
`group_healthcare_owner` implies manager, so without it an owner would be
pinned to their own province by their inherited groups.

Verified live 2026-08-20: **all 57 notes carry a `catchment_province_id`
(0 NULL)**, so the rule genuinely narrows and no note falls into the
invisible-to-everyone-but-owner hole that the domain's
`('catchment_province_id','!=',False)` clause would otherwise create. A
doctor in one province can no longer read every note in every province,
which was the ticket's headline.

**Still open — the second half of the fix shape.** The original ticket asked
for the record rule **plus** "a decision on whether the note should also
respect the patient's `data_sharing` consent the way the FHIR facade does".
No such decision is recorded anywhere in `docs/strategy/`, and the shipped
domains are purely geographic — there is no consent clause in either rule. So
a clinician inside the right catchment still reads a note regardless of what
the patient consented to, while the FHIR facade covering the same data does
check. That asymmetry is a clinical-workflow decision, not a security patch,
and it is what remains of this ticket. Do not re-derive the scoping half.

*Original ticket text follows.*

**Found:** SH-1 review (2026-08-03). Verified live **at that time**: the model
had **zero** active `ir.rule` rows.

Every ACL grant on `health.clinical.note` is therefore full-table. Nurse (57
users), operations manager (14), manager/admin/owner and — after SH-1 §3.2 —
doctor (10) all read **all 57 notes** with no catchment, facility, author or
patient-consent scoping. Every sibling PHI model in this codebase is
catchment-scoped: `health.fieldservice.order` carries nine catchment rules,
`res.partner` carries rule 342, `health.condition` and `health.observation`
follow the same ladder.

The SH-1 review removed the receptionist row it had specified, on the grounds
that it widened unnarrowed PHI access to ten front-desk users and bought
nothing reachable. The remaining grants are all clinically justified — but
"justified" and "unscoped" are different claims, and a doctor in one province
can currently read every note in every province.

**Fix shape:** a catchment/facility record rule on `health.clinical.note`
mirroring the FSO rules, plus a decision on whether the note should also
respect the patient's `data_sharing` consent the way the FHIR facade does.
Needs its own phase: it changes what clinicians see, so it is a clinical
workflow decision, not a security patch. Snapshot before/after **by rule
name, not id** (ledger §5.113).

---

## T-010 — 610 `__pycache__` files are tracked in git

**Found:** SH-1 review (2026-08-03). Pre-existing; SH-1 merely made it
visible (`health_fieldservice/models/__pycache__/hr_employee_public.pyc` went
dirty because the source changed, as did `health_redinvoice`'s).

Compiled bytecode is build output. Tracking it means every source change
leaves a phantom dirty binary that no reviewer can read, and "I committed only
my own files" becomes unverifiable.

**Fix shape:** `git rm -r --cached` every `__pycache__` directory and add it
to `.gitignore`, in a commit that touches nothing else so the 610-file diff is
reviewable at a glance. Deliberately NOT done inside SH-1 — a 610-file
deletion landing in the middle of a security review is exactly the kind of
noise that hides a real change.

---

## T-011 — 58 of 69 active internal users are Accounting and HR Administrators

**Found:** SH-2 review (2026-08-03). Measured live, not inferred.

SH-2 removed the *healthcare* over-grant. The **Odoo application** over-grant
is untouched and is much larger. Direct rows in `res_groups_users_rel`, active
holders out of 69 active internal users:

| Group | Active holders |
|---|---|
| `sales_team.group_sale_manager` | 61 |
| `stock.group_stock_manager` | 58 |
| `hr.group_hr_manager` | **58** |
| `account.group_account_manager` | **58** |
| `purchase.group_purchase_manager` | 58 |
| `hr_holidays.group_hr_holidays_manager` | 51 |
| `base.group_system` | 1 ← the two-ring model, intact |

`account.group_account_manager` is full Accounting Administrator over **1,098
journal entries / 3,145 move lines** across 3 companies. `hr.group_hr_manager`
is full HR Administrator over **98 employee records**, including the private
columns this build carries: `birthday`, `private_phone`, `private_email`,
`emergency_contact`.

These are **not** granted by any `access.role`: all ten Doctor-role users hold
the Doctor role and nothing else, yet carry 11–13 direct group rows each. The
rows were assigned outside the role system — almost certainly by duplicating a
template user — and `_update_users_groups()` only ever *adds*, so nothing has
ever taken them away. `base.group_system` at 1 holder proves the platform-admin
ring itself is sound; the failure is the app-manager ring beneath it.

**Why this outranks T-009.** T-009 is 57 clinical notes visible to 10 licensed
clinicians. T-011 is the general ledger and every employee's private contact
details visible to 58 accounts, most of which are field nurses.

**Fix shape:** decide the intended group set per `access.role`, then a
migration that *revokes* direct rows not justified by the holder's role —
revocation is the hard part, since nothing in `access_roles` removes groups.
Needs a before/after snapshot by group xmlid (not id) and a per-persona login
probe, because this is the change most likely to lock someone out of a screen
they use daily. Do **not** fold into a feature phase.

---

## ~~T-012~~ — 8 of the 10 doctors have no catchment province, so catchment rules deny them everything — **CLOSED 2026-08-04, module `health_catchment_backfill`**

**Closed by a one-time backfill module.** `health_catchment_backfill`'s
`post_init_hook` set `catchment_province_id` for every `access.role` "Doctor"
user with none, deriving it from `hr.employee.healthcare_facility_id
.catchment_province_id`. Applied live at install: 8 of 8 backfilled — huynh,
staff_155, staff_203 → Hà Nội (2); staff_130/140/154/205/207 → TPHCM (1) — each
matching their facility, and consistent with the two already-correct doctors.
Idempotent (only NULL rows), doctors only. 6 tests, 0 failed. The remaining
NULL-catchment CLINICAL STAFF are ~41 nurses — deliberately out of scope, now
**T-014**, because populating them EXPANDS patient visibility and is a separate
access decision. Do T-014 (or decide against it) **before** T-009 adds a
catchment rule to `health.clinical.note`, or that rule blackholes them.

*Original ticket text follows.*

**Found:** SH-2 review (2026-08-03).

`res_users.catchment_province_id` is set for exactly two of the ten Doctor-role
users (`dhanoi`=2, `dhcmc`=1). The catchment rule domain used across the
clinical models is

```
['&', ('catchment_province_id','=',user.catchment_province_id.id),
      ('catchment_province_id','!=',False)]
```

which is **unsatisfiable when the user's own field is NULL** — it is a deny-all,
not a pass-through. So of the 26 catchment-narrowed models SH-2's role repair
newly granted, eight of the ten clinicians see **zero rows**.

This is not an SH-2 regression: before the phase those users had no ACL on
those models at all. But it means the phase's "clinical access restored"
holds for two users in the functional sense and ten in the permission sense.

**Fix shape:** populate `catchment_province_id` for the eight (an ops data
task, not a code change), *before* T-009 adds a catchment rule to
`health.clinical.note` — that rule would otherwise blackhole the same eight
users on the notes they can currently read.

---

## T-013 — the deployed `health_base` manifest is not the committed one, and references an untracked file

**Found:** SH-2 review (2026-08-03). **Authored by the concurrent migration
workstream, not by SH-2** — SH-2's `-u health_base` deploy merely re-pushed it.

`addons/health_base/__manifest__.py` in the working tree (and therefore on the
server, md5 `5f283ad2…` vs the committed `6a783eb4…`) inserts
`'data/health_facility_official.xml'` into `data`. That XML is **untracked**.
Consequences: the running code is not described by git, and whoever commits the
working tree next ships a manifest pointing at a file that is not in the
repo — `health_base` then fails to install from a clean checkout.

**Fix shape:** the owner of that workstream either commits
`health_facility_official.xml` or reverts the manifest line. Do not split the
pair. Six `health.facility` rows (1812–1817) already exist on vietuat from that
work, so the seed has already been applied by hand.

---

## T-014 — ~41 nurses share the NULL-catchment deny-all, but populating them expands visibility

**Found:** T-012 fix (2026-08-04). Split out of T-012 rather than folded in.

The same NULL-catchment deny-all (§5.117) that stranded the eight doctors also
covers **~41 active Nurse-role clinical staff** whose province is equally
derivable from their facility (36 at facility 1815 → HCMC, ~13 at 1812 → Hanoi;
`khoa.bv`/`ahanoi`/`ahcmc` have no facility and are not derivable). T-012's fix
was scoped to doctors ONLY, because a doctor's catchment merely completed a
data-entry gap validated by two correct reference rows — whereas backfilling 41
nurses would **grant them patient visibility on 26 catchment-narrowed models
they currently see nothing on**. That is an access expansion, not a data repair,
and needs an explicit decision.

**Two questions to answer first:** (1) is a nurse *supposed* to see every patient
in her province, or is nurse access meant to be assignment-scoped (via
`assigned_staff_ids` on the FSO) rather than catchment-scoped? (2) if catchment
is right, the same `health_catchment_backfill` hook generalises to
`access_role_id.name ilike 'nurse'` in one line. **Do not run it blind** —
confirm the intended nurse access model, because turning it on makes ~41
accounts able to read every patient record in their city.

**Also note (minor):** the single-record snippet path (`filter_id=0`,
`res_model=product.product`, `res_id`) raises a core `KeyError: ''` because an
empty filter has no `field_names`. Pre-existing core behaviour, surfaced by the
T-003 positive control; not introduced by `health_website_security`, which only
gates the model. No leak (it errors before rendering). Left for core, unticketed
beyond this note.

---

*Registered 2026-07-29 during the W3 review close-out; T-003 – T-008 added
2026-08-03 by SH-1; T-009 – T-010 added 2026-08-03 by the SH-1 review;
T-001 closed and T-011 – T-013 added 2026-08-03 by the SH-2 review;
T-003 & T-012 closed and T-014 added 2026-08-04;
T-009's scoping half closed 2026-08-20 (shipped by the catchment phase
`f297d18c` on 2026-08-04 and left unstruck for sixteen days — a closed defect
that still reads open costs the next phase a re-investigation, so strike the
ticket in the commit that fixes it).*
