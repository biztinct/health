# MENU IA programme — rail + tab column shell, and the consolidated catalogue

Status: DESIGN (2026-09-29). Owner asked for a Payobook-style menu (icon rail + drawer +
per-area vertical tab column, collapsible to give the page room) and a consolidation of the
sub-entries. Runs inside the ACCESS REVAMP block; phased Fable-designs / Opus-builds cycle
already confirmed by the owner for this block (do not re-ask).

Read with `docs/handovers/ACCESS_REVAMP_GAP_ANALYSIS.md` (Access side) and
`docs/strategy/HANDOVER-CONVENTIONS.md` (ledger continues after AR-2's last entry).

## 1. Verified facts (2026-09-29 — do not re-derive)

### 1.1 Carejiox shell today
- Data: `cms.sidebar.section` (`health_cms_sidebar/models/cms_sidebar_section.py:4-17`: name,
  technical_key, sequence, icon, color, active) + `cms.sidebar.item`
  (`models/cms_sidebar_item.py:12-59`: name, section_id, parent_id, sequence, icon [FontAwesome
  class], action_xmlid/action_tag, active, match_action_tags/xmlids/models). Overlays add
  `biz_role_ids`/`effective_biz_role_ids` (health_access) and `feature_key` (health_tenancy).
  No constraints at all (no uniqueness, no depth check). Two levels only; a parent never
  navigates (`cms_sidebar.js:153-160`); the server nests direct children only (`:200-206`).
- Live catalogue 2026-09-29: 7 active sections (crm 10, ops 20, finance 30, clinical 32,
  interop 35, analytics 37, admin 40), 114 active items of which 8 parents carry 30 children.
  Section `icon`/`color` are sent by the server and **never rendered** (`cms_sidebar_item.py:214`).
- Rendering: `health_fieldservice/static/src/xml/ops_webclient_patch.xml:5-10` replaces
  `//ActionContainer` with `.ops-layout-wrapper > SidebarHost + ActionContainer`; `SidebarHost`
  (`sidebar_host.js:20-61`) picks a component from `registry.category("custom_sidebars")` on
  `ACTION_MANAGER:UI-UPDATED`; `CmsSidebar` (`health_cms_sidebar/static/src/js/cms_sidebar.js`,
  template `xml/cms_sidebar.xml:4-78`) is ONE flat template: logo (hard-coded "VIET UC / CMS"),
  catchment `<select>`, sections with chevrons, items, children, user block. Width
  `--vu-sidebar-width` 220px (`ops_sidebar_global.scss:48`, token
  `health_theme/.../primary_variables.scss:306`); ONE breakpoint `max-width:1024px` → 56px hover
  rail (`scss:185-246`). No keyboard, no ARIA, no phone rule. Section collapse stored under
  `cms_sidebar_collapse_${session_info.uid||0}` — uid is undefined → **all users share key `_0`**
  (`js:284-290, 320-342`). Item expansion not persisted. No whole-rail toggle.
- Match/highlight: `_buildMatchIndex` `js:81-108` (tag > xmlid > model, last-wins, active
  items only); `_resolveActiveItem` `js:110-131` keeps a stale highlight when nothing matches.
  Shell allowlist = `get_match_keys()` incl. INACTIVE rows, loaded once at startup by the
  `cms_sidebar_keys` service (`js:481-497`) and NOT refreshed on `CMS_SIDEBAR:RELOAD`.
  Bootstrap sets hard-coded at `js:357-464`. Ledger §5.94 (satellites use xmlids only),
  §5.150 (parents claim children's actions; resolvers try the leaf's own action first),
  §5.189 (hand-built act_window dicts have no xml_id).
- Visibility: `get_sidebar_data()` (`cms_sidebar_item.py:162-218`, `@api.model`) →
  `_sidebar_visible_items` MRO base → health_access (role lane, admin = `base.group_system`
  only, `models/cms_sidebar.py:172-229`) → health_tenancy (feature filter, applies to admins
  too). Hidden/inactive parent hides children; empty section hidden. `@api.model` is NOT
  inherited — every override must carry it (fleet ledger F46).
- Catchment: `get_catchment_scope()`; `navigateTo` ANDs the scope into the action domain
  (`js:173-197`); pick stored under `cms_catchment_${user.userId}`; native `<select>` on
  purpose (dropdown containment guard §5.96 — NO `transform`/`contain`/`filter`/`opacity<1`
  on any ancestor of form fields; animate width/position only).
- Top bar: only `.o_menu_sections` hidden (`ops_sidebar_global.scss:7-11`); `.o_main_navbar`
  (apps grid, systray: language, chat, activities) stays; `biz_access.topbar_mode=admin_only`
  trims non-admins' apps to `health_cms_sidebar.menu_cms_root` (action
  `health_fieldservice.action_ops_command_center`, `cms_sidebar_menus.xml:6-10`).
- Coach anchors after `MainComponentsContainer`, never on ActionContainer
  (`health_learn/static/src/coach/coach_patch.xml:4-13`).
- PWA (`/health_pwa`) is a separate shell — untouched by this programme.
- Consumers (compatibility contract): health_access provider `HealthCmsRail`
  (`models/cms_sidebar.py:294-441`: sections/entries/visibility_for/set_roles/
  set_section_roles/set_active/reorder/advanced_action/reload_event); health_tenancy
  (`feature_key`, `feature_action_map` reads match lists, `menu_preview`); health_cms_coverage
  hooks write active/name/section/parent/sequence/match/biz_role_ids on fixed xmlids;
  **health_learn hard-codes the CRM/OPS/FIN menus, labels and sequences** in
  `static/src/engine/fixture.js:549-630` (+ `docs/tutorial_crm/practice-data.js`) and walks
  `get_sidebar_data()` `items/children` (`models/learn_station.py:247-265`);
  `health_landing` admin tab strip (`admin_model_navigator.js`, registries
  `health_landing.admin_tabs` / `admin_tab_groups`).
- Seed files: most `noupdate="1"` (re-homing needs hooks + migrations, and coverage test t05b
  requires hook-written rows to be noupdate=1); **noupdate="0" satellites re-assert their own
  section/sequence/parent on every `-u`**: `biz_bi_cms`, `health_care_command`,
  `health_care_command_channels` (3 files), `health_care_command_voip`, `health_web_leads`,
  `health_google_ads`, `health_learn` (generated file), and
  `health_cms_sidebar/data/cms_sidebar_items_ops_schedule.xml`. Any consolidation must edit
  THOSE seed files too.
- Tests that pin data (all Python, none pin the DOM): `health_cms_coverage/tests/
  test_cms_coverage.py` + `test_cms_consolidation.py` (t07: no active expander without action
  or active children; t05b noupdate), `health_cms_clinical/tests`, `health_access/tests/
  test_rail_gate.py` + `test_provider.py` ("the home draws exactly what the menu draws") +
  `test_ar2_screens.py` (`switched_off >= 15`, admin section by key) + `test_retirement.py`
  (:220 a heading's active flag equals whether it has children), `health_tenancy/tests/
  test_overlay.py`, `biz_bi_cms/tests/test_hub.py:318` (ANALYTICS between FINANCE and ADMIN;
  key `analytics`), `health_care_command_voip/tests/test_bridge.py:196-222` (Phone is a root
  expander w/o action in section_crm), channels `test_golive.py:1113,1206`, web_leads
  ×3 (leaf is a root), `health_catchment_scope` (catchment_field in payload), `health_learn`
  `test_bundle.py:135` + `test_coach.py:300,357`.
- Section xmlids `health_cms_sidebar.section_{crm,ops,finance,admin,clinical,interop}` +
  `biz_bi_cms` analytics are `ref`'d everywhere — **never rename or renumber them**.

### 1.2 Payobook shell (the reference)
- ONE `<aside>` in two states: drawer 256px (`#0E1430`, header "Payobook / Payroll Suite",
  « button, group headings Operate/Understand/Grow) or rail 60px (labels hidden, hover widens
  to 256px OVER the page with a 160ms width animation, no reflow) —
  `pb_sidebar/static/src/xml/pb_sidebar.xml:5-65`, `biz_theme/static/src/scss/
  biz_breakpoints.scss:40-92`, `biz_sidebar.scss:26-29`. Mode persisted in localStorage
  `biz.sidebar.mode.<uid>` (auto|collapsed|expanded; auto = rail below 1920px)
  (`biz_sidebar_state.js:47-61`). Group folds in `pb_sidebar_collapsed` (not per user — a
  known wart). Active entry: rgba(99,102,241,.26) fill + `inset 3px 0 0 #818CF8`. Tooltip =
  native `title`. 9 rail entries; every one opens a HUB.
- Hub (`pb_hub/static/src/js/hub_shell.js:67-89`): dark command bar (brand, back chip,
  context, tracker, ⌘K, cog, avatar) + **76px white tab column** (60px buttons, 17px icon over
  9px/800 uppercase label, letter-spacing .04em, active `#EDEAF8`/`#5A4BB0`, `aria-current`)
  + canvas. Tab choice: `pb_lens` context → localStorage `pbhub.<key>.lens.v1` → default →
  first; blocked tabs ABSENT not greyed (`hub_gates.js:35-60`); only the active tab mounted.
  Below 1099px: column 56px, labels hidden. Tabs are JS registry entries, not sidebar rows.
- Five decisions behind the feel: one rail entry per domain with old screens as tabs; a hub
  reopens on the last tab and every link can name a tab; tabs you can't use are absent; the
  rail always shows where you are (match lists) and every cross-hub jump has a back chip; the
  chrome gets out of the way (60px rail, hover-expand, ⌘K).
- Ledger warts to avoid: W71 (flat last-wins highlight maps), W98 (open by xmlid not tag),
  R63 (60px label box — measure every label), W151 (root class names are global), fold storage
  not per user, two wrong breakpoint comments.

## 2. The design

### 2.1 Shape — three columns, two levels, data model unchanged
```
┌──┬────────┬─────────────────────────────────────────┐
│  │  RUN   │  [catchment ▾]  Bookings › (segment strip: Calls | Call backs | Recordings) │
│▣ │  RUNS  │                                          │
│⚡│  …     │              the screen, unchanged        │
│  │        │                                          │
│⚙ │        │                                          │
│MA│        │                                          │
└──┴────────┴─────────────────────────────────────────┘
 rail   tab column        page
```
- **Rail** (60px, dark `--vu-sidebar-bg`, hover/« → 240px drawer with group headings) = one
  entry per **section**. Uses `section.icon` (already in data) and `section.name`. Order =
  section sequence. Bottom: Settings (ADMIN) pinned above the avatar, Payobook-style.
- **Tab column** (76px, white) = the **root items** of the active section, icon over a
  small-caps label. Remembers the last tab per section (`localStorage cms.tab.<uid>.<section>`),
  deep-linkable via action context `cms_tab: <item xmlid>`.
- **Segment strip** (inside the page header, pill strip) = the **children** of the active
  item. A parent tab opens its first visible child. This is exactly the "parent never
  navigates" rule rendered differently — no data change, coverage/retirement/voip tests hold.
- **Catchment pill** moves into the page header (left), still a native `<select>`.
- **Home** rail entry (new section `home`, seq 0, one item → `action_ops_command_center`;
  role-aware landing is an owner option, §4 Q1).
- **Learn** becomes a rail entry (new section `learn`, seq 38, Training journey + the
  Training admin children) — owner option Q3.
- Blocked entries are absent (as today); the "Switched off" state stays in the Access lens only.
- Phone/tablet: ≤1024 rail stays 56px hover; tab column 56px labels hidden; ≤768 tab column
  becomes a horizontal scroll strip under the page header; rail becomes a bottom bar of icons.
- Keyboard + ARIA: rail/tabs are real `<button>`s with `aria-current`, ↑↓ within the tab
  column, Alt+1..9 jumps to a rail entry, `?` remains the Coach's.
- Persisted state per real uid (`user.userId`, NOT `session_info.uid`), fixing the shared
  `_0` key.
- All chrome animates width/left only (dropdown guard §5.96); wrapper stays the single owner
  of the `//ActionContainer` xpath; layout-restore rules kept; `.o_main_navbar` kept.
- Highlight: keep the three maps but build them from the FULL tree (parents + children), keep
  "leaf's own action first" (§5.150), and clear a stale highlight when nothing matches. Refresh
  the allowlist on `CMS_SIDEBAR:RELOAD` (today it never refreshes).

### 2.2 The consolidated catalogue (MENU-2) — 114 entries → 9 areas, ~50 tabs, ~55 segments
Rule: a tab is a place you go; a segment is a view of the same place. Setup screens go to
Settings. Every current action keeps an entry (nothing becomes unreachable); role gates move
with the entry (a segment inherits its tab's gate, a tab its area's — `effective_biz_role_ids`
already does this).

| Area (rail) | Tabs → segments |
|---|---|
| **Home** | (the person's landing screen) |
| **CRM** | Dashboard · Care Command · **Channels** → Channel Center, Unrouted Contacts, Channel audit, Channel messages, Watchlist phrases · **Phone** → Calls, Call backs, Recordings, Records from the phone system · **Contacts** → Contacts, Relationships · Activities · **Web & Ads** → Web Touchpoints, Lead Analysis, Google Ads |
| **Operations** | Dashboard · Bookings · Clients · **Schedule** → Staff Schedule, Time Off, Workload · Collections · Family Inbox · Routes · **Exceptions** → First-visit offers, Timecard mismatches · **Development** → Employee development, Coaching |
| **Clinical** | Observations · **Care Intelligence** → Worklist, Alerts, NEWS2 · **Medications** → Orders, Administration Register · Assessments · **Incidents** → Register, Corrective Actions, Analysis · Consents (expiring) · **Notes** → Unsigned Notes, Voice Notes, Coding Review |
| **Finance** | Dashboard · Invoices · **Receivables** → AR Dashboard, AR Transactions, Overdue Clients · **Payments** → Payments, Account Payment, Cash In Transit, Refund / Credit · VAT Log · BHYT Claims · Service Packages · Red Invoice Log |
| **Compliance** (was INTEROP & COMPLIANCE) | **Terminology** → Medical Codes, Coding Systems, Import Codes · **EMR (VN)** → Export, Readiness · Visit Messaging · EVV Events |
| **Analytics** | Analytics · Explore · Dashboards & schedules · **Data** → Sources, Datasets, Refresh jobs, Pipelines, Semantic model, Glossary |
| **Learn** | Training (journey) · **Training admin** → Lessons, Stations, Learner progress, Learning events, Training wording |
| **Settings** (was ADMIN; cog at the bottom) | Overview · **People** → Users & Roles, Access & roles, Healthcare Staff · **Master data** → Facilities, Pricing, Equipment, Public Holidays, Observation Types, Medication Catalog, Form Templates, Monitoring Devices, Field Requirements · **Connections** → Channels (setup), Reply Templates, Channel Go-Live, Website Connector, Google Ads application, Phone system, Extensions · **Records** → Audit Log, Data Lifecycle, Consent Check Log · Menu (CMS Sidebar Config) · Settings · About · Customers (platform only) |

Counts: tabs 7+9+7+8+4+4+2+9 = 50 (+Home); today's flat+nested 114. Clicks to any screen
≤ 3 (area → tab → segment), with the last tab per area remembered → usually 1-2.

### 2.3 Where each piece lives (no dependency loops — §5.71)
- **Shell rendering** → `health_cms_sidebar` (owns the component) + `health_fieldservice`
  (owns the wrapper xpath) + `health_theme` (tokens). New tokens `--vu-rail-w`, `--vu-drawer-w`,
  `--vu-tabcol-w`, whitelisted in `vu_theme.py:36`.
- **Home + Learn sections** → `health_cms_sidebar` seeds `section_home`; `health_learn`'s
  generated seed moves Training (regenerate from `docs/tutorial_crm/`).
- **Consolidation** → a new glue module `health_cms_ia` (depends on every module that seeds
  rows: cms_sidebar, coverage, clinical, access, tenancy, biz_bi_cms, care_command*, voip,
  web_leads, google_ads, learn) with an idempotent `consolidate_ia()` hook + migration; PLUS
  edits to every noupdate=0 satellite seed so `-u` cannot undo it; PLUS `health_learn`
  fixture/practice-data updates; PLUS Access lens vocabulary ("Area / Tab / Inside the tab")
  and the passport mini-rail drawn as rail+tabs.

## 3. Phase map and sequence (with the Access stream)
1. **AR-2** (Access Screens lens) — resume and finish first: its code is in the tree
   uncommitted; block gates = area gates in the new vocabulary.
2. **MENU-1 — the shell**: rail + drawer + tab column + segment strip + Home + collapse/memory
   + keyboard + phone + highlight fixes. **Zero catalogue changes** (every entry appears where
   it is today, just in the new chrome). Python data tests untouched; add HttpCase tour tests
   for the shell. Deploy master + template + hhh.
3. **MENU-2 — the consolidation**: `health_cms_ia` + satellite seed edits + Learn fixture +
   role-gate re-map + Access lens vocabulary + mini-rail. Before/after per-user reachability
   diff = 0 lost (reuse `health_access/diff.py`). Deploy.
4. **AR-3 — Vietnamese + coach** last, so the new labels are covered.

## 4. Owner rulings (2026-09-29, binding)
- Q1 Home = **each role's own dashboard** (CRM → Care Command; Operations Manager/Branch
  Manager/Admin/Owner → Operations dashboard; Accountant → Finance dashboard; Nurse/Doctor →
  Clinical (Observations); fallback Operations dashboard). Resolved server-side from the
  person's roles (`biz.access.role.area`), overridable per role later.
- Q2 The consolidation table §2.2 **approved as proposed**.
- Q3 **Learn is its own rail entry.**
- Q4 Rail default on laptops = **icons only, widen on hover**; large monitors start expanded;
  remembered per person.
- Sequence §3 stands: AR-2 → MENU-1 → MENU-2 → AR-3.
- Q6 (2026-09-29, from the AR-2 finding that every CLINICAL entry is gated to Admin only):
  **the Clinical area opens for Doctor, Owner and Admin** — NOT Nurse. Applied in M2's gate
  re-map (area gate on `section_clinical` = Doctor + Owner + Admin; entry gates inside
  follow). Record rules untouched.
- Q7: hhh's three ready CRM screens (Channel audit / messages / Watchlist phrases) switched on
  for Owner + CRM by Fable on 2026-09-29.
