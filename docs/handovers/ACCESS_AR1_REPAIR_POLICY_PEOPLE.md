# ACCESS REVAMP — AR-1: repair, policy and the People lens

Status: HANDOVER to Opus (2026-09-28). Designed by Fable. Read first:
`docs/handovers/ACCESS_REVAMP_GAP_ANALYSIS.md` (the comparison and the owner answers),
`docs/strategy/HANDOVER-CONVENTIONS.md` (§2 test/deploy rails, §4 module rules; **ledger
continues at §5.209** — append every gotcha you hit), and
`docs/handovers/SAAS_PORT_PROGRAM.md` H-ledger (H77, H78, H85, H102 are the traps that
bit the last programme on this box).

Owner decisions that bind this phase (2026-09-28): **no approvals**, **nothing that needs
e-mail** (no invitation flow; the two hand-over mails stay exactly as they are), **only a
holder of Owner may give or lend Owner**, **nobody may give a role to themselves**,
**managers may start a hand-over on somebody's behalf**, **14-day default becomes a
setting**, Payobook's `grant_many` / `copy_roles` / Hand-overs search+filters come across.
Everything else (Screens lens, sub-screen expansion, Vietnamese, coach) is AR-2/AR-3 —
NOT this phase.

## 0. Standing rules (state them back in your report)

- White-label: the word "Odoo" never appears in a user-visible string. Plain-English copy in
  the screen's vocabulary ("role", "hand-over", "the left menu", "Owner"). No permission-group
  names on screen, ever.
- `biz_access` stays product-agnostic: no clinic words, no `health_*` imports. Product
  vocabulary and policy *values* (which role is guarded) live in `health_access`. Clone
  Payobook's `TestNoProductNameInTheGenericLayer` idea (gitlocal `biz_access/tests/
  test_access_generic.py:204`) as a Carejiox test if one does not exist yet.
- Styling: `--bzk-*` tokens only, flat colours, `ic()` inline SVG from biz_kit. Follow the
  existing `.bza-*` classes in `addons/biz_access/static/src/scss/access.scss`.
- Tests: `--db-filter=^<clone>$` on every manual run; **never `carejiox-deploy -t` on the live
  box** (H77 — it stops the service for the whole run); run suites through `systemd-run` on a
  spare port per HANDOVER-CONVENTIONS §2. Rehearse on a clone whose `biz.tenant` rows are
  neutralised first (H102).
- `post_init_hook` does not fire on `-u`; any seed/policy change ships a migration.
- Version bumps: `biz_access` 19.0.1.2.0 → **19.0.1.3.0**, `health_access` 19.0.1.2.1 →
  **19.0.1.3.0**, each with `migrations/<version>/post-migrate.py` where §3 says so.

## 1. Scope

| # | Item | Module |
|---|---|---|
| A | Clinic administrator becomes a full Access manager (ACL/rules) | health_access |
| B | Guarded role ("only holders may give or lend it") + Owner is guarded | biz_access + health_access |
| C | No self-grant | biz_access |
| D | Give several roles at once (`grant_many`) | biz_access |
| E | Copy roles from another person (`copy_roles`) | biz_access |
| F | Hand-over on behalf (UI + manage-group fix) | biz_access |
| G | Default hand-over window from the setting | biz_access |
| H | Hand-overs lens: search + state chips | biz_access |
| I | "people hold one" counter counts everybody | biz_access |
| J | Platform recovery account hidden from People / pickers | biz_access (+ biz_tenancy if the login lives there) |
| K | Tests for the untested seams (`delegate()`, auto-revert, both exports, `user_options`) | biz_access |
| L | Dead-code sweep listed in §3.L | health_access |

Binding non-goals: Screens lens changes, passport sub-screen expansion, teaser switch
removal, dark-screen abilities, re-seed button, Vietnamese, coach anchors, approvals,
invitation mail, audit-trail module. Do not touch `health_cms_sidebar`.

## 2. Verified plumbing (2026-09-28 — do not re-derive)

Paths: `BA/` = `addons/biz_access/`, `HA/` = `addons/health_access/`,
`F` = `BA/models/access_facade.py`, `JS` = `BA/static/src/js/access_board.js`,
`QW` = `BA/static/src/xml/access_board.xml`, `DL` = `BA/models/access_delegation.py`,
`AC` = `BA/models/access_common.py`. Payobook precedents: `PB/` =
`/Users/adity/Documents/GitHub/gitlocal/biz_access/` (`PBF` = `PB/models/pb_access_facade.py`,
`PBJS` = `PB/static/src/js/access_board.js`, `PBX` = `PB/static/src/xml/access_board.xml`).

- Manage gate: `can_manage` F:99 = `base.group_system` OR any of `MANAGE_GROUPS` AC:105
  (`biz_access.group_access_manager` + `health_access.group_clinic_admin`, registered at
  `HA/hooks.py:413`). Browser mirror `ACCESS_MANAGE_GATE` `BA/static/src/js/access_palette.js:54-69`
  extended by `HA/static/src/js/health_access_palette.js`.
- **The gap A bug**: ACL `BA/security/ir.model.access.csv` lines 4-5 and rules
  `BA/security/biz_access_security.xml` :83-:114 only name `biz_access.group_access_manager`
  (seeded to root + admin, `:38-48`). `HA/security/health_access_security.xml:19-29` defines
  `group_clinic_admin` implying `health_base.group_healthcare_admin` only. Symptoms:
  `_delegations` F:196 and `build_delegations` (`BA/models/access_export.py:124`) run unsudo'd
  under `rule_delegation_mine`; `revoke` F:508 `check_access` fails; role list read-only.
  `DL._assert_can_delegate` :452-:459 hard-codes `group_access_manager` instead of `MANAGE_GROUPS`.
- Grant path: `grant` F:263 (adds only missing groups, audit `origin='board'`), `remove` F:309,
  `_internal_user` F:442 (no self check), `_safe_profile` F:419 (forbidden closure).
  `user_options` F:1601 excludes self (the ONLY thing stopping self-grant today).
  Grant modal QW ~1118-1244 area (search "Give a role"); `openGrant` JS:1085, `confirmGrant`
  JS:1120, `openGiveRole` JS:527, `pickRoleToGive` JS:537, `openRemove` JS:1092.
- Passport: `passport` F:1438, `_roles_of` F:1385, people list `people` F:1280
  (`PEOPLE_CAP=200`), `_person` F:1219 (non-managers see self only).
- Delegation: `delegate` F:454 → `DL.action_activate` :~183 / `_activate_one` :176;
  `_groups_to_hand` DL:220; `_check_two_people` DL:141; `revoke` F:501 → `action_revoke`
  DL:268; `run_auto_revert` DL:366 + cron `BA/data/ir_cron.xml:17-25`; mails DL:312-342
  switched by `biz_access.delegation_mail` (AC:173) — leave the mails untouched.
  `default_end_days()` DL:468 reads `biz_access.default_window_days` (AC DEFAULTS ~:173-196)
  and is dead: JS:1187 hard-codes 14. Dialog QW:1433-1530, `openDelegate` JS:1185,
  `confirmDelegate` JS:1232. Hand-overs lens QW:1103-1167, rows from `_delegations` F:189
  (origin=`delegation` only, cap 500), `daysLine` JS:360.
- KPIs: `_kpis` F:234, `people` F:242 counts over holder lists capped at `HOLDER_CAP=40`
  (AC:160). Live Nurse role has 44 holders.
- Role model `BA/models/access_role.py`: `name` :61, `ability_ids` :65, `group_ids` stored
  compute :70/:151, `area` :86, `visible_group_id` :92, `holder_count` :134/:158-198,
  constraints :230-271. Seeded role xmlids `HA/hooks.py:329-339` (`health_access.role_owner`
  … `role_crm`), notes `ROLE_NOTES` :271-326, fresh abilities :345-373, live carry :487.
  `HA/hooks.py:1376` post_init runs catalogue + migrate + retire + gates + topbar settings.
- Provisioning grants the tenant-admin role through the facade at
  `addons/biz_tenants/models/service.py:849-851` — check under WHICH user that env runs before
  adding the self-grant refusal (if actor == target there, exempt via the explicit context key
  in §3.C, never by weakening the rule).
- Recovery account: login `platform.recovery@carejiox.com` (SAaS H3/H4; grep
  `platform.recovery` in `addons/biz_tenancy` / `addons/biz_tenants` for the constant).
  Payobook precedent: `PB/models/access_common.py:167-190` (`visible_people` :184) +
  `PBF._internal_user` :509 + test `PB/tests/test_access_p3.py:368`.
- Payobook precedents to clone (rename `pb.`→`biz.access.`, `.pbva-`→`.bza-`):
  `PBF.grant_many` :294 (cap 100, one write, one audit row), `PBF.copy_roles` :340
  (permanent visible roles only, never lent, then `grant_many`), `PBF._roles_covering` :443
  + messages :392-421; passport multi-select `PBJS.givableRoles` :732, `toggleRoleToGive`
  :667, `showCopyRoles` :680, `onCopyPersonSearch` :694, `pickCopyPerson` :710; dialog
  `PBX:1118-1244`; tests `PB/tests/test_access_p3.py:614` (`test_many_roles_are_given_together`),
  `:635` (`test_copying_roles_excludes_temporary_handovers`), `PB/tests/test_grant_to_self.py`
  (the *opposite* policy — clone the shape, invert the assertions).
- Existing Carejiox tests to keep green: `BA/tests/` (generic, p2, p3, p4, top_bar, no_rail,
  rail_state, debug_block, person_actions) and `HA/tests/` (catalogue, provider, rail_gate,
  rings, job_field, new_person, retirement, topbar_*). `biz_tenants` + `health_tenancy`
  suites touch the facade too — run them.

## 3. Design

### A. Clinic administrator = full Access manager
One line + a migration: `health_access.group_clinic_admin` gains
`implied_ids += biz_access.group_access_manager` in `HA/security/health_access_security.xml`.
Ship `HA/migrations/19.0.1.3.0/post-migrate.py` that re-asserts the implication (the XML is
loaded on `-u`, but assert it anyway and log the count of users who gained the group).
Then replace the hard-coded group in `DL._assert_can_delegate` with the `MANAGE_GROUPS`
check that `can_manage` uses (expose a helper `AC.user_can_manage(user)` if none exists).
Rail: `group_access_manager` must stay outside the forbidden closure — `TestRailB` proves it.

### B. Guarded role (generic) + Owner guarded (product)
- `biz.access.role.guarded` Boolean, label **"Only people who hold this role may give it or
  lend it"**, help sentence in the same words. Shown on the role form and as a small
  "Guarded" chip on the role card (next to "Restricted").
- Enforced in `grant`, `grant_many`, `copy_roles`, `delegate` (for the *actor*, i.e.
  `self.env.user`): if any role is guarded and the actor does not fully hold it →
  `UserError` "Only somebody who holds Owner can give it." (name the role). `base.group_system`
  is exempt (the platform administrator). Copy-from-person silently *drops* guarded roles the
  actor cannot give and says so in the success message ("Owner was left out — only an Owner
  can give it.").
- `health_access` sets `guarded=True` on `role_owner` in the seed (fresh path) **and** in the
  19.0.1.3.0 migration (live path). Create-only afterwards: an upgrade never flips it back.

### C. No self-grant
In `grant` / `grant_many` / `copy_roles`: if `target == self.env.user` and not superuser →
`UserError` "You cannot give a role to yourself. Ask another Owner or Admin." Keep the
existing picker exclusion. Add context key `biz_access_system_apply` that ONLY provisioning /
hooks may pass (document it in the model docstring); the facade refuses it unless
`self.env.su` or `base.group_system`. Delegation self-check stays as it is (`_check_two_people`).

### D. `grant_many(profile_ids, user_id, reason)`
Clone `PBF.grant_many`: manage gate, `_internal_user`, B + C checks, skip roles already
fully held (refuse only when *nothing* would change), one `group_ids` write, ONE audit
row with all roles, message "Gave Lan 3 roles: …". Passport "Give a role" becomes a
multi-select (tick list of `givable` roles = visible, active, not held, not guarded-unless-
holder). Single-role path from a role card keeps calling `grant`.

### E. `copy_roles(source_user_id, target_user_id, reason)`
Clone `PBF.copy_roles`: source's *permanent* (not lent) visible roles minus what target
already holds minus guarded-the-actor-cannot-give → `grant_many`. Passport gains
"Copy from another person" with a person search (reuse `user_options(term, include_me=…)`
shape — check C's `user_options` signature F:1601 and add `include_me` if absent) and a
preview list before the button. Refuse with a sentence when nothing would be copied.

### F. Hand-over on behalf
Dialog gains, **for managers only**, a "Handing over for" row defaulting to "me" with a
person search; picking someone else changes the offered roles to *that* person's held roles
(new read `held_roles_of(user_id)` — or reuse `_roles_of` — manage-gated). Server:
`delegate(vals)` already accepts `delegator_user_id`; keep lend-only-what-**they**-hold
(`_groups_to_hand` checks the delegator) and add: the actor must be able to manage (A) and
must hold any guarded role being lent (B). Record who started it: the delegation card and
the history export show "Started by <actor>" when `create_uid != delegator_user_id`
(add a computed `started_by_note`, no new stored field needed beyond `create_uid`).

### G. Default window from the setting
`get_board` (or `composer_options`) returns `default_window_days` from `DL.default_end_days()`;
`openDelegate` uses it. Expose the parameter on the role-list backend view as a small
settings block only if a Settings seam already exists in biz_access — otherwise leave it a
parameter and note it.

### H. Hand-overs lens search + chips
`_delegations(state=None, search=None)`: chips **Running / Ended / Taken back / All**
(default Running), search by either person's name (accent-folded via `AC.fold`), cap stays
500 *after* filtering, headline says "N running, M ended". Same visual language as the
Roles chips (`QW:228-234`).

### I. Counter
`_kpis.people` = distinct active internal users who fully hold at least one visible role,
computed over `holder_count`'s underlying query (not the capped lists). Keep the 40-cap
for the face rows.

### J. Recovery account hidden
Port `visible_people` + the `_internal_user` refusal: the recovery login never appears in
People, pickers, "See it as", copy-from search, or the exports, and cannot be a grant/
delegation target except by itself. The login value must come from biz_tenancy's constant
or a parameter — `biz_access` must not hard-code `carejiox`. If biz_tenancy has no exported
constant, add `biz_access.hidden_logins` parameter read in AC and set it from
`health_tenancy`/`biz_tenancy` hooks.

### K. Tests (numbered — run all, report each)
1. Clinic admin (holding ONLY `group_clinic_admin` via the Admin role) sees every hand-over
   in the lens, can revoke another person's hand-over, can write a role, and History export
   returns all rows.
2. `TestRailB` still green after A (access team not in the forbidden closure).
3. Guarded role: a manager who does not hold Owner cannot grant, grant_many, copy or lend
   Owner; an Owner can; the message names the role; `base.group_system` exempt.
4. Self-grant refused for grant / grant_many / copy (target == actor) with the sentence;
   provisioning's tenant-admin grant still passes (biz_tenants suite green).
5. `grant_many`: three roles → one write, one audit row, already-held ones skipped, all-held
   refused; cap 100.
6. `copy_roles`: lent roles never copied; guarded role dropped with the note; nothing-to-copy
   refused.
7. Hand-over on behalf: manager starts one for an absent nurse; only the nurse's held roles
   are lendable; card shows "Started by"; a non-manager cannot pass `delegator_user_id`.
8. `default_end_days` reaches the browser: `biz_access.default_window_days=7` → board
   reports 7.
9. Hand-overs lens: state chips filter; name search matches lender or borrower; default
   view is Running.
10. Counter: 45 holders on one role → `people` == 45.
11. Recovery login absent from `people`, `user_options`, `as_user` options and both exports;
    `grant` to it refused.
12. Previously untested seams: `delegate()` end-to-end (groups added, audit row, state
    active), `run_auto_revert` ends an expired one and leaves a running one, `build_roles` and
    `build_delegations` return a workbook with the expected headers, `user_options` excludes
    self and portal users.
13. Whole `biz_access` + `health_access` + `biz_tenants` + `health_tenancy` suites green on
    the clone (report counts before/after).

### L. Dead-code sweep (health_access)
Remove `_also_write_the_older_lane` and its call (`HA/wizard/new_person.py:348-372`), fix
the "BOTH LANES" docstring (:30-33), delete `counts_as_line()` (`HA/models/access_role.py:70`)
if grep shows no caller, drop `legacy_note` returning `''` only if the provider protocol
allows omission (else leave, note it).

## 4. Browser QA (chrome-devtools, on the clone URL, then live)
Sign in as an **Admin-role** user (not ash): Hand-overs lens shows the 4 running hand-overs
with chips; passport "Give a role" multi-select; "Copy from another person" preview; the
hand-over dialog's "Handing over for" row; role card "Guarded" chip on Owner; the
self-grant refusal toast. Screenshots into `docs/handovers/access_ar1_shots/`.

## 5. Deploy (one sitting, R3 rule — H4c)
1. Clone `carejiox` → `carejiox_ar1`, neutralise `biz_tenant` rows (H102), private
   `--addons-path`, run §3.K there.
2. Backup live: `pg_dump -Fc` of `carejiox`, `carejiox_template`, `hhh` to
   `/var/backups/access_ar1/`.
3. `scp` both modules → `carejiox-deploy -d -m biz_access,health_access` (master), then
   `-D carejiox_template`, then `-D hhh` — all three before you stop. Bump
   `web.assets.version` if the wrapper does not (ledger B5 precedent).
4. Verify: live diff of users × roles before/after = 0 lost (reuse `HA/diff.py`
   `access_snapshot_diff`); an Admin user's Hand-overs lens on carejiox.com; hhh.carejiox.com
   200 and its Access home opens.

## 6. Report back
Per test: PASS/FAIL with the assertion. Suite counts on the clone. Any spec deviation, with
why. New ledger entries (§5.209+) you appended. The users on live who gained
`group_access_manager` through A (names). Commit hashes (commit per item group, messages in
the repo's plain-sentence style, `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`).
Do not push.
