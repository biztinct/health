# MENU IA — M1: the shell (rail + drawer + tab column + segment strip)

Status: HANDOVER to Opus (written 2026-09-29; launches after ACCESS AR-2 reports). Designed
by Fable. Read first: `docs/handovers/MENU_IA_PROGRAM.md` (§1 verified facts, §2 design, §4
owner rulings — all binding), `docs/strategy/HANDOVER-CONVENTIONS.md` §2/§4 + ledger tail
(continue numbering after AR-2's last entry), and the AR-2 report (it touched
`health_access/models/cms_sidebar.py` and `health_landing/.../admin_model_navigator.js`).

**This phase changes HOW the menu is drawn. It changes NOTHING about what is in it.** Every
section, item and child keeps its xmlid, section, parent, sequence, gate and action. The only
data additions are the two new sections `home` and `learn` with their items (§3.F/G). The
catalogue consolidation is M2, not here.

## 0. Standing rules
- White-label (no "Odoo"), plain-English copy, `--vu-*` tokens (this is a health_* shell,
  not biz_kit), flat colours, **FontAwesome classes on `item.icon`/`section.icon` stay** (the
  data carries them; masks would need a migration of 120 rows — not this phase).
- Dropdown containment guard §5.96: NO `transform`, `contain`, `filter`, `opacity<1`,
  `container-type` on any ancestor of the action container. Animate `width`/`left`/`padding`
  only. `.ops-layout-wrapper` stays the single owner of the `//ActionContainer` xpath; keep the
  layout-restore rules in `ops_sidebar_global.scss:13-45`.
- `@api.model` on every override of `get_sidebar_data`/`_sidebar_visible_items` (F46).
- Seeds noupdate=1 + migration for anything an upgrade must apply; `post_init_hook` does not
  fire on `-u`.
- Tests via `systemd-run` on a spare port, `--db-filter=^<clone>$`, never `-t` on live;
  HttpCase tours need `--workers=0` and no `--no-http` (memory: HttpCase needs http).
- Versions: `health_cms_sidebar` → next minor, `health_fieldservice`, `health_theme`,
  `health_learn` bump only if their data/manifest change. Commits in plain sentences ending
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; no push.

## 1. Scope

| # | Item | Module |
|---|---|---|
| A | Rail (60px) ⇄ drawer (240px) — one entry per section, `section.icon`, hover-widen over the page, « toggle, per-user memory, large-screen default expanded | health_cms_sidebar (component) + health_fieldservice (wrapper scss) + health_theme (tokens) |
| B | Tab column (76px, white) = root items of the active section; last-tab memory per section; `cms_tab` deep link | health_cms_sidebar |
| C | Segment strip in the page header = children of the active item; parent tab opens first visible child | health_cms_sidebar |
| D | Page header: catchment pill (native select) + section › tab › segment breadcrumb text | health_cms_sidebar |
| E | Highlight + allowlist fixes: full-tree index, leaf-own-action first, stale highlight cleared, allowlist refreshed on `CMS_SIDEBAR:RELOAD` | health_cms_sidebar |
| F | Home rail entry (section `home`, seq 0) with **role-aware landing** resolved server-side | health_cms_sidebar (section+item) + health_access (resolver by role area) |
| G | Learn rail entry (section `learn`, seq 38): move `health_learn.item_learn_journey`-style Training item out of CRM into it (edit the GENERATED seed at its source + regenerate); the Training-admin expander (ADMIN seq 200, 5 children) moves under `learn` too | health_cms_sidebar (section) + health_learn + health_access (seed edit) |
| H | Keyboard + ARIA: real `<button>`s, `aria-current`, ↑↓ in the tab column, Alt+1..9 rail jump, Esc closes the hover-drawer | health_cms_sidebar |
| I | Breakpoints: ≥1920 drawer default; <1920 rail; ≤1024 rail 56px + tab column 56px labels hidden; ≤768 tab column → horizontal scroll strip under the header, rail → bottom icon bar | health_cms_sidebar + health_fieldservice |
| J | Fix the shared `_0` storage key (use `user.userId`) for collapse/fold/tab memory | health_cms_sidebar |
| K | Tests (Python + one HttpCase tour) + browser QA + deploy | — |

Non-goals: moving/merging/renaming any existing entry (M2), Vietnamese (AR-3), coach anchors
(AR-3), changing `get_sidebar_data`'s payload shape (ADDITIVE keys only), the PWA shell,
the Odoo top bar (stays; `.o_menu_sections` stays hidden), the admin tab strip
(`admin_model_navigator.js`), hf-wt-ico icon migration, a ⌘K palette.

## 2. Verified plumbing (2026-09-29 — do not re-derive)
See `MENU_IA_PROGRAM.md` §1.1 for the full map. The seams you will edit:
- Component `CmsSidebar` `health_cms_sidebar/static/src/js/cms_sidebar.js` (setup :14, state
  :23, `_loadSidebarData` :65, `_buildMatchIndex` :81, `_resolveActiveItem` :110,
  `_expandParentOf` :133, `toggleSection` :140, `onItemClick` :153, `toggleItem` :162,
  `navigateTo` :173 (catchment domain AND at :173-197), `_catchmentDomain` :220,
  `onCatchmentChange` :255, `navigateHome` :312, `isActive` :316, `_loadCollapseState` :320,
  `_saveCollapseState` :332, legacy sidebar removal :348-355, bootstrap sets :357-464,
  registry entry `cms_unified` :466-471, `cms_sidebar_keys` service :481-497). Template
  `static/src/xml/cms_sidebar.xml` (80 lines: logo :6-12, catchment :14-38, nav :40-68,
  user :70-76). SCSS `static/src/scss/cms_sidebar.scss` (124 lines; bg `!important` :1-2,
  native select note :57-60) and `health_fieldservice/static/src/scss/ops_sidebar_global.scss`
  (246 lines; hide `.o_menu_sections` :7-11, layout restore :13-45, width :48, active border
  `#42A5F5` :116-146, the ≤1024 rule :185-246). Host `health_fieldservice/static/src/js/
  sidebar_host.js` (74 lines; registry pick passes 0/1/2 :20-61; `body.has-custom-sidebar`
  :62-73); wrapper xpath `ops_webclient_patch.xml:5-10`.
- Server payload `cms_sidebar_item.py:162-218` (`get_sidebar_data`), `get_match_keys` :68-83
  (includes inactive rows), `get_catchment_scope` :97-104, per-item `catchment_field` :106-142,
  section keys sent `id,name,key,icon,color,items` :214-215.
- Theme tokens `health_theme/static/src/scss/primary_variables.scss:300-312`
  (`--vu-sidebar-width` 220px, `--vu-sidebar-bg #0D356B`, `--vu-sidebar-text`,
  `--vu-sidebar-hover`, `--vu-navbar-height 46px`); dimension whitelist `DIMENSION_KEYS`
  `health_theme/models/vu_theme.py:33-37`; chrome override `backend_01_chrome_forms.scss:25-28`.
- Live sections + icons: home(new) · crm 10 `fa fa-comments` "CRM" · ops 20 `fa fa-heartbeat`
  "OPERATIONS MANAGER" · finance 30 `fa fa-university` · clinical 32 `fa fa-stethoscope` ·
  interop 35 `fa fa-exchange` · analytics 37 `fa fa-area-chart` · learn(new 38) · admin 40
  `fa fa-cogs`. Section `color` empty everywhere. Rail LABELS come from `section.name` — M2
  renames "OPERATIONS MANAGER"→"Operations" etc.; M1 renders the names as they are but in
  Title Case in the rail/drawer (CSS `text-transform` only — the data stays).
- Role areas (for Home): `biz.access.role.area` ∈ clinical / front_desk / operations /
  finance / admin (`health_access/hooks.py:68-75`); the 9 roles and their areas are in
  `ROLE_NOTES` (~:271-326). Landing actions: front_desk → `health_care_command.action_care_command`
  (fallback `health_crm.action_crm_dashboard` if care_command feature off — use
  `biz.tenancy.feature_of_action`/`features_off()`), operations/admin →
  `health_fieldservice.action_ops_command_center`, finance →
  `health_invoicing.action_fin_dashboard`, clinical → `health_vitals.action_health_observation`.
  A person with several roles: highest-precedence area wins in the order
  admin > operations > front_desk > finance > clinical (an Owner lands on Operations).
  Nobody with a role → Operations dashboard. Cache per user groups; drop on
  `CMS_SIDEBAR:RELOAD`.
- Learn seeds: `health_learn/data/learn_sidebar_item.xml` is GENERATED (header says so) from
  `docs/tutorial_crm/tools/gen_learn_data.py` — change the source, regenerate; the Training
  admin expander is `health_access/data/cms_sidebar_items_topbar.xml` (ADMIN seq 200 + 5
  children, gated Admin/Owner via `NEW_ITEM_ROLES`-style hooks — check `health_access/hooks.py`
  `_gate_new_items`). health_learn's `fixture.js:549-630` hard-codes the CRM menu incl.
  Training at seq 90 — update it (and `docs/tutorial_crm/practice-data.js`) so
  `test_bundle`/`test_coach` stay green.
- Tour precedent: `health_care_command_channels/tests/test_golive.py:1289` `start_tour`.
  Coverage/consolidation/clinical/access/tenancy Python tests read the payload by names/keys —
  ADDITIVE payload keys will not break them; a changed `items/children` shape WILL (Learn walks it).

## 3. Design

### A. Rail ⇄ drawer
- One `<aside class="vu-rail">` in two states. Width tokens `--vu-rail-w: 60px`,
  `--vu-drawer-w: 240px` (add to `primary_variables.scss` + `DIMENSION_KEYS`; keep
  `--vu-sidebar-width` as an alias = drawer width for older SCSS). Colours from
  `--vu-sidebar-bg/-text/-hover`; active fill `rgba(255,255,255,.14)` + `inset 3px 0 0
  var(--vu-brand-accent, #42A5F5)`.
- Content top→bottom: logo block (image + "VIET UC"/"CMS" — keep the strings, they are M2/AR-3
  business), rail entries (Home first, then sections by sequence, Settings/ADMIN pinned to the
  bottom above the avatar), avatar block. Each entry = `<button>` with `section.icon`, label
  (`.vu-rail-label`, hidden in rail state), native `title`.
- Rail state: 60px, hover widens to 240px OVER the page (absolute, z-index ≤ 20, shadow),
  160ms width transition; Esc/mouse-leave closes. Drawer state: 240px in-flow sibling (page
  reflows). « button in the drawer header toggles; state stored in
  `localStorage vu.rail.mode.<uid>` = auto|rail|drawer; auto = drawer at ≥1920, rail below.
- Group headings in the drawer: not needed in M1 (sections ARE the entries). Reserve: a
  section `group` key may come in M2.

### B. Tab column
- `<nav class="vu-tabcol" aria-label="…">`: 76px white, hairline right, buttons 60px:
  17px FontAwesome icon over a 9px/800 uppercase label (letter-spacing .04em; measure every
  label fits 60px — abbreviate via CSS ellipsis + `title`, NOT by editing data). Active
  `aria-current="page"` + `--vu-tab-active` soft fill.
- Contents = root items of the active section (`section.items`, parents included). Clicking
  a leaf navigates as today (`navigateTo`, catchment domain kept). Clicking a parent opens its
  first visible child and shows the segment strip (C).
- Memory: `localStorage vu.tab.<uid>.<sectionKey>` = item id; clicking a rail entry opens the
  remembered tab (else the first). Deep link: action context `cms_tab: "<xmlid>"` wins.
- Which section is active = the section owning the highlighted item (E); if none, the last
  rail entry clicked.

### C. Segment strip
- Rendered by the shell in a slim page header (`.vu-pagehead`, 40px, in the wrapper ABOVE
  `ActionContainer`, in-flow — this is chrome, not part of the action). Pills = the active
  item's visible children; active pill = the highlighted child. Only shown when the active
  item has children. Parent stays lit in the tab column.

### D. Page header
- Left: catchment pill (the existing native `<select>`/pill moved here unchanged). Middle:
  breadcrumb text "Section › Tab › Segment" (plain, muted). Right: empty in M1 (reserved).
- Header hidden when no sidebar is shown for the action (same rule as `body.has-custom-sidebar`).

### E. Highlight + allowlist
- Build the maps from the full visible tree; on resolve, try the leaf's own action first
  (§5.150) then parents; when nothing matches, clear `activeItemId` (no stale highlight) but
  keep the last section so the tab column does not blank.
- The `cms_sidebar_keys` service subscribes to `CMS_SIDEBAR:RELOAD` and re-fetches
  `get_match_keys` (today it never refreshes).

### F. Home
- Seed `health_cms_sidebar.section_home` (`technical_key='home'`, seq 0, icon `fa fa-home`,
  name "Home") + `item_home` (seq 10, `action_tag='cms_home'`). New client action tag
  `cms_home` (health_cms_sidebar) that asks the server `cms.sidebar.item.home_action()` and
  `doAction`s the xmlid it returns. Base implementation returns
  `health_fieldservice.action_ops_command_center`; `health_access` overrides with the role
  rule in §2 (respecting `features_off()`). `menu_cms_root`'s action stays as is.
  `item_home` carries `match_action_tags='cms_home'` only — it must NOT claim the dashboards'
  xmlids (they belong to their sections' Dashboard items).
- The Home rail entry is never gated and never hidden.

### G. Learn
- Seed `section_learn` (`technical_key='learn'`, seq 38, icon `fa fa-graduation-cap`, name
  "Learn"). Move the Training journey item (currently CRM seq 90, `health_learn` generated
  seed) into it at seq 10; move `health_access.item_admin_training` (+5 children) into it at
  seq 20 (edit the seed XML + a health_access migration that re-homes on upgrade; keep the
  Admin/Owner gate). Feature key `learn` keeps working (`_feature_key_of` walks item→section).
  Update `fixture.js` + `practice-data.js` + any `sidebar_key` in `learn_stations.xml`.
  `biz_bi_cms/tests/test_hub.py` asserts ANALYTICS sits between FINANCE and ADMIN — seq 38
  keeps that true.

### H/I/J — as scoped in §1. Phone rule: the bottom icon bar shows Home + sections (Settings
last); the hover drawer is replaced by a tap-to-open overlay (width animation, no transform).

## 4. Tests (numbered)
1. Payload contract: `get_sidebar_data()` keys unchanged for existing sections/items
   (snapshot-compare against a clone before/after for 3 users: Owner, Nurse, Accountant —
   identical except the two new sections).
2. Home: `home_action()` returns Care Command for a CRM-only user, Operations for Owner,
   Finance for Accountant, Observations for Nurse; care_command feature off → CRM dashboard;
   no role → Operations.
3. Learn section exists at seq 38 with the journey + admin expander; `biz_bi_cms` test_hub
   green; `health_learn` `test_bundle` + `test_coach` green; the feature key `learn` still
   hides the section when the feature is off (`health_tenancy` TestFeatureGate green).
4. `get_match_keys` refresh: after `CMS_SIDEBAR:RELOAD` a newly activated item's action is in
   the allowlist without a page reload (JS unit via tour or a HttpCase that toggles and asserts).
5. Highlight: opening a child's action lights the child pill and its parent tab and section;
   opening an unknown action clears the item highlight and keeps the section.
6. Tour (HttpCase): as Owner — rail shows Home + 9 areas with Settings last; click CRM → tab
   column lists CRM's root items; click Phone → Calls opens and the segment strip shows the
   4 children; reload → CRM reopens on Phone (memory); « toggles drawer and persists; Alt+3
   jumps to the third rail entry; Esc closes the hover drawer.
7. Gating unchanged: a Nurse's rail shows only the sections her roles open; tab column shows
   only her items (compare to `visibility_for`).
8. Storage keys carry the real uid (two users on one browser get different memory).
9. Dropdown guard: the theme's guard test/grep (`health_theme` dropdown_trap_guard) passes —
   no forbidden properties on `.ops-layout-wrapper`, `.vu-rail`, `.vu-pagehead`.
10. Full suites green on the clone: health_cms_sidebar, health_fieldservice (sidebar tests),
    health_cms_coverage, health_cms_clinical, health_access, health_tenancy, health_learn,
    biz_bi_cms, health_catchment_scope, health_care_command_voip, health_care_command_channels,
    health_web_leads; counts before/after.

## 5. Browser QA (chrome-devtools, clone then live)
Owner, Nurse and Accountant accounts: rail collapsed + hover; drawer via «; tab column per
area; segment strip on Phone / Care Intelligence / Medications / AR Management; catchment
pill switch still scopes a list; ≥1920 default drawer; 1024 and 768 widths; keyboard.
Pixel pass: rail width, tab label fit (every label), active states, no horizontal page
scroll. Screenshots → `docs/handovers/menu_m1_shots/`.

## 6. Deploy
Clone rehearsal (neutralise `biz_tenant` rows) → backups `/var/backups/menu_m1/` → master →
template (re-disable crons) → hhh, one sitting → `web.assets.version` bump → live: three
accounts' `get_sidebar_data` snapshot diff = 0 lost → screenshots on carejiox.com + hhh.

## 7. Report back
Tests 1-10 PASS/FAIL, suite counts, deviations, ledger entries, the Home rule as shipped,
commit hashes, live evidence, tab labels that needed ellipsis (list them for M2 renaming),
anything undone. Plain English for the owner + engineering appendix.
