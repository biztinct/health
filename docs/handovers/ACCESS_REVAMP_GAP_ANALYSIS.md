# ACCESS REVAMP — gap analysis: Payobook "Access & delegation" vs Carejiox "Access & roles"

Status: ANALYSIS (2026-09-28). Owner asked for a revamp of Carejiox's Access home to
reach parity with (and where sensible exceed) Payobook's. Phased Fable-designs /
Opus-builds cycle confirmed by the owner for this stream (do not re-ask).

Read with `docs/strategy/HANDOVER-CONVENTIONS.md` (ledger continues at **§5.209**) and
`docs/handovers/SAAS_PORT_PROGRAM.md` (H-ledger continues at **H112**).

Sources (both read end to end on 2026-09-28, nothing modified):

- Payobook: `/Users/adity/Documents/GitHub/gitlocal/biz_access` (manifest 19.0.1.4.4),
  `pb_vendor_access` (19.0.1.9.1, the Payobook overlay), `biz_approval_workflow` (engine),
  design docs `gitlocal/docs/handovers/ACCESS_PROGRAM.md` + `ACCESS_CLOSEOUT.md` + P1–P9.
- Carejiox: `addons/biz_access` (19.0.1.2.0) + `addons/health_access` (19.0.1.2.1) +
  `biz_tenancy`/`biz_tenants`/`health_tenancy` (support access).
- Live `carejiox` DB (read-only SQL, 2026-09-28): 9 roles (8 active; Banker archived),
  30 abilities, 74 active internal users (all `en_US`; `vi_VN` active but unused),
  4 hand-overs `active`, 96 of 114 active `cms.sidebar.item` rows role-gated, 1 section
  gated, `topbar_mode=admin_only`, **0 `ir_mail_server`**, no approval/audit module installed.

## 1. History: why the two trees diverged

Payobook's ACCESS programme P1–P6 closed 2026-09-02. Carejiox ported that state on
2026-09-04 (SaaS H1/H2a/H2b) and *renamed* everything (`pb.access` → `biz.access.*`,
`.pbva-` → `.bza-`, `--pbim-` → `--bzk-`), so a line diff is meaningless; the comparison
below is feature-level. Payobook then kept building (2026-09-06 → 2026-09-28):
approvals (`pb_access_request`/`pb_access_approval`), guided invitations, multi-role
grant + copy-from-person, removal that names blocking roles, sub-screen expansion on the
passport, recovery-account hiding, gap roles for role-less screens, Vietnamese catalogue.
None of that reached Carejiox.

Carejiox, meanwhile, built things Payobook lacks (keep them): the person-action slots
(switch off/on, password reset, change job, staff record), the clinic new-person wizard,
the `job_role_id` field + `clinical_kind`, section-level rail gating with inheritance,
the `admin_only` top-bar mode, before/after diff tooling, support-access sessions.

## 2. Side-by-side (P = Payobook, C = Carejiox)

Legend: ✅ has it · ⚠ partial / defective · ❌ missing

| # | Capability | P | C | Notes / Carejiox seam |
|---|---|---|---|---|
| 1 | Four lenses Roles/People/Screens/Hand-overs | ✅ | ✅ | `LENS_REGISTRY` JS:86 |
| 2 | "See it as…" simulator, never an argument to a write | ✅ | ✅ | `as_user` F:1579 |
| 3 | Who-holds-what / History xlsx exports | ✅ | ✅ | untested on both; C History shows a clinic admin only their own rows (see §3.1) |
| 4 | Take back what has ended (manual + nightly cron) | ✅ | ✅ | `run_auto_revert` F:519; untested on C |
| 5 | Role builder w/ live mini-rail + "differs from role X" | ✅ | ✅ | `preview_rail` F:953, `get comparison` JS:1399 |
| 6 | Copy role (start from existing) | ✅ | ✅ | `prefillFrom` JS:1359 |
| 7 | Archive role that explains itself | ✅ | ✅ | `archive_role` F:1108 |
| 8 | Grant/remove single role, audit row | ✅ | ✅ | `grant` F:263 / `remove` F:309 |
| 9 | **Give several roles at once** (`grant_many`) | ✅ | ❌ | P: `F.grant_many` :294, one audit row, cap 100 |
| 10 | **Copy roles from another person** (`copy_roles`, excludes lent) | ✅ | ❌ | P: `F.copy_roles` :340 |
| 11 | Removal names the blocking roles | ✅ | ✅ | C names the covering role F:384 |
| 12 | **Guided "Add a person" + invitation e-mail, user kept if mail fails** | ✅ | ⚠ | C has a richer clinic wizard (`HA/wizard/new_person.py`) but NO invite mail; password reset refuses w/o `ir.mail_server` (HA facade :240) |
| 13 | Passport: menu as they see it | ✅ | ✅ | `_rail_as_seen_by` F:1330 |
| 14 | **Passport expands entries into sub-screens** ("x of y") | ✅ | ❌ | P: `surface_access` F:1511 + `PbMiniRail expandable`; C: children exist as `parent_id` rows and are gated in Screens lens, but the passport mini-rail does not expand them |
| 15 | Person actions (switch off/on, reset, change job, staff record) | ❌ | ✅ | C-only, keep (`HA/models/access_facade.py:139-188`) |
| 16 | Hand my access over (everyone), lend-only-what-you-hold | ✅ | ✅ | `delegate` F:454 — facade untested on C |
| 17 | Lend on somebody's behalf (manager) | ⚠ server only | ⚠ server only | neither has UI; C hard-codes `group_access_manager` at `access_delegation.py:459` instead of `MANAGE_GROUPS` |
| 18 | Hand-over default window from setting | ⚠ | ⚠ | both hard-code 14 days in JS; `default_end_days()` dead on C |
| 19 | Hand-overs lens search/filter/state chips | ❌ | ❌ | neither; cap 500 rows |
| 20 | **Request & approval for grant / removal / hand-over** | ✅ | ❌ | P: `pb.access.request` + `biz_approval_workflow` engine (~21k lines, 20 models). C manifest explicitly declares "no approval chain" (`BA/__manifest__.py:84-86`) |
| 21 | "Ask for access" by an ordinary staff member | ❌ | ❌ | not in either; Payobook only routes a *manager's* action through approval |
| 22 | Screens lens: role gates, on/off, reorder, who-sees-and-why | ✅ | ✅ | `screens_board` F:1788 |
| 23 | Screens lens: teaser ("show it locked with a note") | ✅ | ⚠ dead | C draws the chips (QW:1054-1084) but provider raises on `set_restricted` (`cms_sidebar.py:351`) |
| 24 | Section (block) gates editable in the lens | ❌ (debt D5) | ❌ | C has the model (`cms.sidebar.section.biz_role_ids`) but `screens_board` drops sections (F:1830-1838), no facade write; probable misreport of "everyone with a login" on entries gated via section/parent (F:1701/:1768) |
| 25 | Gates inherited from section / parent | ❌ | ✅ | C-only (`effective_biz_role_ids` :84-121) |
| 26 | Top bar: admin-only / role-hidden | ✅ (launcher rule) | ✅ (`admin_only`) | parity, different mechanism |
| 27 | Developer mode blocked server-side | ✅ | ✅ | `BA/models/ir_http.py` |
| 28 | Forbidden-group rail over implied closure (Rail B) | ✅ | ✅ | `TestRailB` on both |
| 29 | Tenant administrator = a role, not the keys | ✅ | ✅ | `group_clinic_admin` + Owner/Admin roles; `biz_tenants` grants at provisioning |
| 30 | **Clinic/tenant admin sees/edits everything a manager should** | ✅ (lifecycle-admin rule) | ⚠ **bug** | C registers `group_clinic_admin` in `MANAGE_GROUPS` but NOT in the access-team ACL/record rules → see §3.1 |
| 31 | Self-grant policy | deliberate (admins may) + test | silent | C: no server check, no test, a clinic Admin can give themselves Owner |
| 32 | Recovery account hidden from People | ✅ | ❌ | P `visible_people` access_common.py:184; C shows `platform.recovery@carejiox.com` in the People list (verify live) |
| 33 | Roles for screens that shipped with groups and no role | ✅ (P 1.9.0) | ⚠ | C: 9 phone/Zalo + 3 reporting-config screens OFF the menu because no role holds their groups (SAAS ledger H2b, §5.208) |
| 34 | "people hold one" counter | ⚠ | ⚠ | both count over holder lists capped at 40 — Nurse has 44 |
| 35 | Re-seed catalogue button | ❌ (system only) | ❌ | C: `reseed_catalogue` F:546 has no button yet `biz_tenants/service.py:2059` tells the operator to "press Re-read" |
| 36 | Learn / coach anchors on the Access screen | ✅ (8 anchors) | ❌ | C has `health_learn` but no anchors on Access |
| 37 | **Vietnamese catalogue** (UI strings + role/ability names) | ✅ 448 strings + `catalogue_vi.py` | ❌ | C: no `i18n/` in biz_access/health_access/biz_kit/biz_tenancy/health_tenancy — violates conventions §4 |
| 38 | Settings hub entry via registry | ✅ | ⚠ | C tab is hard-coded in `health_landing/.../admin_model_navigator.js:139-141`, not via `health_landing.admin_tabs` |
| 39 | `clinical_kind` editable | n/a | ❌ | C: no UI; `counts_as_line()` dead |
| 40 | Support access (reason + time box + trail + customer refuse switch) | ✅ | ✅ | C-only gap: `biz.support.session.sweep()` has no cron |
| 41 | Field-change audit trail (`biz_audit_trail`) | ✅ (separate module) | ❌ | out of Access scope; owner question |
| 42 | Vendor register (`pb_vendor_access`) | ✅ | n/a | payroll-specific, not relevant to a clinic |
| 43 | Tests on `delegate()`, auto-revert, exports, ended mail | ⚠ partial | ❌ | C gaps listed by the inventory |

## 3. Carejiox defects found during the inventory (fix inside the revamp)

### 3.1 The clinic administrator is half a manager (highest value fix)
`health_access.group_clinic_admin` is registered into `MANAGE_GROUPS` (`HA/hooks.py:413`)
so the board *offers* every manager action, but the ACL (`BA/security/ir.model.access.csv`
lines 4-5) and the record rules (`biz_access_security.xml` :83-:114) only know
`biz_access.group_access_manager` (held by root + admin only). Consequences on live
(the two "Admin"-role users ahanoi/ahcmc, and every Owner without group_system):
- Hand-overs lens + History export show only their own rows (`_delegations` F:196,
  `build_delegations` unsudo'd).
- "Take it back now" on somebody else's hand-over fails `check_access` (F:508).
- "Edit the list of roles" opens a list they cannot write.
- Lending on behalf hard-codes `group_access_manager` (`access_delegation.py:459`).
The security XML (:99-100) says "the application adds its own rule" — health_access never did.
Fix direction: either make `group_clinic_admin` imply `group_access_manager`, or ship the
health_access rules/ACL for it (Payobook's `rule_delegation_lifecycle_admin_all` precedent).

### 3.2 Dead / inert UI
- "Show it locked, with a note" chips (QW:1054-1084) → provider refuses. Either remove or
  build teaser support in `health_cms_sidebar` (`restricted` flag + locked row rendering).
- `hidden_menu_ids` notebook page on the role form is inert under `admin_only`.
- `legacy_note` always `''`; `_also_write_the_older_lane` no-op; new-person docstring stale.

### 3.3 Counters / defaults
- 14-day default hard-coded (JS:1187) — wire `biz_access.default_window_days`.
- "people hold one" undercount past 40 holders (F:242).

### 3.4 Missing tests (C)
facade `delegate()`, `run_auto_revert`/`cron_auto_revert`, both exports, `user_options`,
`reseed_catalogue`, the "ended" mail, self-grant policy.

## 4. What Payobook's approval layer actually is (sizing for the owner decision)

`biz_approval_workflow` = 20 models / ~21k lines incl. `pb_approval_config` (inbox UI),
`biz_approval_chain` (stepper). Access hooks in via `biz.approval.adapter.mixin`
(`pb_access_request.py:65`), routed only when a `biz.approval.binding` for process `roles`
is live; `_ask_instead` (`pb_access_approval.py:45`) turns a manager's grant/remove/
delegate into a request; the last approver applies through the same facade under
`ENGINE_APPLY`; seat users get read via `seat_user_ids` + rule.
**Porting the engine is its own programme.** For Carejiox Access the economical option is a
*built-in* request model inside `biz_access` (kind, roles, target, reason, state
pending/applied/returned/rejected; approver = a configurable role, default Owner) with the
same "ask instead of do" seam on `grant`/`grant_many`/`remove`/`delegate`, an in-app
Approvals card on the Access home, and the seat-read rule. Shape it so a future generic
engine can take over the routing (same request fields, same apply seam).

## 5. Candidate phase map (to be confirmed by owner answers)

- **AR-1 Repair + parity core**: §3.1 clinic-admin rules/ACL, `grant_many`, `copy_roles`,
  removal wording, recovery account hidden, counters/defaults, dead-control decision,
  tests for the untested seams. (biz_access + health_access)
- **AR-2 People**: invitation flow (mail-aware, honest when dark), multi-role/copy in the
  passport, sub-screen expansion of the passport mini-rail (`parent_id` children, "x of y"),
  Hand-overs lens search/filter/chips, lend-on-behalf UI, `clinical_kind` editor.
- **AR-3 Requests & approvals** (if chosen): built-in request model + "Ask for access"
  for everyone + Approvals card + seat-read rule + the ask-instead seam.
- **AR-4 Screens**: section gates in the lens, teaser support or removal, gap roles for
  the 12 role-less screens, re-seed button, Settings hub entry via registry.
- **AR-5 Vietnamese + coach**: `i18n/vi.po` for biz_access + health_access (seed from
  Payobook's 448-string catalogue where labels match), role/ability catalogue in Vietnamese,
  health_learn anchors + a short Access journey.
- Deploy each phase: clone rehearsal → `carejiox` master → `carejiox_template` → `hhh`
  via the rollout screen (SaaS ledger H4b/H4c rails; `-t` stops the service — use
  `systemd-run` per HANDOVER-CONVENTIONS §2).

## 6. Binding rules for every handover in this stream

- White-label: never "Odoo" in a user-visible string. Plain-English UI copy in the screen's
  vocabulary. `--bzk-*` tokens (bridged to `--vu-*` in `health_theme/bzk_brand.scss`),
  flat colours, `ic()` inline SVG inside biz_access (the `hf-wt-ico` rule is for health_*
  modules; `cms.sidebar.item.icon` stays font-awesome).
- Generic/overlay split stays: product vocabulary (roles, areas, clinic actions, Vietnamese
  catalogue text) lives in `health_access`; mechanics in `biz_access`. Payobook adopts
  `biz_access` changes later — keep `biz_access` free of health words (test
  `TestNoProductNameInTheGenericLayer` precedent from Payobook is worth cloning).
- Never `-t` on the live box; `--db-filter=^<clone>$` on every manual run; `noupdate=1`
  data needs a migration on upgrade (§ A2 precedent); `post_init_hook` does not fire on `-u`.
