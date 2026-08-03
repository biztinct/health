# Platform security hardening — phase SH-1 (Opus implementation handover)

**Author:** Fable (design) · **Date:** 2026-08-03 · **Branch:** 19.0
**Companion:** `docs/strategy/HANDOVER-CONVENTIONS.md` (read it first — deploy
workflow §2, gotcha ledger §5, definition of done §8)
**Origin:** the GC-3 review (2026-08-03) plus the two standing tickets in
`docs/strategy/open-tickets.md`, which have now been re-derived by three
independent phases and deserve a phase of their own.

---

## 0. Mission and binding non-goals

**Mission.** Close four access-control defects that live on PHI surfaces, and
repair the ledger that every future handover depends on. Nothing in this
phase adds a feature. Every item is "who can read what", and every item is
verified live before and after.

**Why one phase.** All four are access-control changes on shared modules.
Shipped separately inside feature phases they would each be a drive-by edit
to a security surface — which is exactly what `open-tickets.md` says must not
happen. Shipped together they get one review, one before/after evidence pass,
and one rollback story.

**Binding non-goals — do not do these, no exceptions:**

1. **No new environment, no provisioning, no instance.** Nothing is stood up.
   `/etc/odoo-server.conf` is not edited (it currently reads
   `db_name = vietuat`, `dbfilter = ^vietuat$`, `list_db = False` — correct,
   leave it). The client deferred environment work on 2026-08-03.
2. **No group *creation* and no new roles.** This phase deletes and narrows;
   it does not invent a permission model. If a fix seems to need a new group,
   STOP and report it.
3. **No changes to the FHIR facade's behaviour** beyond what §4 sanctions.
   No new serializers, no new routes, no capability change (the baseline
   test and the weekly cron will both fail you if the CapabilityStatement
   moves — that is intended).
4. **No fixes to F3** (DocumentReference/FSO record-rule mismatch) — it is
   assigned to GC-4 §5.4a. Do not touch the DocumentReference serializer.
5. **No PWA-facing changes**, so conventions §3 (the PWA version bump) does
   not apply. If you find yourself editing anything under `health_pwa/`,
   STOP — you have left the scope.
6. **Do not "tidy" ACL or rule rows beyond the ones §3, §4 and §6 name
   explicitly.** Report anything else you notice. An unrequested ACL edit is
   indistinguishable from a mistake at review time, and §3.4 lists six rows
   that are deliberately being left alone.
7. **Never edit, copy or deploy `addons/mail`.** See §6.0(a) — the repo's
   copy is a stale Odoo 18 snapshot and deploying it would downgrade core
   mail on a running system.

**Modules sanctioned:**
- `health_fieldservice` — `security/ir.model.access.csv` (§3) and
  `models/hr_employee_public.py` (§4) ONLY.
- `health_base` — `security/health_security.xml` ONLY, and only to add the
  one `ir.rule` record specified in §6.2.
- `health_fhir_core` — `serializers/practitioner.py` ONLY (§4).
- `docs/strategy/` — `HANDOVER-CONVENTIONS.md` (§2) and `open-tickets.md`
  (strike T-002's chatter half, add T-003 per §3.4).
- Tests and `i18n/vi.po` in any module you touch, plus manifest version
  bumps for those modules.

Everything else is out of scope. **`health_consent`, `health_pwa`,
`health_emr`, `access_roles`, `health_web_leads` and `addons/mail` are NOT
sanctioned** — if a fix appears to need them, stop and report.

---

## 1. Work items at a glance

**SH-1 — this phase:**

| # | Item | Origin | Surface |
|---|---|---|---|
| §2 | Ledger repair — merge ten unmerged gotcha entries | process gap | docs only |
| §3 | F1 — `base.group_public` reads clinical notes | GC-3 F1 | **PHI ACL** |
| §4 | F2 — Practitioner qualification needs an HR group | GC-3 F2 | employee data |
| §6 | T-002 — chatter AccessError for ops personas | open-tickets | record rule |

Do them in that order. §2 is fifteen minutes and makes the rest of the phase
citable. §3 is the one with a live PHI surface — if you run out of budget,
§3 is the item that must land.

**SH-2 — a SEPARATE phase, specified at §5, NOT part of SH-1.** T-001 turned
out to change effective access for 76 live users and to be entangled with a
broken role mapping (ten doctors currently reach clinical data only through
the defect). It gets its own phase, its own review and its own rollback
story. **Do not implement §5 during SH-1 — not even partially, not even the
"obvious" row deletion.** *(SH-1 is complete and reviewed as of 2026-08-03;
the §5.5 decision it was waiting on has been answered, so SH-2 is now
unblocked and is the next phase to run.)*

---

## 2. Ledger repair — do this FIRST (docs only, ~15 minutes)

**The defect:** ten gotcha entries were written into phase reports and never
merged into `docs/strategy/HANDOVER-CONVENTIONS.md`, which is the document
every kickoff tells the implementer to read first. Live code already cites
one of them — `health_consent/models/health_consent_check_log.py` references
"gotcha ledger §5.99", which currently resolves to nothing. The conventions
ledger stops at §5.97.

**Verified locations — copy from exactly here (do NOT rewrite the prose,
these entries were paid for):**

| Entry | Source file | Line |
|---|---|---|
| §5.98 | `docs/strategy/reports/gc-2-report.md` | 351 |
| §5.99 | `docs/strategy/reports/gc-2-report.md` | 369 |
| §5.100 | `docs/strategy/reports/gc-3-report.md` | 737 |
| §5.101 | `docs/strategy/reports/gc-3-report.md` | 755 |
| §5.102 | `docs/strategy/reports/gc-3-report.md` | 768 |
| §5.103 | `docs/strategy/reports/gc-3-report.md` | 784 |
| §5.104 | `docs/strategy/reports/gc-3-report.md` | 796 |
| §5.105 | `docs/strategy/reports/gc-3-report.md` | 810 |
| §5.106 | `docs/strategy/reports/gc-3-report.md` | 822 |
| §5.107 | `docs/strategy/reports/gc-3-report.md` | 843 |

**Task:** append all ten to §5 of `HANDOVER-CONVENTIONS.md`, in numeric
order, after the current last entry (§5.97), matching the existing entry
formatting exactly (`- **§5.NN — <one-line rule>.** <body> (Phase X.)`).
Preserve the text verbatim; you may only adjust markdown indentation to match
the surrounding entries and append the phase attribution if it is missing.

**Then add one NEW entry of your own, §5.108, recording this very failure:**
that a gotcha written only into a phase report does not exist for the next
phase, because the kickoff points at the conventions doc and nothing else;
the merge belongs in the same commit as the report. Keep it short.

**Verify:** `grep -c '§5\.10[0-7]' docs/strategy/HANDOVER-CONVENTIONS.md`
returns ≥ 8, and every `§5.9x`/`§5.10x` reference in the addons source now
resolves to a real entry.

---

## 3. F1 — unrestricted `base.group_public` read on three PHI models

**This is the item that must land.** GC-3 reported it as one ACL row on
clinical notes. The design investigation found it is a **pattern of four rows
in one file**, covering three PHI-bearing models, with **no record rules
narrowing any of them**, and a **reachable unauthenticated primitive** that
exercises it.

### 3.0 Verified facts — do NOT re-derive

**The four rows, all in `addons/health_fieldservice/security/ir.model.access.csv`:**

| CSV line | Model | Group | Live rows | Narrowed by a rule? |
|---|---|---|---|---|
| 75 | `health.clinical.note` | `base.group_public` | 57 | **No — zero `ir.rule` on the model** |
| 24 | `health.fieldservice.order` | `base.group_public` | **1269** | **No** — 9 rules exist but every one is group-bound, so none matches the public user |
| 60 | `health.appointment` | `base.group_public` | 0 | **No** |
| 59 | `health.appointment` | `base.group_portal` | 0 | **No** |

**Odoo rule semantics that make this a real hole (know this before you touch
anything):** global rules AND together, group rules OR together, and **when
no group rule matches the acting user, nothing narrows the ACL at all.** The
nine FSO rules are all group-bound to healthcare roles, so they do not
constrain `base.group_public` — the public user gets unrestricted read of all
1269 field-service orders, which carry patient identity, address, service
type, assigned staff and symptoms. Contrast the one correctly-narrowed public
grant in the system: core `res.partner`'s public row is bounded by
`[('id','child_of',user.commercial_partner_id.id)]`, which is why patients
are not exposed through it.

**The reachable primitive.** `POST /mail/thread/data` is `auth='public'`,
`type='json'` (so no CSRF token), and takes a caller-supplied `thread_model`
— `addons/mail/controllers/thread.py:16-25`. `health_emr` makes the note a
mail thread (`addons/health_emr/models/health_clinical_note.py:75-78`;
confirmed live — `message_ids`/`message_follower_ids`/`activity_ids` all exist
on the model). The gate is `_get_thread_with_access` →
`thread.sudo(False).has_access(mode)` at
`addons/mail/models/mail_thread.py:4774-4778`, which returns **True** for the
anonymous public user given the ACL row and no record rule. The response then
carries `hasReadAccess: True` instead of the
`{hasReadAccess: false, hasWriteAccess: false}` stub.

**What it does and does not leak — do not overstate this in the report.** It
is an **unauthenticated enumeration and existence oracle**, not a content
dump: with `fields=None` the payload is `_read_format([])`, i.e. ids only
(`mail_thread.py:4703-4709`), and every optional sub-payload is blocked by its
own ACL for the public user (`mail.followers`, `mail.activity`,
`mail.scheduled.message`, `ir.attachment` — all verified live). Writes are
closed: no health module sets `_mail_post_access`, so it stays the core
default `'write'`, which public lacks. **53 `mail_message` rows exist on
clinical notes**, and `mail.message` does carry a public read row whose
document-access rule would transitively unlock them — the only saving grace is
that `/mail/thread/messages` is `auth='user'`. The ACL row is what keeps that
second-order hole armed.

**Deletion is safe — verified four ways:**
1. Every public/tokenized controller that touches these models resolves
   through `.sudo()`: `health_portal/controllers/portal_public.py:33-47`,
   `health_family_link/controllers/family_public.py:38`,
   `health_family_messages`, `health_self_booking`, `health_telehealth`,
   `health_workflow_auto`. A grep across all six for `request.env[` without
   `.sudo()` returns **zero hits**.
2. **No test** references the group: `grep -rn "group_public\|public_user\|_is_public" addons/health_*/tests/` → zero hits.
3. The 13 health-module references to `group_public` are all **rejection
   guards** — controllers refusing to serve the public user (e.g.
   `health_pwa/controllers/api.py:31`, `health_consent/controllers/api.py:39`).
   Deleting the rows makes them redundant, never wrong.
4. `base.group_public` (id 11) has exactly one member: uid 3, login `public`.
   **Its `active = f` is NOT a mitigation** — `auth='public'` binds
   `env.ref('base.public_user')` directly rather than authenticating a login,
   so the inactive flag never gates the request. Treat the row as live.
   The 54 `health_base.group_healthcare_patient` users are unaffected: that
   group has zero `res_groups_implied_rel` rows in either direction.

**Deletion mechanics — no migration needed (unlike §5).** The xmlid
`health_fieldservice.access_health_clinical_note_public` has
`ir_model_data.noupdate = false`, so **removing the CSV line deletes the row
on module upgrade.** Live row ids for your before/after snapshot: 6396 nurse,
6397 ops-manager, **6398 public (delete)**, 6399 owner.

### 3.1 Delete the four rows

Remove lines 24, 59, 60 and 75 from
`addons/health_fieldservice/security/ir.model.access.csv`. Nothing else in
that file changes in this step.

### 3.2 Add the clinical ladder the public row was masking

`group_healthcare_doctor` has **no read at all** on `health.clinical.note`
(it implies only `group_healthcare_base` →
`health_base/security/health_security.xml:52`), yet `health_emr` ships an
"Unsigned Clinical Notes" **sign-off worklist** whose entire purpose is
doctors finalizing notes (`health_emr/views/health_clinical_note_views.xml:98`,
menu at `:110-114`, surfaced in the CMS sidebar at
`health_cms_coverage/data/cms_sidebar_items_features.xml:144-145`). A model no
doctor can read is a functional defect that the public row was hiding.

**Clone the house ladder — do not invent one.** The precedent is
`addons/health_condition/security/ir.model.access.csv:2-9`, which is the
sidecar model of `health.clinical.note` itself: receptionist `1,0,0,0` /
nurse `1,0,0,0` / head_nurse `1,1,1,0` / doctor `1,1,1,0` /
operations_manager `1,0,0,0` / manager `1,1,1,0` / admin `1,1,1,0` /
owner `1,1,1,1`. Same shape in `health_vitals` (`health.observation`),
`health_consent` and `health_emar`.

**Add exactly two rows** — `group_healthcare_doctor` (`1,1,1,0`) and
`group_healthcare_receptionist` (`1,0,0,0`) — and **leave the existing four
rows untouched**. Do not restructure the nurse/ops/owner rows to match the
ladder exactly; that is a wider change than this phase sanctions, and the
existing rows already work. Note in your report that the result is a hybrid.

**Effective read today, for your before/after table** (via implication —
`health_security.xml:45,82,89,96`): nurse, head_nurse, manager, admin, owner,
operations_manager, and `base.group_public`. Genuinely zero: **doctor**,
receptionist, sales, finance, patient-portal.

### 3.3 The regression test — test the exploit, not the row

**T3.1 (required, HttpCase).** Unauthenticated `POST /mail/thread/data` with
`thread_model='health.clinical.note'` and a real note id must come back with
`hasReadAccess` false. Assert on the response, not on the ACL table — the ACL
row is the cause, the oracle is the defect. Note the investigation did **not**
execute this probe live (read-only constraint), so **your run is its first
execution**: if it does not behave as described, that is a finding to report,
not a test to adjust until it passes.

**T3.2.** Same probe for `thread_model='health.fieldservice.order'` — but
first check whether that model actually inherits `mail.thread`. The
investigation flagged this as unverified. If it does not, say so and skip the
assertion with a comment rather than writing a test that proves nothing.

**T3.3.** A `base.group_healthcare_doctor` user can read and create a
clinical note (the §3.2 grant works).

**T3.4.** A `base.group_public`-only user gets `AccessError` on
`health.clinical.note`, `health.fieldservice.order` and `health.appointment`
— the direct negative for §3.1.

**T3.5.** The tokenized portal path still works: `/my/care/<token>/records`
returns 200 for a valid token after the rows are gone (it is sudo'd, so it
must be unaffected — prove it). Note that `emr_state='final'` count is **0**
on vietuat today, so the records list is legitimately empty; assert on the
HTTP status and page render, not on note content.

### 3.4 Report, do NOT fix

- **Doctors also have no `health.fieldservice.order` read**
  (`ir.model.access.csv` has FSO rows for nurse, ops-manager, owner and
  public only), so the FSO form and possibly the Unsigned Notes worklist may
  still not render for a doctor after §3.2. **Check whether the worklist
  renders; report the answer honestly either way.** Granting doctors read on
  1269 field-service orders is a wider decision than this phase makes.
- **Six non-PHI public/portal rows remain** in the same file:
  `health.portable.equipment` (25), `health.clinical.protocol` (26),
  `health.staff.skill` (49), `health.service.area` (50),
  `health.staff.assignment` (47, portal),
  `health.staff.availability.matrix` (48, portal). Left deliberately — some
  may legitimately serve a public website page (a coverage map, a services
  list), and each needs its own check. List them as a follow-up ticket.
- **`/website/snippet/filters`** (`addons/website/controllers/main.py:417-426`
  → `website_snippet_filter.py:61-84`) accepts a caller-supplied
  `res_model`/`res_id` and renders through a **sudo** recordset, guarded only
  by an `assert '.dynamic_filter_template_' in template_key`. It is
  independent of F1 and this fix does not close it. Raise it as a new ticket
  in `docs/strategy/open-tickets.md` (T-003) with that evidence; do not
  investigate further in this phase.
- **A group-implication cycle** exists between
  `health_base.group_healthcare_admin` and
  `health_cms_sidebar.group_cms_sidebar_admin` (each implies the other).
  Noted, unrelated, report only.

---

## 4. F2 — Practitioner qualification requires an HR-privileged token

**What is wrong.** `/fhir/r4/Practitioner` returns 403 for a service user
without an HR group, because `PractitionerSerializer.to_fhir` reads
`healthcare_skill_ids` for `Practitioner.qualification`, and `hr.employee`
treats every field outside its public-profile whitelist as private. GC-3
fixed the blanket-prefetch half of this (D9) and correctly declined to fix
the rest; this is the rest. Live evidence is in the GC-3 report §1.3 and the
smoke transcript (`FHIR-SMOKE type Practitioner: HTTP 403`).

**Verified plumbing — do NOT re-derive:**

- The whitelist mechanism is `addons/hr/models/hr_employee.py:1134-1137`:
  `_check_private_fields` treats a field as public **iff a field of that name
  exists on `hr.employee.public`**. There is no separate list to edit.
- `healthcare_skill_ids` is defined at
  `addons/health_fieldservice/models/hr_employee.py:134` — a Many2many to
  `health.staff.skill` through `employee_healthcare_skill_rel`.
  **The GC-3 report says the remedy is "one entry in health_base's
  public-employee whitelist". That is wrong on the module** — the field lives
  in `health_fieldservice`, and so does the public-model extension. Fix it
  there.
- The extension point already exists:
  `addons/health_fieldservice/models/hr_employee_public.py` inherits
  `hr.employee.public` and already publishes ~50 fields. Clone that file's
  own pattern; `skill_level` (line 74) is the sibling skills field.
- `hr.employee.public` is `_auto = False` — a SQL view
  (`addons/hr/models/hr_employee_public.py:14`, `init()` at line 194). A
  Many2many needs no column in that view (it lives in its own relation
  table), so no view regeneration should be required — **but verify the read
  actually works rather than assuming it, and if the view does need
  regenerating, report that rather than editing core `hr`.**
- The comodel ACL is already open enough: `health.staff.skill` grants read to
  `base.group_user` at
  `addons/health_fieldservice/security/ir.model.access.csv:41`. No ACL change
  is needed for this item.

**The security question, already decided — do not re-litigate.** Exposing
staff skills on the public employee profile is consistent with a decision
this codebase already made: `license_number`, `license_expiry`,
`specializations`, `qualifications`, `certifications` and `years_experience`
are **already** on `hr.employee.public`
(`health_fieldservice/models/hr_employee_public.py:8-13`). Professional
credentials are already public-profile data here; a skills list is the same
class of information, and it is precisely what FHIR `Practitioner.
qualification` is for. Note in your report that this widens skill visibility
to any user who can read the public employee profile.

**Implement:**
1. Add `healthcare_skill_ids` to
   `health_fieldservice/models/hr_employee_public.py`, declared with the SAME
   comodel, relation table and column names as the `hr.employee` definition,
   `readonly=True`, under the existing "Skills and Qualifications" comment
   block beside `skill_level`.
2. In `health_fhir_core/serializers/practitioner.py`: add
   `healthcare_skill_ids` to `prefetch_fields`, and **replace** the comment
   at lines 41-46 that says the field is "deliberately ABSENT" — that comment
   documents the old state and will mislead the next reader. Say instead that
   the field is published on `hr.employee.public` by health_fieldservice, and
   cite this phase.
3. Version-bump both touched modules' manifests.

**Tests (numbered, both required):**
- **T4.1** — as a user holding ONLY a minimal service group (no
  `hr.group_hr_user`), `env['hr.employee'].browse(id).fetch(['healthcare_skill_ids'])`
  succeeds. Clone the minimally-grouped-user fixture from GC-1's Patient
  prefetch test rather than inventing one (§5.102: an admin-grouped fixture
  cannot see this class of bug at all — if your test user is admin, the test
  is worthless).
- **T4.2** — `PractitionerSerializer` serializes a real employee for that
  same minimal user and the resulting resource carries a `qualification`
  entry. Assert on serializer OUTPUT, not on the field read.

**Live proof required in the report:** re-run
`tools/fhir_deploy_smoke.sh <version>` in token mode if ops has a token
available, and show `Practitioner` returning a 200 Bundle. If no token is
available, say so plainly and give the T4.2 output instead — do NOT create or
activate an OAuth client for this (`smoke_test_client` is OPS-owned; GC-3
used a throwaway and destroyed it, and repeating that is acceptable ONLY if
you destroy it and prove the destruction in a fresh cursor, per §5.34/§6).

---

## 5. Phase SH-2 — T-001, the inverted group implication (NOT part of SH-1)

**Do not implement this during SH-1.** It changes effective access for 76
live users, it cannot be done safely without a paired role repair, and it
needs a business decision the user must make first (§5.5). It is specified
here so the decision can be taken against real facts.

### 5.0 Verified facts — do NOT re-derive

**The edge is present.** `res_groups_implied_rel` holds `(gid=1, hid=346)` —
`base.group_user` implies `health_base.group_healthcare_base` — **forming a
cycle** with the declared `346 → 1` at
`health_base/security/health_security.xml:23`. Because 15 other groups imply
`base.group_user`, all of them transitively reach 346 as well. (Note: Odoo 19
`res_groups` has **no `category_id`** — it is `privilege_id` →
`res_groups_privilege`. A `category_id` query errors out.)

**We authored it, and the comment says why.** `health_base/data/menu_access.xml`
before commit `8be03c5e` contained
`<field name="implied_ids" eval="[(4, ref('group_healthcare_base'))]"/>` on a
`base.group_user` record, under the comment *"Give base users healthcare
access for debugging"*. It applied at install time on 2025-12-06. Not a manual
grant, not `access_roles` (audited — it only ever writes
`res.users.group_ids`, never `res.groups.implied_ids`).

**The fix already in the repo is permanently dead code.** Commit `8be03c5e`
flipped it to `(3, …)` (unlink) at `menu_access.xml:8`. That write is silently
dropped on every upgrade: `base.group_user`'s own `ir_model_data.noupdate` is
`true`, and `odoo/orm/models.py:5157` skips `to_update` when
`update and d_noupdate`. This is the *noupdate seed cutover* gotcha in its
purest form. **Therefore the row must be deleted directly — XML cannot do
it.** Precedent on this exact database, from commit `a201b3d1`: *"deleted
DB-only implied row 356→4 so Healthcare: Owner no longer grants system
admin"*. Manual row deletion is the established, accepted remedy here.

**No resurrection risk** once deleted: no module XML or Python links 346 into
1 any more (the eight `(4, ref('…group_healthcare_base'))` hits elsewhere are
all the correct `X → 346` direction).

**Blast radius, measured.** 76 active internal users; **18 ACL rows** and 7
menus gated on group 346; **zero record rules** (so no rule-widening to
reason about). The ACLs include `health.ews.score` read — the ticket's
headline — and, not in the ticket, **`health.fso.clinical.notes.wizard` at
full `1,1,1,1`**, a clinical-note entry surface. The closure is flat: 346
implies only `base.group_user`, so the leak is exactly group 346's own grant
surface and nothing deeper.

**Out of scope, do not confuse:** 17 further `health.*` ACLs are granted
**directly to `group_id=1`** and are untouched by deleting the edge
(`health.appointment`, `health.staff.assignment`, `health.pwa.config`, the
`health.*.wizard` family, …). Deleting the edge does not close those.

### 5.1 THE BLOCKER — deleting the edge alone locks out 21 users

**21 active users lose group 346 entirely**, and **ten of them are doctors**:
`dhanoi`, `dhcmc`, `huynh`, `staff_130`, `staff_203`, `staff_205`,
`staff_207`, `staff_140`, `staff_155`, `staff_154`.

The root cause is a second defect the edge has been masking: **`access.role`
id 6 "Doctor" grants `base.group_user` and nothing else** — not even
`health_base.group_healthcare_doctor` (id 350), which exists and is correctly
wired in XML. Ten real clinicians reach every healthcare menu, the landing
dashboard, the Client Registry and the FSO wizards *solely through the bug*.
The Doctor role was almost certainly built this way because the edge already
made it work.

Roles 3 (Branch Manager), 4 (Banker) and 8 (Admin) also lack
`group_healthcare_base`; roles 1, 2, 5, 7, 9 are correctly mapped.

**Therefore the role repair is part of this fix, not a follow-up.**

### 5.2 Implement — in this order, nothing skipped

1. **Snapshot first.** Capture, as psql output committed to the report: the
   full `res_groups_implied_rel` rows for `gid=1`; the recursive closure of
   `base.group_user`; the 18 ACLs and 7 menus gated on 346; and the complete
   list of users who would lose 346, with their `access.role` and their
   direct groups. This snapshot is the rollback plan — re-inserting one row
   restores the previous state exactly.
2. **Repair the Doctor role**: add `health_base.group_healthcare_doctor`
   (id 350, which already implies 346 via `health_security.xml:52`) to
   `access_role` id 6. Do it through the `access_roles` module's own data/API,
   not by hand-writing the relation table, and make it reproducible.
3. **Apply the §5.5 decision** for the remaining affected accounts.
4. **Delete the row** `(gid=1, hid=346)` — and ship a
   `health_base/migrations/<new-version>/post-migrate.py` that performs the
   same deletion idempotently, so any other database converges. Bump the
   `health_base` manifest version to match the migration directory. Leave the
   `(3, …)` lines in `menu_access.xml` in place and add a comment noting they
   are inert on upgraded databases and the migration is what does the work.
5. **Re-run the closure query** (§5.88 rule b) and prove `346` is no longer
   reachable from `base.group_user`.

**Scope discipline:** change the ONE row. Eleven other forward edges hang off
`base.group_user` and they are the legitimate Odoo settings-toggle mechanism.
In particular **do not touch `1 → 7` (`base.group_no_one`)** — it is
load-bearing for documented rationale in
`health_user_admin/models/res_users_saas.py:23-28` and
`access_role_saas.py:32-38`, both of which explain that `group_no_one` must
stay a *direct-only* check precisely because `base.group_user` implies it. An
implementer "tidying up all of `base.group_user`'s forward edges" would
invalidate both files' reasoning.

### 5.3 The two-ring model is unaffected — verified

346 has exactly one outgoing edge (`346 → 1`); `base.group_system`'s edges
are all outgoing; there is no `1 → 4` and no `356 → 4`. The transitive guards
in `res_users_saas.py:40-46` and `access_role_saas.py:50-63` test against
`{base.group_system, base.group_erp_manager, access_roles.access_role_group_administrator}`,
none of which is reachable from 346. No role's `is_privileged` computation
changes. `ALLOWED_PRIVILEGE_NAMES` already includes `'Healthcare'`, so tenant
admins are *meant* to hand out healthcare groups through roles — which is the
path this fix restores.

### 5.4 Tests

**T5.1 — the ticket's own acceptance test.**
`addons/health_web_leads/tests/test_web_leads_w2.py:372-395`
(`test_w2_08b_ews_read_survives_and_it_is_not_ours_to_close`) currently
**self-skips** when the implication is gone (`:388-390`), so after this fix it
goes green vacuously. **Rewrite it into a positive assertion:** a
`base.group_user`-only user must raise `AccessError` on `health.ews.score`.
A permanently-skipped test is not evidence.

**T5.2** — same negative for `health.fso.clinical.notes.wizard`.

**T5.3** — each of the ten doctors' effective closure still contains 346
after the role repair (assert via the live-closure helper, not by reading XML
— §5.88 rule a).

**T5.4** — the `_live_closure` guards at `test_web_leads_w3.py:542` and
`test_web_leads_connector.py:584` stay green.

**T5.5** — `svc_web_leads`: run the full web-leads suites and confirm they
pass without group 346. Its `implied_ids eval="[(5, 0, 0)]"` narrowing
(`health_web_leads/security/web_leads_security.xml:41`) is deliberate W2 work;
if something fails, report it rather than granting the service user
healthcare groups.

### 5.5 THE DECISION THE USER MUST MAKE BEFORE THIS PHASE RUNS

Ten doctors are handled by the role repair (§5.2.2). Three demo accounts
(`demo`, `dds_DemoLead`, `dds_DemoAsst`) and one service account
(`svc_web_leads`) should lose healthcare access — that is the fix working.
**Seven real accounts are genuinely ambiguous** and the phase must not guess:

| User | Role | Direct healthcare groups |
|---|---|---|
| `nam.lh` | Banker | none |
| `anh.pd`, `mai.vt`, `tuan.hm`, `ha.dt`, `huong.nt`, `bao.tq` | **none assigned** | none |

**ANSWERED BY THE USER 2026-08-03 — decision made, do NOT re-litigate and do
NOT apply any fallback.** All seven accounts are unused. **They lose
healthcare access along with everyone else: grant them nothing, assign them
nothing, preserve nothing.**

So the rule for the whole phase is now uniform and simple:

- The **ten Doctor-role users** keep access, via the role repair in §5.2.2 —
  that is the only mitigation this phase applies.
- **Every other affected account loses group 346**: the seven above, the three
  demo accounts (`demo`, `dds_DemoLead`, `dds_DemoAsst`) and `svc_web_leads`.
  That is the fix working as intended, not breakage to be worked around.

**Add T5.6:** after the change, assert that a `base.group_user`-only user
holding no healthcare group cannot read `health.ews.score` (this is T5.1) and
that the seven named accounts' effective closures no longer contain group 346.
List each of the 21 affected logins in the report with its before/after
closure verdict — the point of the phase is that access is now explicit and
auditable, so the report must show it.

**Do NOT archive or delete any of these accounts.** The user said they are
unused, not that they should be removed; deactivating real logins is a
separate action nobody authorised. If you think they should be archived, say
so in the report as a recommendation.

Also unresolved, flag rather than assume: who removed the sibling `4 → 356`
edge is not established (`a201b3d1` documents deleting `356 → 4`, the opposite
direction), and the dormancy of the affected accounts cannot be concluded from
`res_device_log` alone.

---

## 6. T-002 — chatter AccessError for ops personas

The ticket is real but **two of its three key facts are wrong**. Read 6.0
before touching anything.

### 6.0 Verified facts — do NOT re-derive

**(a) The repo's `addons/mail` is NOT the code that runs on the server, and
copying it would be a catastrophe.** The vendored copy is an Odoo-18-era
snapshot: `addons/mail/__manifest__.py:5` says version `1.18`,
`models/models.py` is 509 lines, and it still imports `odoo.osv.expression`
(removed in Odoo 19). The live `/odoo/odoo-server/addons/mail` is version
`1.19` with a 926-line `models/models.py`. **The offending code does not
exist in the repo copy at all.** Because the deploy procedure copies repo
modules *into* the core addons directory, deploying `addons/mail` would
downgrade core mail to Odoo 18 on a running system. **Do not edit, do not
copy, do not deploy `addons/mail`. Do not "fix" it by syncing it.** Report
this as a NEW ledger gotcha — a stale vendored copy of a core module that
looks authoritative in the repo and is nothing of the kind.

**(b) The partner id in the ticket is wrong.** `base.partner_root` is
**`res.partner` id 2** — "Viet Uc Care", the OdooBot partner renamed by
`biz_debranding`. Id 1 is `base.main_partner`, "VIET UC", the company partner.
**A fix hard-coding id 1 will not fix the bug.**

**(c) There are two unsudo'd reads, not one**, both in the live
`mail/models/models.py`: line **406** (in `_message_get_default_recipients`,
which the composer and mail templates drive) and line **557** (in
`_message_get_suggested_recipients_batch`, which every chatter drives). Both
dereference `email_normalized` on the root partner. The chatter reaches it
unconditionally: `chatter_patch.js:271-281` always includes
`"suggestedRecipients"` in its `requestList` → `_thread_to_store`
(`mail_thread.py:5048-5051`) → `models.py:486` → 557. A rule-based fix closes
both; a targeted `sudo()` on one `env.ref` would close only one.

**(d) Why it denies, precisely.** For uid 40 (`crm`) the applicable rules are
global rule 2 (`res.partner company`) plus group rules 340 (`User: Own Partner
Record`, `[('id','=',user.partner_id.id)]`) and 618 (`Healthcare CRM Partner`,
catchment + is_patient/caregiver/payer/referrer). Partner 2 fails **both**
group rules, so their OR-union is empty and the record is denied. The global
rule passes and is not the cause. Verified analytically with a SELECT-only
domain simulation — no writes were made. Clinical staff never saw this because
rule 342 (`Healthcare Staff: Patient and Business Partners`) carries an
`('is_patient','=',False)` branch that matches partner 2; uid 40 holds none of
the groups rule 342 applies to.

**(e) Blast radius: 16 active internal users**, including `crm` (uid 40),
`accounts`, `dhcmc`, `huynh`, seven `staff_*` accounts, `svc_web_leads` and
four demo accounts.

**(f) What partner 2 actually contains** (full row inspected): `name='Viet Uc
Care'`, `email='bot@example.com'`, `active=f`, `company_id=1`,
`partner_share=f`, `type=contact` — and no street, phone, mobile, VAT, bank
data, attachments or PHI. Granting internal users read on it discloses two
strings.

### 6.1 THE TRAP — read this twice before writing the record

`ir.rule` combination semantics, from
`/odoo/odoo-server/odoo/addons/base/models/ir_rule.py:150-171`: **group rules
are OR-ed together (`:170`); global rules are AND-ed (`:171`)**, and
`_compute_global` (`:54-56`) makes a rule global **iff its `groups` field is
empty**.

So a new `res.partner` rule with domain `[('id','=',2)]` and **no `groups`
field** becomes a *global* rule, gets AND-ed into every partner query for
every user, and **collapses the entire partner table to one record for the
whole system.** That is a total-outage-shaped mistake, and it is one omitted
line away.

**Non-negotiable:** the record MUST carry
`<field name="groups" eval="[(4, ref('base.group_user'))]"/>` and MUST be
`perm_read` only (`_get_rules` filters on `r.perm_<mode>` at `ir_rule.py:124`,
so a read-only rule cannot grant write on the root partner). With `groups`
set, the widening is exactly `{partner 2}` — `Domain.OR` cannot leak past the
global rule's AND.

### 6.2 Implement — one XML record in `health_base`

**Where:** `addons/health_base/security/health_security.xml`, in the
`res.partner` rule block at lines 108-170. **Clone
`rule_user_own_partner` at :108-117** — same shape, same field order.

**The domain cannot use `ref` or `env`.** The `ir.rule` eval context is only
`{user, company_ids, company_id}` (`ir_rule.py:38-51`), so
`[('id','=',ref('base.partner_root'))]` fails at evaluation time, and
hard-coding `2` is database-specific. Bake the id **at XML load** using `eval`
on the Text field, exactly as
`addons/health_user_admin/security/ir_rules.xml:23` already does:

```xml
<field name="domain_force"
       eval="'[(\'id\', \'=\', ' + str(ref('base.partner_root')) + ')]'"/>
```

Name it something a future reader understands without this document, e.g.
`rule_internal_read_root_partner`, with an XML comment stating: core mail
reads `base.partner_root.email_normalized` unsudo'd in two places, so every
internal user needs read on that one record or every chatter raises.

`health_security.xml` has no `noupdate` wrapper and every health_base partner
rule carries `ir_model_data.noupdate = false`, so the record installs cleanly
and future edits apply on upgrade — no seed-cutover problem, no migration.

### 6.3 Tests

**T6.1 (positive).** Clone the ops persona from
`addons/health_web_leads/tests/test_web_leads_w3.py:38-59` — it already builds
a `base.group_user` + `sales_team.group_sale_manager` +
`health_crm.group_health_crm_manager` +
`health_base.group_healthcare_operations_manager` user with a catchment
province, which reproduces uid 40's effective rule set. Drive
`rec.with_user(ops)._message_get_suggested_recipients_batch(reply_discussion=True, no_create=True)`
on a `mail.thread` record the persona can read, and assert it does **not**
raise. **§5.4 applies with full force: a uid-1 test cannot see this bug at
all** — `_get_rules` returns an empty recordset when `self.env.su`
(`ir_rule.py:118-119`). If your test passes before the fix, your test is
wrong.

**T6.2 (the anti-trap negative — required).** Assert the rule widened the
persona's readable partner set by **exactly one record**. Capture
`env['res.partner'].with_user(ops).search([])` ids before and after; the
difference must be `{2}` and nothing else. This is the test that catches the
global-rule mistake, and it is the most important test in this phase.

**T6.3 (write is still denied).** The persona can read partner 2 but must
still fail to write it.

**T6.4.** The existing `_live_closure`-guarded web-leads suites
(`test_web_leads_w3.py:542`, `test_web_leads_connector.py:584`) stay green.

### 6.4 Browser evidence — required for this item only

Per conventions §8.5, and because the entire defect is a dialog a human sees:
drive a real chatter render on `care.biztinct.com` as an ops persona via
chrome-devtools, showing the AccessError dialog is gone. Include the console
log and the exact click path from a normal entry point.

### 6.5 Report, do NOT fix

- **The "CMS Contacts list" half of T-002 is unverified.** The investigation
  confirmed only the chatter/composer path. A plain `res.partner` list does
  not traverse `mail/models/models.py`, so if the CMS Contacts list really
  raises, the cause is different — most likely rule 618 denying non-patient
  partners — and this fix will not address it. **Do not widen the fix to chase
  it.** Reproduce it if cheap; either way, split it into its own ticket in
  `docs/strategy/open-tickets.md` and strike T-002 only for the chatter path
  you actually fixed.
- The stale vendored `addons/mail` from 6.0(a), as a ledger entry.

---

## 7. Deploy, evidence and report-back

**Deploy** per conventions §2 — scp to `/tmp`, `sudo cp` with `odoo:odoo`
ownership, stop / `sleep 6` / start / `sleep 12`, then verify: `pgrep -fc
odoo-bin` shows the full complement (master + 2 workers + cron + gevent) and
`curl -s -o /dev/null -w '%{http_code}' http://localhost:8069/web/login`
returns 200. **Never `systemctl restart`.**

**Test invocation:** HttpCase tests need BOTH no `--no-http` AND
`--workers=0` (§5.75 and the HttpCase rule in conventions §2). Run on the
spare port (`--http-port=8079 --max-cron-threads=0`) so you do not disturb
the live service. An `EXIT:1` with `FAIL: 0` means read the ERROR lines.

**Evidence discipline for this phase specifically — this is a security
change, so "the tests pass" is not sufficient evidence:**

1. **Before/after ACL and rule snapshots.** For every ACL row and every
   `ir.rule` you add, remove or modify, capture the live state BEFORE the
   upgrade and AFTER, as psql output, in the report. A security change with
   no before/after is unreviewable.
2. **A negative test per item** — assert that the thing that should now be
   denied IS denied, not merely that the allowed path still works. Every item
   in §3–§6 has an obvious negative; write it.
3. **Fresh-cursor verification** of any fixture you create, and delete the
   fixtures (§5.34, §6).
4. No browser evidence pack is required — nothing user-facing changes —
   **except for §6**, where the whole defect is a dialog a human sees. For
   §6 drive a real chatter render as the ops persona per conventions §5.4 and
   include the console output.

**Report-back — write to `docs/strategy/reports/sh-1-report.md`, commit it,
and paste it in your reply:**

- Per item: what changed, the before/after snapshot, the negative test.
- The ten merged ledger entries confirmed present, plus your §5.108.
- Anything you found and did NOT fix, as a numbered finding (the adjacent
  ACL rows from §3's sweep especially).
- Every deviation with its reasoning.
- Verbatim `odoo.tests.result` line(s), and the executed-test count — a
  count of failures is not evidence a suite ran (§5.83).
- Any NEW gotcha, flagged for the ledger — **and this time merge it into
  `HANDOVER-CONVENTIONS.md` in the same commit** (that is §5.108's whole
  point).

---

## 8. Review protocol

The user reports "opus done" → Fable auto-reviews first: a bulk review in ONE
subagent (whole diff vs this spec + independent live verification of every
ACL and rule change — implementer QA claims are not trusted), then a personal
read of the security-bearing files, then small fixes shipped directly and
larger ones handed back as a fix-list.

**Phase order from here:** SH-1 (this) → **SH-2** (§5, once the user has
answered §5.5) → GC-4 (§5 of `docs/strategy/handovers/hl7-gap-closure.md`,
environment-deferred) → GC-3.5 (§4.6 there) whenever a second environment is
actually wanted.

---

## 9. Kickoff (paste into the Opus session, verbatim)

**SH-1:**

Implement Phase SH-1 (sections 2, 3, 4 and 6 ONLY — NOT section 5) specified
in docs/strategy/handovers/platform-security-hardening.md.

Then the canonical block from `docs/strategy/KICKOFF-TEMPLATE.md` with
`<PHASE-DOC>` = `platform-security-hardening`.

**SH-2** (issued separately, after the SH-1 review AND after the user has
answered §5.5):

Implement Phase SH-2 (ONLY section 5) specified in
docs/strategy/handovers/platform-security-hardening.md.
