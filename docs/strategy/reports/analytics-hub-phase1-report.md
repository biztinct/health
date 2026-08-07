# Phase AH-1 implementation report — `biz_bi_cms` Analytics Hub

Handover: `docs/strategy/handovers/analytics-hub-phase1.md`
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md`
Deployed to **vietuat** (`care.biztinct.com`), branch `19.0`.

---

## 1. What was built

A new glue module **`addons/biz_bi_cms`** (nothing outside it was touched):

| File | Lines | What it is |
|---|---:|---|
| `__manifest__.py` | 66 | *Analytics Hub (CMS)*, `19.0.1.0.0`, depends `biz_bi` + `health_cms_sidebar`, `post_init_hook`, `web.assets_backend` globs over `static/src/**/*.{scss,js,xml}` |
| `__init__.py` | 3 | models + the hook |
| `hooks.py` | 121 | `ANALYTICS_ROLE_NAMES`, `ROLE_GATES`, `apply_role_gates(env)`, `grant_creator_group(env)`, `post_init_hook(env)` |
| `migrations/19.0.1.0.0/post-apply-role-gates.py` | 18 | re-runs both, so an upgrade converges with a fresh install |
| `data/cms_sidebar_analytics.xml` | 59 | the **ANALYTICS** section (seq 37) + the **Analytics** leaf |
| `views/bi_hub_actions.xml` | 12 | `ir.actions.client` `action_bi_hub` → tag `biz_bi.hub`, no menuitem |
| `models/bi_workspace.py` | 77 | `get_hub_data()` — one RPC for the whole landing |
| `models/bi_ai.py` | 38 | `is_available()` answers `False` on `AccessError` instead of raising (deviation **D4**) |
| `static/src/components/hub/hub_action.js` | 216 | the `biz_bi.hub` OWL client action |
| `static/src/components/hub/hub_templates.xml` | 153 | its QWeb template |
| `static/src/components/hub/hub.scss` | 432 | flat-mono stylesheet namespaced under `.bi-hub` |
| `tests/test_hub.py` | 311 | six tests, `post_install` |
| `i18n/vi.po` | 143 | 17 entries, every one with `#. module:` + a `#:` occurrence |

Docs committed alongside: this report and
`docs/strategy/reports/analytics-hub-phase1-evidence/` (README + 9
screenshots + 4 server-side evidence files).

### The three deliverables

1. **Sidebar** — `cms.sidebar.section` `analytics` (name `ANALYTICS`,
   `technical_key` `analytics`, sequence **37**, icon `fa fa-area-chart`) and
   a single root leaf `item_analytics_hub` (name `Analytics`, sequence 10,
   icon `fa fa-bar-chart`, `parent_id eval="False"`, no `match_models`),
   gated in python to **Owner / Operations Manager / Branch Manager /
   Accountant**. `match_action_tags = biz_bi.hub,biz_bi.dashboard,biz_bi.explore`
   so the CMS chrome survives everywhere the hub navigates — zero JS edits
   were needed, the `cms_sidebar_keys` service picks the keys up at boot.
2. **Permission** — `grant_creator_group()` links `biz_bi.group_bi_creator`
   to every active, non-share user whose `access_role_id.name` is one of the
   four. It measured 9 users on vietuat (was: **2 accounts held any BI group
   at all**, both BI administrators). Additive only: `Command.link`, never
   `Command.set`, skips anyone who already reaches the group through the
   implication closure (`all_group_ids`, §5.114), never removes anything,
   never touches a user with no role.
3. **Hub** — the `biz_bi.hub` client action: header + creator-gated
   `＋ Create Report`, an instant client-side search, a
   *Continue where you left off* recents strip (hidden when empty), and a
   responsive workspace grid with an inline-SVG lucide icon, a flat mono
   left colour bar, counts, and **every** dashboard the user may see listed
   as a clickable row. Skeleton loading, and a friendly empty state instead
   of a crash when the user has no BI access.

### Old-Home defects deliberately not inherited

| Defect | Now |
|---|---|
| three sequential awaited RPCs | **one** `get_hub_data()` |
| `searchRead("bi.dashboard", [], limit: 40)` — unscoped and capped, so workspaces past the 40th dashboard read "No dashboards yet" | one `search_read` scoped to the visible workspaces, **no limit**; `test_hub_data_shape` puts 45 dashboards in one workspace and asserts all 45 return |
| `window.prompt()` | gone (no "New dashboard" button in Phase 1 by design) |
| `workspace.icon` never rendered | rendered from a built-in lucide map |

---

## 2. Deviations from the handover, with reasoning

**D1 — `ROLE_GATES` is keyed by the leaf's xml-id, not by its display name.**
§4.3 writes `ROLE_GATES = {"Analytics": [...]}`. `apply_role_gates` resolves
the leaf with `env.ref('biz_bi_cms.<key>')`, exactly as the
`health_cms_coverage` precedent the handover told me to clone does, so the
key must be `item_analytics_hub`. Same structure, same behaviour, one entry.

**D2 — ANALYTICS section sequence is 37, not "directly after FINANCE".**
§4.2 said "read the actual numbers". They are: CRM 10, OPERATIONS MANAGER 20,
FINANCE 30, **CLINICAL 32, INTEROP & COMPLIANCE 35**, ADMIN 40 — two sections
the handover's prose did not enumerate already sit between FINANCE and ADMIN.
37 is the only slot that is both after FINANCE and before ADMIN without
renumbering anything that exists. Verified live in
`evidence/sidebar-gating.txt`.

**D3 — the workspace icons are stroked with `currentColor`, not filled.**
§4.6 says "filled with `currentColor`". Lucide icons are stroke-based
outlines; `fill`ing their path data produces blobs. They are rendered
`fill="none" stroke="currentColor"`, which is what "coloured by the current
text colour" means for this icon family. The intent (one colour, inherited,
no hardcoded hex inside the SVG) is preserved exactly.

**D4 — one additive file the handover did not ask for: `models/bi_ai.py`.**
Non-goal §2 forbids editing `biz_bi` core but allows "smallest additive
change + record the deviation" when a seam is genuinely missing. Driving the
phase's own CTA (evidence step 7) showed the Explore builder greeting a
creator-only user with a modal: *"You are not allowed to access 'BI AI
Provider' (bi.ai.provider) records."* — `explore_action.js` fires
`bi.ai.is_available()` in `onWillStart` with no `.catch`, and that model's
ACL starts at `group_bi_modeler`. The defect is pre-existing in `biz_bi` and
had never fired because only two accounts held a BI group and both were
administrators; **this phase is what makes it reachable**, for nine users, on
the button the phase exists to add. `biz_bi_cms` therefore `_inherit`s
`bi.ai` and returns `False` on `AccessError`. No ACL widened, no group
granted, no biz_bi file edited, modelers and admins unchanged, only
`AccessError` caught (§5.47). Screenshots 07/08 are the before, 09 the after;
`test_ai_probe_degrades_for_a_creator` pins it. **A reviewer may prefer this
to move into `biz_bi` proper as a `.catch()` on the JS side — flagging it
rather than deciding it.**

**D5 (minor, in-module) — the hub's search input carries `id`/`name`.**
Not in the spec; without them Chrome adds an accessibility `[issue]` to the
console on every hub load, and the DoD asks for a clean console.

Everything else follows §4 literally: model and method names, the payload
keys, the action tag, the sidebar field values, the CTA target
(`doAction({tag: "biz_bi.explore"})` with no options, matching §4.6's
asymmetry with `openDashboard`'s `clearBreadcrumbs: true`), the non-goals
(no wizard, no ACLs, no groups, no record rules, no catchment scoping, no
"New dashboard" button, no TV/sharing/workspace management), and "no `sudo()`
anywhere in this module" — the only `sudo()` calls are in `hooks.py`, which
runs as SUPERUSER from the install hook and the migration.

---

## 3. Answers the handover asked for

| Question | Answer |
|---|---|
| exact `bi.ai` availability method | **`env['bi.ai'].is_available()`** — `@api.model` on the `bi.ai` AbstractModel, `biz_bi/models/bi_ai.py:262-265`; returns `bool(provider and provider._is_usable())` over `bi.ai.provider.get_default()`. On vietuat it returns `False` for a creator (ACL) and there is no usable provider configured anyway. |
| exact `res.users` role field | **`access_role_id`** (`access_roles/models/res_users.py:30`, `Many2one('access.role')`). The groups field is `group_ids`, not `groups_id` (§5.41/§5.114). |
| sidebar section sequences chosen | ANALYTICS = **37**. Live table: crm 10, ops 20, finance 30, clinical 32, interop 35, **analytics 37**, admin 40. |

---

## 4. Test results — verbatim

Final deploy, `/tmp/ahp1/deploy4.log`, `EXIT:0`:

```
2026-08-07 02:47:42,311 2398894 INFO vietuat odoo.tests.stats: biz_bi_cms: 8 tests 2.59s 1741 queries 
2026-08-07 02:47:42,311 2398894 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 6 tests when loading database 'vietuat' 
```

The six that ran (§5.83 — a count of failures is not evidence, a count of
*executed* methods is; `grep -ao "Starting Test.*\.test_"`):

```
Starting TestAnalyticsHub.test_ai_probe_degrades_for_a_creator
Starting TestAnalyticsHub.test_creator_group_grant
Starting TestAnalyticsHub.test_hub_data_respects_workspace_rules
Starting TestAnalyticsHub.test_hub_data_shape
Starting TestAnalyticsHub.test_role_gate_idempotent
Starting TestAnalyticsHub.test_sidebar_wiring
```

`grep -ac "FAIL:\|ERROR:\|CRITICAL"` over the whole deploy log: **0**.
Server after the final restart: **`HTTP:200`** on `localhost:8069/web/login`
(and re-confirmed after the QA cleanup, `evidence/qa-fixture-cleanup.txt`).

Mapping to handover §5: 1 → `test_hub_data_shape` (45 dashboards, kills the
40-cap), 2 → `test_hub_data_respects_workspace_rules`, 3 →
`test_role_gate_idempotent`, 4 → `test_creator_group_grant`, 5 →
`test_sidebar_wiring`; plus `test_ai_probe_degrades_for_a_creator` for D4.

### i18n

`i18n/vi.po`, 17 entries, filename is a language code Odoo actually opens
(§5.84). Verified three ways rather than assumed:

* the `health_base` G1/G1b/G1c shape rules replicated over the new file —
  every entry has `#. module: biz_bi_cms`, every entry has a `#:`
  occurrence, and every `#. odoo-javascript` marker is paired with a
  `#: code:addons/biz_bi_cms/…` occurrence: **clean**;
* live loader: `code_translations.get_web_translations('biz_bi_cms',
  'vi_VN')` → **16 messages** (an empty dict is §5.67's symptom);
* live model terms through the ORM: the sidebar item reads **`Phân tích`**,
  the section **`PHÂN TÍCH`** and the client action **`Phân tích`** under
  `lang='vi_VN'`.

The module ships **no** python `_()` strings, so `test_g2` has nothing to
assert about it, and no new fields, so `test_g2b` has no field label to
check. `TestI18nCatalogueShape` / `TestI18nCatalogueLoads` themselves were
not re-executed on the server: Odoo only collects tests for modules in the
run's update set, and pulling them in needs `-u health_base`, whose upgrade
cascade is far riskier than the check is worth. The replication above covers
G1/G1b/G1c exactly and the live loader call covers G2 for this module.

`health_theme`'s `TestDropdownTrapGuard` does not scan `hub.scss` (it skips
glob asset entries) — the file has no `contain:`/`transform:`/`filter:` and
no CSS `min()`/`max()`/`clamp()` (§5.68), and `sass.compile()` was run
against it **on the server** before every deploy.

---

## 5. Browser evidence

`docs/strategy/reports/analytics-hub-phase1-evidence/` — see its `README.md`
for the click-by-click path. It starts at `https://care.biztinct.com/web/login`
as a real Operations-Manager-role persona and reaches the hub only through
the CMS sidebar; there is no deep link anywhere in it. It contains the nine
screenshots, the full console log per screen (zero errors, zero warnings; the
one `[issue]` is a pre-existing accessibility advisory already present on the
shell before the hub opens), the `bi.audit.log` rows the drive created **by
id**, `get_hub_data()`'s exact payload for that persona, `get_sidebar_data()`
run as four real personas (OM sees ANALYTICS, two Nurses and CRM do not), and
the fresh-cursor proof that both throwaway users are gone (§5.34/§6).

---

## 6. Deferred / not done

* **Phase 2** as scoped by the handover: the guided 3-step report builder.
  The CTA currently opens the existing Explore builder, and `ai_available`
  is already in the payload and in component state waiting for it.
* The **migration script never runs on this deployment yet.** §4.1 specified
  `migrations/19.0.1.0.0/` and version `19.0.1.0.0`; Odoo runs migration
  scripts only when the *installed* version is lower than the module
  version, so the directory will first execute on the phase that bumps the
  version. `post_init_hook` covered the install. This matters: it is why a
  user created **after** the install does not have the BI group — measured
  live, the QA persona came back `HAS_CREATOR: False` until
  `grant_creator_group(env)` was re-run by hand. **Recommendation for Phase 2:
  bump the manifest to `19.0.1.1.0` and move the script to
  `migrations/19.0.1.1.0/`, and consider making the grant a cron or an
  `access.role`-write hook so new hires get it automatically.**
* The `biz_bi` Explore JS still has the unguarded `bi.ai.is_available()` call
  (D4 neutralises it from the server side; the JS `.catch()` belongs in
  `biz_bi` and was out of sanction).
* `health_base`'s repo-wide i18n suite and `health_theme`'s dropdown guard
  were not re-executed on the server (reasoning in §4).

---

## 7. New gotcha discovered — FOR THE CONVENTIONS LEDGER §5

Flagging explicitly per §5.108 ("a gotcha that lives only in a phase report
does not exist for the next phase"). Proposed entry:

> **§5.127 — a phase that GRANTS a group inherits every latent ACL bug on
> every screen that group can now reach, and the ones that bite are in
> other modules' JS.** AH-1's whole job was to give nine business users
> `biz_bi.group_bi_creator`. The module itself was clean; the first thing
> the new audience saw on the phase's own CTA was
> *"You are not allowed to access 'BI AI Provider' (bi.ai.provider)
> records."* — `biz_bi`'s `explore_action.js` fires
> `orm.call("bi.ai", "is_available")` in `onWillStart` **without awaiting
> it and without a `.catch`**, so the rejection reaches the global error
> handler as a modal, and `bi.ai.provider`'s ACL starts one rung higher
> (`group_bi_modeler`) than the group being granted. The bug had existed
> since biz_bi shipped and had never once fired, because the only two
> accounts on the database holding any BI group were both BI
> *administrators* — a population of two, both privileged, is a test
> fixture, not a test. Three rules: (a) when a phase grants a group,
> enumerate the screens that group newly unlocks and DRIVE them as a member
> of exactly that group — not as admin, and not as the next rung up (this
> is §5.102's blind spot moved from API tokens to the UI); (b) a
> capability *probe* ("is feature X available to me?") must never be able
> to raise — it has an honest answer for every user, and for someone who
> cannot read the configuration table the answer is "no"; (c) a fire-and-
> forget `orm.call(...).then(...)` in `onWillStart` has no error path at
> all, so an ACL failure in it becomes a modal on a screen that otherwise
> works perfectly — grep for `.then(` without `.catch(` when auditing a
> newly-reachable component. Fixed additively from the granting module by
> `_inherit`ing the model and catching `AccessError` (biz_bi_cms/models/
> bi_ai.py); the caller-side `.catch()` still belongs in biz_bi.

Two smaller observations, worth a line each if the ledger owner wants them:

* **`bi.audit.log` cannot be deleted, and that makes a QA user
  undeletable.** Its `unlink()` raises (correctly — append-only), and
  `user_id` is a `required=True` Many2one, which Odoo materialises as
  `ON DELETE RESTRICT`. So a throwaway QA persona that so much as *opens a
  dashboard* can no longer be removed through the ORM, and §5.34's
  "delete your fixtures" needs a raw `DELETE` scoped to that uid. Worth
  knowing before creating a QA persona on any module with an append-only
  log keyed on the user.
* **A `.po` occurrence line of the `model:<model>,name:<module>.<xmlid>`
  form works for arbitrary business models, not just core ones** —
  `model:cms.sidebar.item,name:biz_bi_cms.item_analytics_hub` correctly
  lands `Phân tích` in the jsonb column at upgrade. §5.85 lists the
  occurrence *types*; this is the confirmation that the model half is not
  limited to `ir.*`.

---

## 8. Commit

Branch `19.0`, message `feat(analytics): CMS Analytics Hub (biz_bi_cms)`.
