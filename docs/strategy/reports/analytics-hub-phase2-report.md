# Phase AH-2 implementation report — the guided Create Report wizard

Handover: `docs/strategy/handovers/analytics-hub-phase2.md`
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md`
Deployed to **vietuat** (`care.biztinct.com`), branch `19.0`.
Module: **`addons/biz_bi_cms`** `19.0.1.0.0` → **`19.0.1.1.0`**.

---

## 1. What was built

Everything is inside `addons/biz_bi_cms/**`, plus the sanctioned §5 ledger
append and this report + its evidence pack. Nothing else in the repo was
touched (the working tree carries unrelated unstaged changes from another
session; the commit is path-scoped).

| File | Δ | What it is |
|---|---|---|
| `static/src/components/wizard/report_wizard.js` | **new**, 620 | the `ReportWizard` OWL component — three steps, the AI ask, the recommender, the preview query, the save flow |
| `static/src/components/wizard/report_wizard.xml` | **new**, 300 | its QWeb template |
| `static/src/components/wizard/report_wizard.scss` | **new**, 500 | flat-mono stylesheet namespaced under `.bi-wizard` |
| `models/res_users.py` | **new**, 66 | auto-grant `group_bi_creator` when a gated `access_role_id` is set (create **or** write) |
| `migrations/19.0.1.1.0/post-apply-role-gates.py` | **new**, 33 | the migration that actually runs (the 1.0.0 one never did) |
| `tests/test_wizard_flow.py` | **new**, 300 | `TestReportWizard`, 7 methods, `post_install` |
| `hooks.py` | +40/−22 | split into `gated_role_ids()` / `grant_creator_to_users()` / `grant_creator_group()` so the sweep and the per-record hook share one role list |
| `static/src/components/hub/hub_action.js` | +14/−9 | `state.wizardOpen`, `createReport()` opens the wizard, `closeWizard()` |
| `static/src/components/hub/hub_templates.xml` | +7 | mounts `<ReportWizard t-if="state.wizardOpen" onClose.bind="closeWizard"/>` |
| `tests/test_hub.py` | +12/−2 | T4 adjusted for the new auto-grant (see D3) |
| `tests/__init__.py` | +1 | registers the new suite |
| `models/__init__.py` | +1 | registers `res_users` |
| `__manifest__.py` | +9/−1 | version `19.0.1.1.0`, description paragraph for the wizard |
| `i18n/vi.po` | 17 → **79** entries | every new user-visible string |

Docs: this report and
`docs/strategy/reports/analytics-hub-phase2-evidence/` (README + 12
screenshots + 4 evidence text files), plus **§5.127–§5.130** appended to
`HANDOVER-CONVENTIONS.md`.

### The wizard

A full-viewport overlay mounted by the hub, `props = {onClose}`:

1. **Choose data** — cards for every published dataset, `Certified` badge,
   one dataset auto-advances, a click loads `get_builder_metadata` and
   precomputes measures / dimensions / date fields.
2. **Build** — an *Ask in your own words* box when `bi.ai.is_available()`
   (above an *OR BUILD IT YOURSELF* divider), and always the four pickers:
   Measure (sets `agg = default_agg || "sum"`), Break it down by (+ grain
   chips for a date), Split by, Date range (chip row from `RELATIVE_RANGES`
   + *All time*). The chart gallery re-recommends on every change via
   `recommendChartType` unless the user picked a type, and every
   incompatible type is `disabled` with `checkCompatibility`'s reason as its
   tooltip.
3. **Preview & save** — a real `ChartRenderer` / `KpiCard` / `DataTable` /
   `PivotTable` over a 400 ms-debounced `bi_data.query`, a name pre-filled
   *"&lt;Measure&gt; by &lt;Group by&gt;"* (or the AI's own title), a radio list of
   writable dashboards plus *New dashboard*, and one **Save report** button:
   `orm.create("bi.chart")` (destructured), create-or-pick the dashboard,
   `add_chart`, notification, close, navigate to the dashboard.

*Open in advanced builder* on steps 2–3 hands the same state to Explore
(`params: {dataset_id}`, or `{chart_id}` once saved). The config it writes
is byte-compatible with `explore_action.js:466`'s `buildConfigJson()`, so
the hand-off is lossless in both directions and nothing downstream knows a
wizard exists.

### The three carry-overs

* **Version + migration** — manifest at `19.0.1.1.0`, script in
  `migrations/19.0.1.1.0/`. It ran, verbatim from `/tmp/ahp2/deploy1.log`:
  `module biz_bi_cms: Running migration [19.0.1.1.0>] post-apply-role-gates`
  → `1 leaf(s) gated, 0 user(s) granted the BI creator group` (0 because
  all nine already held it from AH-1's install hook — convergence, which is
  what `test_06` asserts).
* **Auto-grant** — `models/res_users.py` overrides `create` and `write`;
  when `access_role_id` lands on one of `hooks.ANALYTICS_ROLE_NAMES` the
  user gets `Command.link(group_bi_creator)`. **Add-only** (losing the role
  never revokes — same reasoning `access_roles` gives for not un-granting
  role groups), idempotent through the `all_group_ids` closure check
  (§5.114), guarded so a deployment without `access_roles` can still create
  users. Proven live, not just in tests: the QA persona was created after
  the module was installed and came back `HAS_CREATOR: True`, where Phase 1
  measured `False`.
* **Ledger** — §5.127 (granted-group latent ACL), §5.128 (append-only log
  makes a QA persona undeletable), §5.129 (`model:` occurrences work for
  business models) appended, plus §5.130 which AH-2 found itself.

---

## 2. Deviations from the handover, with reasoning

**D1 — three extra keys in the wizard's state.** §4.1 lists the state; I
added `aiAvailable`, `chartId` and `nameTouched`. `aiAvailable` is required
because props are pinned to `{onClose}`, so the wizard must probe
`bi.ai.is_available()` itself rather than read the hub's copy. `chartId` is
required by §4.1's own last sentence ("if the chart got created but
`add_chart` failed, keep the chartId so retry doesn't duplicate") — the
same guard now also holds the dashboard id for the same reason.
`nameTouched` stops `afterChange()` re-deriving a title the user typed when
they go Back and change a picker. No interface changed.

**D2 — the AI probe is `await`ed, and there is no separate `ai_available`
prop.** §3 says the wizard "can call it without a guard". It is awaited in
`onWillStart` rather than fired and forgotten, because a
fire-and-forget `orm.call(...).then(...)` in `onWillStart` is precisely the
shape §5.127(c) is about.

**D3 — `tests/test_hub.py::test_creator_group_grant` was edited (in-module,
forced).** This is the §5.62 class: the new per-record auto-grant means a
user created *with* a gated role already holds the group, so the pre-
existing fixture guard `assertNotIn(creator_group, gated_user.all_group_ids)`
was correct before and false after. The test now asserts the new guarantee
(the group IS there at create), strips the direct link, and *then* measures
the backfill sweep — so what the test is named for still gets tested.
`test_05_auto_grant_on_role_assign` covers the hook proper.

**D4 — one extra test, `test_01b_relative_range_vocabulary_is_shared`.**
Not in §5's list. The wizard's date chips come from `biz_bi`'s JS
`RELATIVE_RANGES` while the engine has its own python table; a value in one
and not the other is a chip that raises `UserError` on click. Six lines,
reads the JS file, asserts the JS keys are a subset of
`bi_query_engine.RELATIVE_RANGES`.

**D5 — grain chips show words, not the engine's keys.** §4.1 says "grain
chips, default month". Explore renders the raw `year/quarter/month/week/day`
in a `<select>`; in a wizard aimed at non-technical creators they render as
*Year / Quarter / Month / Week / Day* through `_t`. The values sent to the
engine are unchanged.

**D6 — a footer hint on step 1.** Step 1 has no Back and no Preview, so the
footer bar drew empty, which reads as a rendering bug. It now says *Pick a
dataset to continue*. Cosmetic, one string, translated.

**D7 — the escape hatch calls `onClose()` before `doAction`, not after.**
§4.1 writes "→ doAction(…), then `onClose()`". Closing first means the last
write to `this.state` happens while the component is still mounted; the
same ordering is used on the save path. Behaviourally identical, verified
live (evidence step 10).

Everything else follows §4 literally: the component/file names, the state
machine, the picker semantics, the `kpi`-needs-no-group-by exception, the
gallery subset, the 400 ms debounce, the `rendererKind` switch, the
`buildConfigJson()` shape, the `sort: [{ref:"m0",dir:"desc"}]`-except-line
default, `limit: 500`, the AccessError notification, and every binding
non-goal in §2 (no drag-and-drop, no multi-measure, no filter builder
beyond the one date-range chip row, no chart editing, no `compose_report`,
no new server models, no edits to `biz_bi`, and the flagged
`explore_action.js` `.catch()` is still open).

---

## 3. Answers the handover asked for

### The exact date-range `{op, value}` format

```json
{"field_id": <bi.field id>, "op": "relative", "value": "<range key>"}
```

`<range key>` is a key of `RELATIVE_RANGES`
(`biz_bi/static/src/core/range_labels.js`), which the engine mirrors 1:1 in
`biz_bi/models/bi_query_engine.py:45-75`:
`today, yesterday, last_7_days, last_30_days, this_week, this_month,
last_month, this_quarter, last_6_months, last_12_months, this_year,
last_year`. It goes into `config_json.filters[0]` and, unchanged, into the
engine request's `filters`.

Verbatim from the row the browser drive created (`bi_chart` id 49):

```json
"filters": [{"op": "relative", "value": "last_12_months", "field_id": 593}]
```

and, verbatim from the live AI response the wizard materialised
(`bi_ai_log` id 27): `{"op": "relative", "value": "last_6_months",
"field_id": 593}`.

### Was AI live on vietuat?

**Yes, and the answer has two halves.** `bi.ai.provider` id 2 (OpenAI /
`gpt-4o-mini`) is active, `is_default`, and carries an API key, so
`bi.ai.is_available()` returns `True` for an administrator and a real
`nlq_chart` call from the wizard reached OpenAI and came back in 4 s
(`bi_ai_log` id 27, evidence steps 11–13).

But `bi.ai.provider`'s ACL starts at `biz_bi.group_bi_modeler`, so for the
plain **creator** the wizard exists for, the probe honestly answers `False`
(AH-1's `models/bi_ai.py` turns the AccessError into a "no") and the AI box
is **hidden**. Both states are in the evidence pack. Widening that ACL — or
letting a creator use AI at all — is a `biz_bi` product decision and out of
this phase's sanction; flagged, not decided.

---

## 4. Test results — verbatim

Final deploy, `/tmp/ahp2/deploy3.log`, `EXIT:0`:

```
2026-08-07 03:35:15,402 2408149 INFO vietuat odoo.tests.stats: biz_bi_cms: 17 tests 4.69s 3510 queries 
2026-08-07 03:35:15,402 2408149 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 13 tests when loading database 'vietuat' 
```

The thirteen that ran (§5.83/§5.90 — a count of failures is not evidence, a
count of *executed* methods is):

```
Starting TestAnalyticsHub.test_ai_probe_degrades_for_a_creator
Starting TestAnalyticsHub.test_creator_group_grant
Starting TestAnalyticsHub.test_hub_data_respects_workspace_rules
Starting TestAnalyticsHub.test_hub_data_shape
Starting TestAnalyticsHub.test_role_gate_idempotent
Starting TestAnalyticsHub.test_sidebar_wiring
Starting TestReportWizard.test_01_wizard_config_roundtrip
Starting TestReportWizard.test_01b_relative_range_vocabulary_is_shared
Starting TestReportWizard.test_02_wizard_save_flow
Starting TestReportWizard.test_03_creator_cannot_add_to_foreign_dashboard
Starting TestReportWizard.test_04_nlq_unavailable_is_clean
Starting TestReportWizard.test_05_auto_grant_on_role_assign
Starting TestReportWizard.test_06_migration_reruns_gates
```

`grep -ac "FAIL:\|ERROR:\|CRITICAL"` over the whole deploy log: **0**.
Server after the final restart: listener present on 8069 and **`HTTP:200`**
on `localhost:8069/web/login` (re-confirmed after the QA cleanup).
Deployed files were byte-compared against the repo afterwards: identical.

Mapping to handover §5: 1 → `test_01`, 2 → `test_02`, 3 → `test_03`,
4 → `test_04`, 5 → `test_05`, 6 → `test_06`; plus `test_01b` (D4).

### i18n

`i18n/vi.po`, **79** entries (was 17), filename a language code Odoo
actually opens (§5.84). Verified three ways rather than assumed:

* shape — a script over every non-header block: all 79 carry
  `#. module: biz_bi_cms`, all 79 carry a `#:` occurrence, and every
  `#. odoo-javascript` marker is paired with a
  `#: code:addons/biz_bi_cms/…` occurrence (§5.29 / §5.58 / §5.67);
* content — every msgid was matched back against the source file its
  occurrence names (XML entities decoded): **0 unmatched**, so no entry is
  a typo that would translate nothing;
* live loader on the server —
  `code_translations.get_web_translations('biz_bi_cms', 'vi_VN')['messages']`
  → **78** messages (the 79th is the `ANALYTICS` section label, a model
  term with no code occurrence), spot-checked:
  `'Save report' → 'Lưu báo cáo'`,
  `'What do you want to look at?' → 'Bạn muốn xem dữ liệu nào?'`,
  `'Open in advanced builder' → 'Mở trong trình dựng nâng cao'`,
  `'— choose —' → '— chọn —'`. Model terms still land:
  the sidebar item reads `Phân tích` under `lang='vi_VN'`.

### Assets

`report_wizard.scss` compiles under the server's libsass
(`sass.compile(filename=…)` run on vietuat before every deploy), contains
no `contain:` / `transform` / `filter` on any field-bearing wrapper (§5.96)
and no CSS `min()` / `max()` / `clamp()` (§5.68). Verified on the real
bundle rather than assumed: `web.assets_backend` regenerates at **2.23 MB**
of CSS containing `.bi-wizard` **and** the known-good siblings `.bi-hub`,
`.bi-explore`, `.o_care_command`; the JS bundle (10.5 MB) contains
`components/wizard/report_wizard` and `biz_bi_cms.ReportWizard`.

### PWA

This phase touches no PWA asset, no app shell and no module that injects JS
into it, so conventions §3 does not apply and `health_pwa` was not bumped.

---

## 5. Browser evidence

`docs/strategy/reports/analytics-hub-phase2-evidence/` — see its
`README.md` for the click-by-click path. It starts at
`https://care.biztinct.com/web/login` as a real Operations-Manager persona
and reaches the wizard only through the CMS sidebar; there is no deep link
anywhere in it. Thirteen screenshots cover login → shell → hub → wizard
steps 1/2/3 → save → the new dashboard *with CMS chrome* → the recents
strip → the advanced-builder escape hatch → the AI box → a live AI ask →
the AI config materialised back into the ordinary pickers.

`console-log.txt` has the full console per screen: **zero errors, zero
warnings** everywhere; the one `[issue]` advisory is pre-existing and
*measured* (a DOM query proves the wizard contributes no form field without
`id`/`name`; the four on the Explore screen all belong to the CMS shell and
`biz_bi`). It also attributes the one 502 burst honestly: another session
stopped the Odoo service mid-drive for its own deploy, and the affected
step was re-driven afterwards.

`server-side-rows.txt` gives the created rows **by id** (chart 49,
dashboard 243, widget 41, ai-log 27) with the verbatim `config_json`.
`qa-fixture-cleanup.txt` is the fresh-cursor proof that all of it, and the
throwaway account, are gone (§5.34).

---

## 6. Deferred / not done

* **The `biz_bi` `.catch()` on `explore_action.js`'s `is_available()` call**
  — still open, deliberately (§2 forbids it). The server-side override
  neutralises it for every caller.
* **AI for creators.** A usable provider is configured, but
  `bi.ai.provider`'s ACL starts at `group_bi_modeler`, so the wizard's AI
  box never appears for the role this whole stream serves. Options are (a)
  a read-only ACL row for `group_bi_creator`, or (b) moving the probe
  behind a sudo'd `@api.model` in `biz_bi`. Both are `biz_bi` decisions.
* **A dashboard the user can read but not write** is still only discovered
  at Save time (the list comes from `searchRead`, which is read-scoped).
  The UI catches the AccessError and says so; pre-filtering it would need a
  writable-dashboards helper in `biz_bi`.
* `health_base`'s repo-wide i18n suite and `health_theme`'s dropdown guard
  were not re-executed on the server (they need `-u health_base` /
  `-u health_theme`, whose upgrade cascade is far riskier than the check;
  both were replicated locally instead — and the theme guard skips glob
  asset entries, which is how this module ships its stylesheets).

---

## 7. New gotchas discovered

All four are already **merged into `HANDOVER-CONVENTIONS.md` §5 in this
same commit** (§5.108: a gotcha that lives only in a phase report does not
exist for the next phase).

* **§5.127** — a phase that grants a group inherits every latent ACL bug on
  the screens that group newly reaches (carried over from AH-1's report,
  with the AH-2 corollary that an honest "no" from a capability probe can
  read as breakage in an evidence pack unless you say so).
* **§5.128** — an append-only log keyed on `res.users` makes a QA persona
  undeletable; plan the raw `DELETE` before you create the persona.
* **§5.129** — `.po` `model:<model>,name:<module>.<xmlid>` occurrences work
  for arbitrary business models, not just `ir.*`.
* **§5.130 (NEW, found by this phase)** — a second `odoo-bin` on the same
  database does not have to be yours, and its symptom is a serialization
  error in code that never touches the same table. AH-2's second test run
  died in `setUpClass` with *"could not serialize access due to concurrent
  update"* on a plain `INSERT INTO bi_source … RETURNING id` — a table with
  no unique index. The row's `model_id` FK takes a row-share lock on
  `ir_model`, and a concurrent `-u <module>` upgrade **started by another
  implementer's session** rewrites `ir_model`; under Odoo's REPEATABLE READ
  that is a serialization failure, not a lock wait, so nothing hangs and
  nothing names the cause. The same run then hit §5.122: `service
  odoo-server start` reported success, `systemctl is-active` said `active`,
  and there was no process and no listener — `/web/login` answered 500.
  Recovery was stop → `rm -f /var/run/odoo-server.pid` → start, confirmed
  on `ss -lntp | grep :8069`. Practical rules: re-check
  `pgrep -c -f '^python3 /odoo/odoo-server/odoo-bin'` immediately before
  `service stop` (§5.45 is a property of the database, not of your
  terminal); treat a serialization error in unrelated fixture code as
  evidence somebody else is deploying; and expect a concurrent browser QA
  session to show it as a 502 burst + `ConnectionLostError`, which you must
  flag rather than attribute to your own code.

---

## 8. Commit

Branch `19.0`, path-scoped to `addons/biz_bi_cms/`,
`docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/analytics-hub-phase2*` — the working tree carried
unrelated unstaged changes from another session throughout, and none of
them are in this commit.
