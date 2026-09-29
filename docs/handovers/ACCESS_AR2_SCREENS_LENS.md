# ACCESS REVAMP — AR-2: the Screens lens, the passport's sub-screens, the dark screens

Status: HANDOVER to Opus (written 2026-09-28, launches after AR-1 reports). Designed by
Fable. Read first: `ACCESS_REVAMP_GAP_ANALYSIS.md`, `ACCESS_AR1_REPAIR_POLICY_PEOPLE.md`
(AR-1 changed the facade/JS/XML — **re-read the AR-1 report and `git log` before you
touch a line**; the seams below are named by METHOD, not line), and
`docs/strategy/HANDOVER-CONVENTIONS.md` §2/§4 + ledger tail (continue numbering after
AR-1's last entry).

Owner decisions that bind this phase: **remove** the dead "Show it locked, with a note"
switch (Carejiox's menu hides, never teases); **block (section) gates editable on the
Screens tab**; **abilities for the dark screens, granted to nobody**; **passport opens
into sub-screens**. No approvals, nothing needing e-mail, no Vietnamese yet (AR-3).

## 0. Standing rules
Same as AR-1 §0 (white-label, plain English, `biz_access` product-agnostic, `--bzk-*`,
`ic()`, no `-t` on live, `--db-filter`, migrations for seed changes, commit style, no push).
Versions: `biz_access` → **19.0.1.4.0**, `health_access` → **19.0.1.4.0**,
`health_landing` bump only if you change its manifest data.

## 1. Scope

| # | Item | Module |
|---|---|---|
| A | Section (block) rows in the Screens lens with editable role gates; "everyone with a login" misreport fixed | biz_access (protocol + lens) + health_access (provider write) |
| B | Teaser switch hidden when the provider cannot restrict | biz_access (capability flag) — Carejiox provider says no |
| C | Passport mini-rail expands parents into children ("3 of 5"), same in "See it as" | biz_access |
| D | Dark screens: 3-4 new abilities in the clinic catalogue; Screens lens shows switched-off entries with "could be opened by …" and a one-click switch-on | health_access (abilities) + biz_access (lens) |
| E | "Re-seed the role catalogue" door for the platform administrator | biz_access |
| F | Settings tab strip entry registered through `health_landing.admin_tabs`, not hard-coded | health_access + health_landing |
| G | `clinical_kind` editable on the role form | health_access |
| H | Tests + browser QA + deploy (master, template, hhh) | — |

Non-goals: Vietnamese, coach anchors (AR-3), any change to `health_cms_sidebar`'s
rendering beyond what A needs (the section gate ALREADY exists there — you only add the
write path), top-bar editor, approvals, mail.

## 2. Verified plumbing (2026-09-28 — do not re-derive; re-locate lines after AR-1)

- RailProvider protocol: `BA/models/access_common.py` class `RailProvider` (reads
  `available`, `sections`, `entries`, `visibility_for`, `advanced_action`, `reload_event`;
  writes `set_roles`, `set_active`, `set_restricted`, `reorder` — default
  `NotImplementedError`). Registered via `register_rail`; read through `biz.access.rail`
  (`BA/models/access_rail.py`). The one rule = `rail_state` (AC ~:487-544).
- Clinic provider `HealthCmsRail` in `HA/models/cms_sidebar.py` (~:246-372, registered at the
  end of the file). `biz_role_ids` on `cms.sidebar.section` (~:65, table
  `health_access_section_role_rel`) and on `cms.sidebar.item` (~:77, `health_access_item_role_rel`).
  `effective_biz_role_ids` (~:84-121) = own ∪ section ∪ parent chain (archived kept).
  `_sidebar_visible_items` (~:125-181) is the real menu rule; `visibility_for` goes through
  `_biz_visible_map` (~:204-240). `group_ids=[]`, `restricted=False` (~:300-302);
  `set_restricted` raises (~:351-354); `reorder` numbers in tens (~:356).
- Lens server side: `screens_board` (F, search the name; sections dropped in the block that
  builds `rows` — the inventory saw it at ~F:1830-1838), `_screen_row` (~F:1701 — `everyone`
  flag and `seen_by` computed from the entry's OWN `role_ids`, not effective), `_seen_by_counts`
  (~F:1768), `screen_detail`, `_who_sees`, `set_screen_roles`, `set_screen_flags`,
  `reorder_screens`. Browser: `loadScreens`, `loadScreen`, `toggleGate`/`_writeGates`,
  `setScreenActive`, `setScreenRestricted`, `onDrop`/`nudge`/`onScreenKey`,
  `afterScreenWrite` → `reloadRealMenu` fires `CMS_SIDEBAR:RELOAD`. Templates: Screens
  block in QW (search `bza-screens`), the "Everybody else" chips (search "Do not show it at
  all").
- Live sections (2026-09-28): CRM, OPERATIONS MANAGER, FINANCE, ADMIN (1 role: Owner),
  CLINICAL, INTEROP & COMPLIANCE, ANALYTICS — all active. 114 active items, 96 gated.
- Passport: `passport` → `_rail_as_seen_by` (uses `visibility_for`); mini-rail component
  `BizMiniRail` `BA/static/src/js/mini_rail.js` + `xml/mini_rail.xml` — **has no expand
  support** (grep `expandable|toggle|childSummary` = nothing). Payobook's has it:
  `/Users/adity/Documents/GitHub/gitlocal/biz_access/static/src/js/mini_rail.js:96` (`expandable`),
  `:127` (`toggle`), `:132` (`childSummary` "x of y"), `xml/mini_rail.xml`, and the passport
  wiring `PBJS.surfaceCatalogue` :485 / `addSurfaceAccess` :505. Carejiox does NOT need
  Payobook's command-palette `surface_access` — children are real `cms.sidebar.item` rows
  with `parent_id`, already present in `visibility_for(user)['items']`.
- Dark screens on live (all `active=false`, all under `health_access` /`biz_bi_cms` xmlids):
  Zalo: `item_crm_zalo` (parent) + `item_crm_zalo_conversations`, `_messages`, `_settings`;
  Voice: `item_ops_voice` (parent) + `_calls`, `_missed`, `_recordings`, `_extensions`,
  `_sync`, `_config`; Analytics: `biz_bi_cms.item_analytics_import`, `_settings`,
  `_access_rules`, `_ai`. They are off because `_gate_new_items` (`HA/hooks.py` ~:1218,
  map `NEW_ITEM_ROLES` ~:842, helper `role_can_read` ~:1193) narrows a gate to roles whose
  ACLs can read the action's model and switches off what nobody can open. Other OFF items
  on live (Staff/Roster/Schedules, Vitals, Care Plans, Consents, Campaign Review, Telehealth,
  Family Links, Diagnoses, …) are off for OTHER reasons (consolidation/feature keys) — leave
  them alone; D applies only to the 15 above.
- Abilities: `HA/hooks.py` `ABILITIES` (~:97-256, one per group, `technical_key` unique,
  missing group xmlid → skipped with a log line), seeded by `ensure_catalogue`; changes need
  a migration (post_init does not fire on `-u`). `reseed_catalogue` is `F` (system-admin only,
  no button); `biz_tenants/models/service.py` ~:2059 tells the operator to "press Re-read".
- Settings tab: hard-coded `{ id:"access", label:"Access & roles", … }` in
  `addons/health_landing/static/src/js/admin_model_navigator.js` "people" group (~:139-141);
  registry `health_landing.admin_tabs` (~:32; contributions `{group, section, sequence, label,
  icon, model, action}`; unknown group/section dropped). Precedent:
  `health_cms_sidebar/static/src/js/admin_lookup_tabs.js`.
- `clinical_kind` Selection on `biz.access.role` added by `HA/models/access_role.py` (~:62:
  doctor / nurse / operations_manager / other); job flags `is_doctor_role`/`is_nurse_role`
  derive from it (`HA/models/res_users.py`). Role form = `BA/views/access_views.xml`
  (form ~:108+); health_access has view inherits in `HA/views/`.

## 3. Design

### A. Section rows with gates
- Protocol: add `set_section_roles(section_id, role_ids)` to `RailProvider` (default
  `NotImplementedError`) and `supports_section_gates` (default False). `HealthCmsRail`
  implements both (`biz_role_ids` write; True). `biz.access.rail` exposes them.
- `screens_board`: each section becomes a **block row** above its entries with its own
  role chips, `everyone` flag, seen-by count and the "gate flows down to N entries" note.
  Entry rows compute `everyone`/`seen_by`/`gated` from the EFFECTIVE roles (own ∪ section
  ∪ parent), and show a small "through <block/parent>" tag when the gate is inherited.
- `screen_detail` for a block: "Unlocked by" chips editable via `set_section_roles`
  (manage-only, same audit line style as `set_screen_roles`), no on/off, no reorder.
- Facade rule: removing the last role from a block is allowed and simply means "the block
  no longer gates; each entry's own gate decides" — say so in the confirm text.

### B. Teaser capability
`RailProvider.supports_restricted` (default True — Payobook keeps its behaviour);
`HealthCmsRail` returns False. `screens_board` returns `can_restrict`; QW renders the
"Everybody else" block only when true; `set_screen_flags` refuses `restricted` writes with
a sentence when unsupported. Net effect on Carejiox: the switch disappears.

### C. Passport sub-screens
Port Payobook's `expandable` mini-rail (toggle chevron per parent, children listed with
their own state, summary "3 of 5" on the collapsed parent). Data: `_rail_as_seen_by` already
receives every item incl. children from `visibility_for`; group children under their
`parent_id` in the row shape (`children: [...]`). Also used by "See it as" (same component),
the role card's "Opens on the left menu" column (list sub-entries as today's "· a, b" —
unchanged) and the builder preview (unchanged). Keyboard: Enter/Space toggles.

### D. Dark screens
- `health_access` catalogue gains abilities (keys, names, one honest sentence each — write
  them in the screen's words, e.g. **"Work the Zalo channel"** — conversations, messages;
  **"Set up the Zalo channel"** — Zalo settings; **"Handle calls"** — all/missed/recordings;
  **"Set up the phone system"** — extensions, sync, voice settings; **"Set up reporting"** —
  import, reporting settings, who-sees-which-numbers, AI providers). Groups = the groups whose
  ACL grants READ on each action's model (find them; if a model is readable by
  `base.group_user` alone, the ability wraps the most specific module group — never leave an
  ability with zero groups). Migration `19.0.1.4.0` seeds them. **Grant nothing.**
- Screens lens: switched-off entries appear in a collapsed **"Switched off"** block per
  section (count in the header) with the state "Nobody can open it yet" and, when some
  active role's holders CAN read the model (`role_can_read` moved to a shared helper),
  "Could be opened by Owner" + a manage-only button **"Switch on for Owner"** =
  `set_screen_roles([that role]) + set_screen_flags(active=True)` in one facade call
  (`switch_on_for(entry_id, role_id)`), audit line, `CMS_SIDEBAR:RELOAD`.
- The `NEW_ITEM_ROLES` hook must not re-switch-off an entry an Owner switched on: make
  `_gate_new_items` create-only per entry (mark handled with a param or by checking the
  entry already has roles).

### E. Re-seed door
Header overflow (three-dot) visible to `base.group_system` only: **"Re-read the role
catalogue"** → `reseed_catalogue` → toast with counts (roles/abilities before → after).
Update the sentence in `biz_tenants/models/service.py` (~:2059) to name this exact button.

### F. Settings tab via registry
Delete the hard-coded tab; `HA/static/src/js/health_access_palette.js` (or a new
`admin_tabs.js`) registers `{group:"people", section:<the one Users is in>, sequence:20,
label:_t("Access & roles"), icon:"fa-key", model:false, action:"biz_access.action_biz_access_home"}`.
Verify the strip renders the tab in the same place (screenshot).

### G. `clinical_kind` on the role form
health_access view inherit adds the field to the role form (after `area`) with help
"Which job flags the people holding this role get". Writing it must recompute the job flags
of holders (check `res_users` compute dependencies; add `@api.depends` through the role if
missing). Delete `counts_as_line()` if AR-1 did not.

### H. Tests (numbered)
1. Section row appears with Owner chip for ADMIN; `set_section_roles` by a clinic admin
   writes `biz_role_ids`; a non-manager is refused.
2. Entry gated only through its section reports `everyone=False`, `gated=True`, `via=section`,
   and its seen-by count equals the section rule's — no more "everyone with a login".
3. Removing the last role from a block leaves its entries governed by their own gates
   (`visibility_for` proves it for a Nurse).
4. `can_restrict` is False on Carejiox; `set_screen_flags(restricted=True)` refused with a
   sentence; the template does not render the block (assert the QW has the `t-if`).
5. Passport row shape has `children` for `item_crm_zalo`-style parents; a Nurse's passport
   reports "x of y" matching `visibility_for`.
6. Five new abilities exist after the migration, each with ≥1 group, none in the forbidden
   closure (`TestRailB`), no role gained any of them (holder diff = 0), users×groups diff = 0.
7. Screens lens lists the 15 switched-off entries under "Switched off" with
   `could_be_opened_by=[]` today; after ticking "Handle calls" onto a test role, the Voice
   entries report that role and `switch_on_for` turns the parent on, gates it, and the
   child rows inherit.
8. `_gate_new_items` re-run does not switch that entry off again.
9. Re-seed door: refused for a clinic admin, works for system admin, returns counts.
10. Settings strip: the registry contribution renders the "Access & roles" tab and the
    hard-coded one is gone (JS test or a chrome-devtools screenshot + DOM assertion).
11. `clinical_kind` write on a role flips `is_nurse_role` of its holders.
12. Whole `biz_access`, `health_access`, `health_cms_sidebar`, `health_landing`,
    `biz_tenants`, `health_tenancy` suites green on the clone; counts before/after.

## 4. Browser QA
Clone URL, Admin-role user: Screens lens with block rows and the inherited-gate tag;
"Switched off" block open with the "could be opened by" hint; a passport parent expanded;
no "Everybody else" chips; Settings strip tab. Screenshots → `docs/handovers/access_ar2_shots/`.

## 5. Deploy
As AR-1 §5 (clone rehearsal with neutralised tenant rows → backups → master → template →
hhh in one sitting → `web.assets.version` bump → live diff users×groups = 0 → screenshots
on carejiox.com and hhh.carejiox.com).

## 6. Report back
Tests 1-12 PASS/FAIL, suite counts, deviations with why, ledger entries appended, the five
ability keys + their groups, commit hashes, live evidence. No push.
