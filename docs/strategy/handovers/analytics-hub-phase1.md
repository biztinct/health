# Phase AH-1 handover — `biz_bi_cms` Analytics Hub: plumbing + landing

Stream: **Analytics Hub** (biz_bi → CMS sidebar consolidation).
Read `docs/strategy/HANDOVER-CONVENTIONS.md` first — deploy workflow (§2),
Odoo 19 gotcha ledger, test fixtures. This doc assumes it.

## 1. What this phase is

CMS users (the `/bizapp` shell) have no path to the biz_bi Analytics app —
its only entry is a backend `menuitem` root invisible from the CMS. This
phase ships a new glue module **`addons/biz_bi_cms`** that:

1. adds an **ANALYTICS** section + **Analytics** leaf to the CMS sidebar,
   role-gated to Owner / Operations Manager / Branch Manager / Accountant;
2. grants those roles' users `biz_bi.group_bi_creator` (sidebar visibility
   alone is NOT permission — BI record rules need the group);
3. ships a new **Analytics Hub** OWL client action (`biz_bi.hub`) — a
   friendly landing that consolidates the old Home: search, recents,
   workspace-grouped dashboard cards, and a "Create Report" CTA.

Phase 2 (later) replaces the CTA's target with a guided 3-step report
builder. In THIS phase the CTA opens the existing full Explore builder.

The existing backend Analytics app (Home/Explore/Data/Configuration menus)
is left completely untouched for power users.

## 2. Binding non-goals

- NO guided create-report wizard (Phase 2). CTA → existing Explore.
- NO edits to `biz_bi` core, `health_cms_sidebar`, or `health_fieldservice`
  shell JS. The sanction list is exactly `addons/biz_bi_cms/**` plus the
  two report/evidence paths. If a seam is genuinely missing, smallest
  additive change + record the deviation.
- NO new security groups, ACLs, or record rules — reuse biz_bi's chain
  (`group_bi_viewer → creator → modeler → admin`).
- NO "New dashboard" button on the hub (dashboards get created via the
  Phase-2 save flow). No TV mode, no sharing UI, no workspace management.
- NO catchment scoping — client actions bypass it by design
  (`cms_sidebar_item.py:83-119` returns False for actions without
  res_model); BI self-scopes via workspace record rules.

## 3. Verified plumbing facts (do not re-derive)

**CMS sidebar engine** (`addons/health_cms_sidebar`):
- `cms.sidebar.item` fields: `models/cms_sidebar_item.py:17-48` — `name`
  (translate), `section_id` (required), `parent_id`, `sequence`, `icon`
  (font-awesome class — the template renders `<i t-att-class="item.icon"/>`,
  `static/src/xml/cms_sidebar.xml:53,61`; hf-wt-ico has NO render path
  here), `action_xmlid`, `action_tag`, `role_ids` (m2m `access.role`),
  `match_action_tags` / `match_action_xmlids` / `match_models`
  (comma-separated).
- Chrome persistence is automatic: `cms_sidebar_keys` service RPCs
  `get_match_keys` at boot and mutates the shell registry sets
  (`static/src/js/cms_sidebar.js:448-464`) — any new item's match keys keep
  the CMS shell around its action with ZERO JS edits.
- Role gating is Python-only: `access.role` rows have NO xmlid (verified —
  no `model="access.role"` in any XML). Clone the `ROLE_GATES` +
  `apply_role_gates(env)` pattern from
  `addons/health_cms_coverage/hooks.py:39-88`: resolve roles by `.name`,
  skip missing names (never write `[(6,0,[])]`), call from `post_init_hook`
  AND a `migrations/19.0.1.0.0/post-*.py` script. Items with empty
  `role_ids` are visible to ALL; `access_roles.access_role_group_administrator`
  bypasses gating (`cms_sidebar_item.py:127-150`).
- Conventions doc-in-code: header comment of
  `addons/health_care_command_channels/data/cms_sidebar_items_channel_center.xml:2-26`.
  Notably: always set `<field name="parent_id" eval="False"/>` explicitly
  (XML updates only write named fields; a stale parent survived a deploy).
  Do NOT wrap the records in `noupdate="1"`.
- Precedent for an OWL-client-action leaf: Care Command,
  `addons/health_care_command/data/cms_sidebar_items_care_command.xml`.
- Existing sections: `section_crm/ops/finance/admin` in
  `health_cms_sidebar/data/cms_sidebar_sections.xml`; clinical adds
  `section_clinical`, `section_interop`
  (`health_cms_clinical/data/cms_sidebar_items_clinical.xml:12,19`). Read
  the sequences and slot ANALYTICS **after FINANCE, before ADMIN**.

**biz_bi** (`addons/biz_bi`):
- Client actions (`views/bi_actions.xml`): `action_bi_home`→tag
  `biz_bi.home`, `action_bi_explore`→`biz_bi.explore`,
  `action_bi_dashboard_view`→`biz_bi.dashboard` (orphaned from menus,
  reached via `doAction({tag:"biz_bi.dashboard", params:{dashboard_id}})` —
  see `home_action.js:39`, `dashboard_action.js:74-79`).
- `bi.workspace.get_home_data()` (`models/bi_workspace.py:49-67`) returns
  `{workspaces:[{id,name,description,color,icon,dataset_count,
  dashboard_count,is_default}], is_creator, is_modeler, is_admin}`.
  `icon` is a **lucide icon name** (seeds use `stethoscope`,
  `credit-card`, `target`); the old Home never rendered it.
- `bi.audit.log.get_recents()` (`models/bi_audit_log.py:57-72`) → last 10
  distinct dashboard_view events for the current user.
- `bi.ai` availability check exists (used by `explore_action.js:82-99` in
  `onWillStart`) — read `models/bi_ai.py` for the exact method name and
  call it server-side; expose as `ai_available` (Phase 2 needs it).
- Groups (`security/biz_bi_security.xml`): linear implication
  viewer(:25)→creator(:32)→modeler(:39)→admin(:46). Creators
  create/write/unlink OWN charts+dashboards; record rules scope everything
  by workspace (owner OR member OR group OR fully-public workspace).
- Old Home defects the hub must NOT inherit: 3 sequential awaited RPCs;
  a single unscoped `searchRead("bi.dashboard", limit:40)` (workspaces
  past 40 wrongly show "No dashboards yet"); `window.prompt()`;
  unrendered workspace icon.
- `orm.create()` returns a LIST of ids — destructure (`[id] = await
  this.orm.create(...)`); this exact bug was commit `5e91455e`.
- Frontend URL prefix on this deployment is `/bizapp` (biz_deroute), and
  the hub is webclient-only — no HTTP controllers needed.

**Theme:** flat mono colors only (no gradients, no dual-tone). Reuse
`vu.theme` CSS custom properties where they exist — read
`addons/health_theme/static/src/**/tokens.css` (or wherever tokens.css
lives; grep for `--vu-`) and prefer tokens over hardcoded hex. Never put
`overflow`/`contain`/`clip-path` on ancestors of dropdown-bearing content
(autocomplete over-paint trap, guarded repo-wide in health_theme).

## 4. Build spec

### 4.1 Module skeleton
`addons/biz_bi_cms/`: `__manifest__.py` (name "Analytics Hub (CMS)",
version `19.0.1.0.0`, depends `["biz_bi", "health_cms_sidebar"]`,
`post_init_hook`, license/author matching sibling modules, assets →
`web.assets_backend` globs over `static/src/**/*`), `__init__.py`,
`hooks.py`, `models/`, `views/`, `data/`, `static/src/components/hub/`,
`tests/`, `i18n/vi.po`, `migrations/19.0.1.0.0/post-apply-role-gates.py`.

### 4.2 Sidebar records (`data/cms_sidebar_analytics.xml`)
- `cms.sidebar.section` id `section_analytics`, name `ANALYTICS`,
  `technical_key` per sibling convention, sequence between FINANCE and
  ADMIN (read the actual numbers).
- `cms.sidebar.item` id `item_analytics_hub`: name `Analytics`,
  `section_id ref` the new section, `parent_id eval="False"`, sequence 10,
  icon `fa fa-bar-chart`, `action_xmlid` `biz_bi_cms.action_bi_hub`,
  `action_tag` `biz_bi.hub`,
  `match_action_tags` `biz_bi.hub,biz_bi.dashboard,biz_bi.explore`
  (chrome must persist when the hub navigates to a dashboard or to the
  advanced Explore builder). Mirror any additional conventions from the
  Channel Center file's header comment.

### 4.3 Hooks (`hooks.py`)
Clone the coverage-module pattern:
- `ROLE_GATES = {"Analytics": ["Owner", "Operations Manager", "Branch Manager", "Accountant"]}`
  → `apply_role_gates(env)` writes `role_ids` on `item_analytics_hub` by
  role-NAME lookup, skipping missing names, idempotent.
- `grant_creator_group(env)`: for each internal active user whose
  `access_role_id.name` is in the gated list, ADD (4-link, never 6-set)
  `biz_bi.group_bi_creator`. Idempotent; never removes anyone; users
  without `access_role_id` untouched. (Field name: verify on `res.users` —
  the coverage hooks / access_roles module show the exact field.)
- `post_init_hook(env)` calls both; the migration script calls both (so a
  later `-u` re-applies after role edits).

### 4.4 Client action (`views/bi_hub_actions.xml`)
`ir.actions.client` id `action_bi_hub`, name "Analytics", tag
`biz_bi.hub`. No menuitem (CMS sidebar is the entry).

### 4.5 Server payload (`models/bi_workspace.py`)
`_inherit = "bi.workspace"`, new method `get_hub_data(self)` — ONE RPC for
the whole landing:
```
{
  "workspaces": [ ...get_home_data()'s entries, each + "dashboards":
                  [{id, name, description}] COMPLETE list (no limit),
                  grouped from one search_read ordered by name... ],
  "recents":    bi.audit.log.get_recents(),
  "is_creator": ..., "is_modeler": ..., "is_admin": ...,   # from get_home_data
  "ai_available": <bi.ai availability>,
}
```
Reuse `get_home_data()` internally — do not duplicate its workspace logic.
Plain `search_read` as the current user so record rules apply. No sudo
anywhere in this module.

### 4.6 Hub component (`static/src/components/hub/`)
`hub_action.js` (+ `hub_templates.xml`, `hub.scss`), registered as action
`biz_bi.hub`. Structure:

- **Header row**: title "Analytics" + subtitle; right-aligned primary
  button `＋ Create Report` shown only when `is_creator` → Phase 1:
  `doAction({tag: "biz_bi.explore"})`.
- **Search**: a single input, client-side filter-as-you-type over
  dashboard names/descriptions across all workspaces. While a query is
  active, render one flat "Results" card list instead of the workspace
  grid; empty query restores the grid. No RPC on keystroke.
- **Recents strip** ("Continue where you left off"): horizontal chip/cards
  from `recents`, hidden when empty. Click → `openDashboard(id)`.
- **Workspace grid**: one card per workspace — left mono color bar
  (map biz color index → flat token color), an inline-SVG icon rendered
  from a small built-in map of lucide names actually used
  (`stethoscope`, `credit-card`, `target`, `bar-chart` default) filled
  with `currentColor` (this is the in-app SVG convention; do NOT use
  font-awesome inside the hub body), name, description, counts, and the
  full dashboard list as rows. Row click → `openDashboard(id)`.
  Per-workspace empty state: "No dashboards yet" + (creator only) a
  "Create one" link → same CTA target.
- `openDashboard(id)` → `doAction({tag:"biz_bi.dashboard",
  params:{dashboard_id: id}}, {clearBreadcrumbs: true})`.
- **Access fallback**: wrap the `get_hub_data` call; on AccessError render
  a friendly empty state ("Analytics access has not been set up for your
  account yet") instead of crashing — an access_roles administrator sees
  every sidebar item but may lack BI groups.
- **Loading**: skeleton placeholders, not a spinner-only page.
- All user-visible strings through `_t(...)`; vi translations in
  `i18n/vi.po`.

Styling: scss namespaced under `.bi-hub`; flat mono colors, generous
whitespace, card grid responsive (CSS grid, `minmax`), no gradients, no
`overflow` on card ancestors that could clip future dropdowns. Match the
CMS look (white cards, subtle borders, the dark-blue accent) — read
`addons/biz_bi/static/src/scss/biz_bi.scss:674-740` (old Home styles) as a
starting reference but this page should look cleaner and calmer.

## 5. Tests (`tests/test_hub.py`, tag `post_install`)

Fixtures: create 2 `access.role` rows in-test (names "Operations Manager",
"Nurse"), users bound to each, a restricted workspace (member-scoped) and
an open one, dashboards in both.

1. `test_hub_data_shape` — creator user calls `get_hub_data`; every
   workspace entry carries its complete `dashboards` list; with 45
   dashboards in one workspace all 45 are returned (kills the 40-limit
   defect); `recents`/`is_creator`/`ai_available` keys present.
2. `test_hub_data_respects_workspace_rules` — a user who is neither owner
   nor member of the restricted workspace sees neither it nor its
   dashboards; the open workspace still appears.
3. `test_role_gate_idempotent` — run `apply_role_gates` twice: same
   `role_ids`, no duplicates; a ROLE_GATES name with no matching
   `access.role` is skipped without raising.
4. `test_creator_group_grant` — "Operations Manager" user gains
   `group_bi_creator` after `grant_creator_group`; "Nurse" user does not;
   second run adds nothing new and removes nothing.
5. `test_sidebar_wiring` — `cms.sidebar.item.get_match_keys()` output
   includes tags `biz_bi.hub`, `biz_bi.dashboard`, `biz_bi.explore`; the
   sidebar payload (`get_sidebar_data` as each user — read its exact
   signature) shows the ANALYTICS section to the gated-role user and hides
   it from the ungated one.

## 6. Deploy + report-back

- Deploy per conventions §2: db `vietuat`, `-u biz_bi_cms`, service
  `odoo-server`, addons path `/odoo/odoo-server/addons/`. Quote the
  `odoo.tests.result` line verbatim.
- Browser evidence pack (DoD item 5) →
  `docs/strategy/reports/analytics-hub-phase1-evidence/`: real path =
  login → Viet Uc CMS shell → ANALYTICS section visible → click
  Analytics → hub renders (screenshot: recents, workspace grid) → click a
  dashboard → dashboard opens WITH the CMS sidebar still present
  (screenshot proving chrome persistence) → back → `＋ Create Report` →
  Explore opens with chrome intact. Console log per screen. Also
  screenshot an ungated user OR quote the `get_sidebar_data` result
  proving the section is hidden for a Nurse-role user.
- Report → `docs/strategy/reports/analytics-hub-phase1-report.md`
  (committed): file list, deviations, verbatim test results, the exact
  `bi.ai` availability method you found, the exact `res.users` role field
  name, sidebar section sequences chosen, and any new gotcha.

## Kickoff line

Implement the phase specified in docs/strategy/handovers/analytics-hub-phase1.md.
