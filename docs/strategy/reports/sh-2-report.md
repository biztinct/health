# Phase SH-2 — T-001, the inverted group implication (implementation report)

**Implementer:** Claude Opus 5 · **Date:** 2026-08-03 · **Branch:** 19.0
**Spec:** `docs/strategy/handovers/platform-security-hardening.md` §5 ONLY
**Deployed to:** vietuat · **Result:** `0 failed, 0 error(s) of 85 tests`
**Evidence:** `docs/strategy/reports/sh-2-evidence/`

---

## 0. What changed, in one paragraph

One row was deleted from `res_groups_implied_rel` — `(gid=1, hid=346)`, the
undeclared `base.group_user → health_base.group_healthcare_base` implication
that handed every internal user on this database the whole healthcare-base ACL
surface. Before deleting it, `access.role` id 6 "Doctor" was repaired so the
ten clinicians who reached healthcare data *only* through the defect keep it
through an explicit grant. After deleting it, the seven accounts the user
declared unused were archived. All three steps live in one idempotent
migration, `health_base/migrations/19.0.1.3.8/post-migrate.py`, because the
`(3, …)` XML fix already in the repo is permanently dead code. Effective
access changed for 24 accounts: **10 keep it explicitly, 14 lose it as
designed.**

---

## 1. Files changed

| File | Change |
|---|---|
| `addons/health_base/migrations/19.0.1.3.8/post-migrate.py` | **NEW** — the whole phase: role repair → edge deletion → archive |
| `addons/health_base/__manifest__.py` | version `19.0.1.3.7` → `19.0.1.3.8` (matches the migration dir) |
| `addons/health_base/data/menu_access.xml` | comment only — records left in place, documented as inert |
| `addons/health_base/tests/test_sh2_group_implication.py` | **NEW** — T5.2, T5.3, T5.6, T5.7 + three edge/scope guards |
| `addons/health_base/tests/__init__.py` | register the new suite |
| `addons/health_web_leads/tests/test_web_leads_w2.py` | **T5.1** — the self-skipping test rewritten as a positive assertion |
| `addons/health_web_leads/tests/test_web_leads_w3.py` | D2 — `test_w3_11` seed-name assertion made case-insensitive (§5.50) |
| `addons/health_web_leads/__manifest__.py` | version `19.0.4.0.0` → `19.0.4.0.1` |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | §5.114–§5.116 merged **in this same commit** (§5.108) |

No model, view, field, controller or ACL was added, removed or edited. No
`.po` change: the phase introduces no user-visible string.

---

## 2. The before/after snapshot — the rollback plan (§5.2.1)

Full psql output: `sh-2-evidence/snapshot-before.txt`,
`sh-2-evidence/snapshot-after.txt`.

| Measure | Before | After |
|---|---|---|
| `res_groups_implied_rel` rows with `gid=1` | **12** | **11** |
| `(gid=1, hid=346)` present | **1** | **0** |
| Recursive closure of `base.group_user` | 13 groups (incl. 346) | 12 groups (**346 absent**) |
| Reverse edges into 346 | 11 (incl. the rogue `1`) | 10 (the declared direction only) |
| ACLs gated on 346 | 18 | **18 (untouched)** |
| Menus gated on 346 | 7 | **7 (untouched)** |
| Record rules gated on 346 | 0 | **0** |
| `access.role` 6 "Doctor" groups | `{1}` | `{1, 350}` |
| `res_users` total | **92** | **92** (nothing deleted) |
| Active internal users | 77 | 70 (the seven archived) |
| Groupless active `ir.rule` on `res.partner` | 1 (id 2) | **1 (id 2)** — §5.113 tripwire clean |

**Rollback is one statement.** The phase removed exactly one row and added
nothing to the group graph:

```sql
INSERT INTO res_groups_implied_rel (gid, hid) VALUES (1, 346);
-- then restart, or env.registry.clear_cache('groups')
```

That restores the previous access state exactly. (Reverting the Doctor role
and the archive is independently optional and equally cheap:
`DELETE FROM access_role_res_groups_rel WHERE access_role_id=6 AND res_groups_id=350;`
and `res.users.browse(...).write({'active': True})`.)

**Scope discipline held.** The other eleven forward edges of `base.group_user`
are untouched, `1 → 7` (`base.group_no_one`) among them — the edge
`health_user_admin/models/res_users_saas.py:23-28` and `access_role_saas.py:32-38`
both reason about. `test_sh2_00c` asserts that specifically.

---

## 3. Per-login verdict for every affected account (§5.6)

Measured by re-running the closure with and without the deleted row —
`sh-2-evidence/snapshot-after.txt` §D. Twenty-four accounts were reachable-346
before; twenty-one of them active, matching the handover's count exactly.

### KEEPS — the ten Doctor-role clinicians (via the §5.2.2 repair)

`dhanoi` · `dhcmc` · `huynh` · `staff_130` · `staff_140` · `staff_154` ·
`staff_155` · `staff_203` · `staff_205` · `staff_207`

All ten: `reached_346_before = t`, `reaches_346_now = t`, each now holding
`health_base.group_healthcare_doctor` (350) **directly**, with 346 arriving
transitively through the XML-declared `350 → 346`.

### LOSES — as designed

| Login | Role | Active | Note |
|---|---|---|---|
| `demo`, `dds_DemoLead`, `dds_DemoAsst` | none | yes | demo accounts — the fix working |
| `svc_web_leads` | none | yes | service account — W2 narrowed it deliberately |
| `nam.lh` | Banker | **archived** | §5.5a; see §7 finding F1 |
| `anh.pd`, `mai.vt`, `tuan.hm`, `ha.dt`, `huong.nt`, `bao.tq` | none | **archived** | §5.5a |
| `__system__` (uid 1) | none | no | superuser; bypasses ACLs regardless — cosmetic |
| `bi_walkthrough` | none | no | already inactive |
| `test` | Owner | no | already inactive; see §7 finding F2 |

The last three were **not** in the handover's list of 21, because the handover
counted active users. They are inactive, so nothing changes for anyone; they
are listed here so the closure arithmetic reconciles (24 = 21 + 3).

---

## 4. Live persona verification

`sh-2-evidence/persona-probe.txt`. Read-only shell probes, no writes.

| Persona | 346 reachable | `health.ews.score` | `health.fso.clinical.notes.wizard` | Menus visible |
|---|---|---|---|---|
| `dhanoi` (Doctor) | **yes** | OK | OK | 5 of 7 |
| `staff_207` (Doctor) | **yes** | OK | OK | 5 of 7 |
| `huynh` (Doctor) | **yes** | — | — | 5 of 7 |
| `demo` | no | **AccessError** | **AccessError** | 0 of 7 |
| `svc_web_leads` | no | **AccessError** | **AccessError** | 0 of 7 |
| `nam.lh` | no | **AccessError** | **AccessError** | 0 of 7 |

The doctors keep the clinical surface; everyone else is denied. Menu
visibility was measured with `ir.ui.menu._visible_menu_ids()`, not `search()` —
see ledger §5.115, which this phase paid for.

**The doctors' "5 of 7" is not a regression — it is an improvement.** A control
probe against three personas SH-2 never touched (a Nurse, an Owner and an
Operations Manager, all holding 346 by other means) shows them seeing **0 of
the same 3 sampled menus**, while the doctor sees the Healthcare root. The two
menus no doctor sees (`health_landing.menu_health_landing_home` 640,
`health_landing.menu_health_viet_uc_root` 641) are invisible to every persona
tested, including the untouched controls. Pre-existing, system-wide, unrelated
to this change — recorded as finding F3.

---

## 5. Tests

**Verbatim result line, final run (PID 2285642):**

```
2026-08-03 08:15:16,540 2285642 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 85 tests when loading database 'vietuat'
```

```
2026-08-03 08:15:16,540 2285642 INFO vietuat odoo.service.server: 85 post-tests in 46.96s, 13009 queries
2026-08-03 08:15:16,540 2285642 INFO vietuat odoo.tests.stats: health_base: 28 tests 2.36s 1125 queries
2026-08-03 08:15:16,540 2285642 INFO vietuat odoo.tests.stats: health_web_leads: 77 tests 15.65s 11542 queries
```

**Executed-method count, not just a failure count (§5.83/§5.90):** 85 methods,
scoped to the run's PID. Suites that ran:

```
2 TestI18nCatalogueLoads.       3 TestI18nCatalogueShape.     5 TestSh1RootPartnerRule.
10 TestSh2GroupImplication.    18 TestWebLeadService.        13 TestWebLeadsConnector.
1 TestWebLeadsConnectorHttp.    6 TestWebLeadsEndpoint.      14 TestWebLeadsW2.
13 TestWebLeadsW3.
```

`TestWebLeadsConnectorHttp` and `TestWebLeadsEndpoint` are `HttpCase` classes
and they executed — the run carried `--workers=0` and no `--no-http` (§5.75).
`EXIT:0`, and `curl localhost:8069/web/login` returned **HTTP 200** after the
final restart.

| Test | Where | Status |
|---|---|---|
| **T5.1** — `base.group_user`-only user raises `AccessError` on `health.ews.score` | `test_web_leads_w2.test_w2_08b_ews_read_is_denied_to_plain_internal_users` | PASS (rewritten from a self-skip) |
| **T5.2** — same negative for `health.fso.clinical.notes.wizard` | `test_sh2_t52_notes_wizard_denied_to_plain_internal_user` | PASS |
| **T5.3** — the ten doctors still reach 346 via the live closure | `test_sh2_t53`, `t53b`, `t53c` | PASS |
| **T5.4** — the `_live_closure` guards stay green | `test_w3_09_catalogue_sidebar_and_acl`, `test_w25_09_acl_matrix` | PASS |
| **T5.5** — the full web-leads suites pass without group 346 | 77 tests across 5 classes | PASS |
| **T5.6** — the seven no longer reach 346 | `test_sh2_t56_the_seven_no_longer_reach_346` | PASS |
| **T5.7** — archived, partners active, no row deleted | `test_sh2_t57_the_seven_are_archived_and_their_partners_are_not` | PASS |

Three extra guards beyond the spec, all cheap and all standing regression
tripwires: `test_sh2_00` (the row is gone), `test_sh2_00b` (the declared
`346 → 1` direction survives — proof the deletion took the right row), and
`test_sh2_00c` (scope discipline: `1 → 7` is still there).

**T5.5 needed no compromise.** `svc_web_leads` lost group 346 and every
web-leads suite still passes; its `implied_ids eval="[(5, 0, 0)]"` narrowing
was never the thing keeping it working. No healthcare group was granted to any
service user.

---

## 6. Deviations

**D1 — all three steps ship in one migration, not just the edge deletion.**
§5.2.4 mandates a migration only for the row deletion; §5.2.2 requires the
role repair to be "reproducible" and §5.5a does not say where the archive
lives. Putting all three in `post-migrate.py` makes the whole access change
one replayable, reviewable, idempotent unit that converges any database,
instead of a migration plus two shell pokes that §5.34 warns can silently
discard writes. Each step no-ops when already applied or when the target is
absent, and Odoo runs migration scripts exactly once (at the 1.3.7 → 1.3.8
boundary), so a later `-u health_base` cannot re-archive an account somebody
deliberately un-archived. Verified: the second deploy did **not** re-run it
(`grep -c "SH-2: starting"` = 1 across both runs).

*Consideration worth the reviewer's eye:* the seven logins are
vietuat-specific data, and they now sit in a module that ships elsewhere. They
are keyed on `login` and skipped when absent, so the script is inert on any
other database — but it is deployment-specific content in a generic module,
and a reviewer may prefer it moved out. Flagging rather than deciding.

**D2 — one unrelated pre-existing test failure fixed:
`test_w3_11_utm_seeds_are_matched_not_duplicated`.** The first run came back
`1 failed, 0 error(s) of 85`. The failure was
`AssertionError: 'TikTok' != 'tiktok'` on `utm.source` — nothing SH-2 touches.

Proof it is not SH-2's: the row (`utm_source` id 201) was last written
**2026-08-03 03:24:19 by uid 1**, four hours and forty minutes before this
phase's first deploy (08:05); SH-2 writes only `access_role_res_groups_rel`,
`res_groups_implied_rel` and `res_users.active`. The test asserts the literal
seeded spelling on the line *above* the line where it asserts the record is
`noupdate` — and `data/utm_seeds.xml`'s own header says *"noupdate='1': once
these rows exist, marketing owns their names."* The test contradicted its own
module's stated contract; it is ledger §5.50 exactly. Fixed in the **test**
(case-insensitive comparison, which is also what the production matcher
`_utm_ids` does — it searches `=ilike`), never in the seed or the engine. The
assertion still catches the real hazard it exists for: an xmlid bound to the
wrong channel row.

**D3 — `health_web_leads` was edited beyond T5.1.** §5.4 sanctions the T5.1
rewrite in that module; D2 is a second test in the same module, needed for the
green run the DoD requires. Both are test-only.

No other deviation. No architecture, model, field or interface was changed.

---

## 7. Findings — reported, NOT fixed

**F1 — `nam.lh` carries session evidence that contradicts "unused", as the
handover warned.** Confirmed live: **30 `res_device_log` rows**, first
2026-02-27 07:03:14, most recent **2026-06-12 02:46:17**. The other six have
**zero device-log rows ever**. New this phase, not in the handover: `nam.lh`
also created **14 `mail_message` rows** (the other six created none), so the
"no work product" finding is true for `crm.lead`, `res.partner` and
field-service orders but **not** absolutely — there is chatter authored by
this account. The user was told about the sessions and confirmed the archive
anyway, so it was archived as instructed. **Un-archiving is a single write
(`active = True`), so a mistake here is trivially reversible**, and the user
row and its messages are intact — nothing was deleted.

**F2 — three accounts beyond the handover's 21 also lost 346, all inactive.**
`__system__` (uid 1, the superuser — bypasses ACLs anyway, so this is
cosmetic), `bi_walkthrough`, and `test` (which carries the **Owner** role yet
did not hold 346 directly — its role grants 346, so its `access.role` → user
group sync is stale). Nobody is affected while they stay inactive, but `test`
being an Owner-role account whose groups do not match its role is worth a look
before anyone reactivates it.

**F3 — two healthcare menus are invisible to every persona tested, including
ones this phase never touched.** `health_landing.menu_health_landing_home`
(640) and `health_landing.menu_health_viet_uc_root` (641) are gated on
`{346, 347, 348, 350, 354, 355, 356}` and carry `ir.actions.client` actions,
yet `_visible_menu_ids()` excludes them for doctors, nurses, owners and
operations managers alike. Pre-existing and unrelated to SH-2 (the control
personas' group membership did not change). Most likely the §5.69 family — the
users who matter live in the `/bizapp` CMS shell where the sidebar, not
`ir.ui.menu`, is the surface. Needs its own look; not this phase's to make.

**F4 — the role repair does not merely preserve the ten doctors' access, it
widens it, and that is what §5.2.2 asked for.** Before, they had group 346's
**18** ACLs. Now they additionally hold group 350's **38** ACLs — care plans,
medication orders/administration, observations, conditions, consents,
incidents, `res.partner` patient write/create, and clinical notes. Twenty-eight
active record rules bound to 350 narrow almost all of it to the user's own
catchment province. This is the access a doctor was always meant to have and
what the broken role should have granted from the start — but it *is* a
widening for ten live accounts and the reviewer should see it named.

**F5 — `health.clinical.note` has zero record rules, so those ten doctors now
have unnarrowed read/write/create on every clinical note in the system.** ACL
7027 (`health.clinical.note.doctor`, `1,1,1,0`) is SH-1's own §3.2 addition,
and SH-1 §3.0 documented that the model carries no `ir.rule` at all — verified
still true today (0 rows). The composition of SH-1's ACL and SH-2's role
repair is therefore the first time anyone holds doctor-level clinical-note
access on this database, and it is not catchment-narrowed the way every other
clinical model on group 350 is. Both halves were explicitly sanctioned by
their phases; adding a record rule to `health.clinical.note` is a wider
decision than SH-2 makes. **Recommended as the next security ticket.**

**F6 — `access.role` id 6's `granted_group_ids` sync snapshot was empty before
this phase and is now `{1, 350}`.** `_update_users_groups` reconciles removals
against that snapshot, so previously removing a group from the Doctor role
would have left it on all ten users; now it will be unlinked properly. A
repair, not a regression — but it means the role's behaviour on future edits
changed, which is worth knowing.

---

## 8. New gotchas — MERGED into `HANDOVER-CONVENTIONS.md` in this commit

Per §5.108, whose whole point is that a gotcha living only in a phase report
does not exist for the next phase. All three are already in §5 of the
conventions doc as of this commit.

- **§5.114** — Odoo 19 computes a user's group closure at READ time
  (`res.users.all_group_ids` is a non-stored compute over
  `group_ids.all_implied_ids`), so granting a group never expands its closure
  into `res_groups_users_rel`, and an implication edit takes effect
  immediately. Remove an implication with
  `res.groups.write({'implied_ids': [Command.unlink(id)]})`, never a raw
  `DELETE` — the ORM path clears the `groups` registry cache and
  `ir.model.access`'s cache-clearing methods; a `DELETE` leaves both serving
  the old graph until a restart. **This is why the ten doctors survive the
  deletion, and why none of them picked up `base.group_no_one` as a direct
  group** — measured: `has_direct_group_no_one = f` for all ten.
- **§5.115** — `ir.ui.menu.search()` does not answer "can this persona see
  this menu"; `_visible_menu_ids()` does. Measured here: `search()` returned
  the identical 5 menus for a doctor holding the gating group and for three
  personas that had just lost it, while `_visible_menu_ids()` returned 5 and
  **0**. Also: it discards `base.group_no_one` outside debug mode, and a
  parent menu with no action is visible only through a visible child.
- **§5.116** — a `noupdate="1"` seed belongs to the business the moment it
  exists, so a test may assert its stable identity but never its display text
  (the §5.50 family, with the noupdate twist that makes it inevitable rather
  than merely likely).

**§5.113 re-confirmed live.** `-u health_base` cascades to
`health_fieldservice`, whose `cleanup_rules.xml` delete/recreates ten record
rules on every upgrade: the FSO rule ids moved again (SH-1 recorded
4746–4754; they now read 4773–4781), with no change in count, name, domain or
group binding. Compare security snapshots **by name**, never by id. The
tripwire the entry asks for is clean: `res.partner` still has exactly one
groupless active rule, id 2, and every FSO rule still carries ≥1 group.

---

## 9. Deploy record

Conventions §2, with the §5.111 pre-flight drain (`pgrep` to zero **and**
zero `idle in transaction` sessions on vietuat) — both clean on both runs, so
none of SH-1's lock-timeout pain recurred.

```
-u health_base,health_web_leads --test-enable
--test-tags /health_base,/health_web_leads
--stop-after-init --workers=0 --http-port=8079 --max-cron-threads=0
```

Migration log, first deploy (the only run that executed it):

```
SH-2: starting T-001 group-implication repair
SH-2: granted health_base.group_healthcare_doctor (id 350) to access.role 'Doctor' (id 6);
      10 linked user(s) reconciled: dhanoi, dhcmc, huynh, staff_130, staff_140,
      staff_154, staff_155, staff_203, staff_205, staff_207
SH-2: deleted res_groups_implied_rel (gid=1, hid=346);
      base.group_user closure 13 -> 12 groups, removed: [346]
SH-2: archived res.users 'nam.lh' (id 21); res.partner 'Le Hoang Nam' (id 145) left active=True
      … (six more, all with their partner left active=True) …
SH-2: T-001 repair complete
```

**Nothing deferred.** Every numbered item in §5 (5.2.1 – 5.2.5, T5.1 – T5.7,
5.5, 5.5a) landed.

No browser evidence pack: no user-facing code changed, and §7 of the handover
requires one only for SH-1 §6. The equivalent live proof for an access-only
change is §4's persona probe, which is server-side and reproducible.
