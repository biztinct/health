# Phase AH-3 implementation report — Analytics Hub polish + hardening

Handover: `docs/strategy/handovers/analytics-hub-phase3.md`
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.127–§5.130 read;
§5.131–§5.134 appended by this phase)
Deployed to **vietuat** (`care.biztinct.com`), branch `19.0`.
Modules: **`addons/biz_bi_cms`** (unchanged version `19.0.1.1.0`) and the two
sanctioned edits in **`addons/biz_bi`**.

---

## 1. What was built

| File | Δ | What changed |
|---|---|---|
| `biz_bi/models/bi_ai.py` | +10/−2 | **sanctioned edit 1** — both `get_default()` call sites resolve the provider through `.sudo()` |
| `biz_bi/static/src/components/explore/explore_action.js` | +11/−3 | **sanctioned edit 2** — `.catch()` on the `is_available` probe |
| `biz_bi_cms/models/bi_dashboard.py` | **new**, 39 | `get_wizard_targets()` — the writable-dashboard list, on `can_edit`'s own predicate |
| `biz_bi_cms/models/bi_workspace.py` | +40/−3 | `_hub_recents()` — prune dead/unreadable recents, and never let the strip take the landing down |
| `biz_bi_cms/models/__init__.py` | +1 | registers `bi_dashboard` |
| `biz_bi_cms/static/src/components/hub/hub_action.js` | +33 | `totalDashboards` / `isFirstRun` / `firstRunIcon` + the first-run glyph |
| `biz_bi_cms/static/src/components/hub/hub_templates.xml` | +26/−4 | the first-run card; the description line is always rendered (alignment) |
| `biz_bi_cms/static/src/components/hub/hub.scss` | +97/−14 | pixel cycles 1–2 + the focus ring |
| `biz_bi_cms/static/src/components/wizard/report_wizard.js` | +72/−8 | `get_wizard_targets` instead of the read-scoped list, `hasNoTargets`, Escape/`onKeydown`, Enter-to-save, pane focus on step change |
| `biz_bi_cms/static/src/components/wizard/report_wizard.xml` | +34/−9 | dataset-card restructure, no-targets hint, `t-ref`/`tabindex` panes, footer bar |
| `biz_bi_cms/static/src/components/wizard/report_wizard.scss` | +111/−15 | pixel cycles 1–3 + the focus ring |
| `biz_bi_cms/tests/test_ah3.py` | **new**, 232 | `TestAnalyticsHubAh3`, 5 methods |
| `biz_bi_cms/tests/test_hub.py` | +30/−8 | T6 re-pointed at the new semantics (deviation **D3**) |
| `biz_bi_cms/tests/test_wizard_flow.py` | +15/−7 | T4 likewise (deviation **D3**) |
| `biz_bi_cms/tests/__init__.py` | +1 | registers the new suite |
| `biz_bi_cms/i18n/vi.po` | 80 → **84** entries | the four new user-visible strings |
| `biz_bi_cms/__manifest__.py` | +8 | description paragraph for the three honest-empty behaviours |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | +74 | ledger §5.131–§5.134 |

Plus this report and `docs/strategy/reports/analytics-hub-phase3-evidence/`
(README + 25 screenshots + 4 evidence text files).

### The seven items of §1

1. **AI for creators** — done, and proven end-to-end in the browser by a user
   who cannot read one `bi.ai.provider` row (evidence 05–08,
   `security-probe.txt`). The AH-2 report's blocked screenshot is unblocked.
2. **The two `biz_bi` fixes** — done, verbatim to §4.1/§4.2.
3. **Writable-dashboard targeting** — `get_wizard_targets()`; step 3 offered
   **1 of 8** dashboards to the QA persona instead of all 8.
4. **Recents hygiene** — `_hub_recents()` prunes deleted/invisible ids and
   survives a refusal (a defect this phase found live — §5 below).
5. **First-run + degraded states** — the first-run card in both variants
   (evidence 21, 22), and the AH-1 AccessError fallback verified rather than
   rebuilt (evidence 20).
6. **Pixel pass** — three measured cycles, both languages, 1440 + 1024 (§6).
7. **i18n + evidence + reports** — loader-verified; 83 web messages.

---

## 2. Deviations from the handover, with reasoning

**D1 — §4.1 names `is_available()` and `_complete()` as "the two
`get_default()` call sites"; they are `is_available()` (`bi_ai.py:264`) and
`_complete_validated()` (`:401`).** `_complete()` is a method on
`bi.ai.provider` and never calls `get_default` — the handover's §3 prose says
so correctly two paragraphs earlier. I edited the two real call sites, which
is what the instruction means; nothing else in the file moved.

**D2 — no version bump, no migration directory.** §4.7 says to bump "only if
a data/schema step needs it (none is expected — say so if you skip it)". None
does: the phase adds no field, no data record and no seed, and the role gate
and the group grant already converged at 19.0.1.1.0. Bumping would also have
forced an edit to `test_06_migration_reruns_gates`, which hard-asserts
`latest_version == '19.0.1.1.0'` — churn with no benefit. The manifest stays
at `19.0.1.1.0`; only its description grew.

**D3 — two pre-existing biz_bi_cms tests were rewritten (forced, in-module).**
`TestAnalyticsHub.test_ai_probe_degrades_for_a_creator` and
`TestReportWizard.test_04_nlq_unavailable_is_clean` both asserted
`is_available() is False` for a creator. That was a statement about the ACL,
and §4.1's whole purpose is to stop the ACL answering that question — on a
database with a usable provider the honest answer is now `True`, and both
tests went red on the first run. This is the §5.62 class exactly. Neither
test was deleted or weakened: the first now asserts what actually mattered
(the probe RETURNS for a user who provably cannot read one provider row —
with an `assertRaises(AccessError)` fixture guard proving that — and the
landing survives whatever it returns), and additionally pins AH-1's
defensive override by patching `get_default` to raise. The second asserts
that with no provider the creator and an administrator now get the **same**
answer, which is the property §4.1 was for.

**D4 — one extra test beyond §5's list:
`test_ah3_04b_recents_accesserror_does_not_kill_the_hub`.** It pins the live
defect described in §5 of this report. Six lines of fixture, one patch.

**D5 — the hub keeps "No workspace is shared with you yet" as a state of its
own.** §4.5 says the grid "collapses to a single friendly first-run card"
when there are zero dashboards anywhere. Implemented as
`workspaces.length > 0 AND totalDashboards === 0`, because "no workspace is
shared with you" is an ACCESS answer and "no dashboards yet" is an EMPTINESS
answer, and telling a locked-out user that their first report starts here
would be a lie. Both states are in the evidence pack (20 vs 21/22).

**D6 — wizard step 1's empty-dataset copy was left as AH-2 shipped it.**
§4.5 suggests "No data sources are published yet"; the existing string is
*"No data is published for you yet"* with a second line telling the user what
to ask for. Same meaning, already translated, already tested. Rewording would
have churned the catalogue for nothing. (The state itself is not stageable on
this deployment without unpublishing six live datasets, so it is not in the
screenshots — flagged rather than faked.)

**D7 — an in-module fix the handover did not ask for:
`_hub_recents()` catches `AccessError`.** §4.4 asked only for a prune. The
prune alone does not help, because the refusal happens INSIDE
`bi.audit.log.get_recents` before anything comes back (details in §5). Kept
inside the sanctioned module, `AccessError` only (§5.47), never a blanket
`except`.

**D8 — `loadDashboards()` has a bare `catch` that empties the list.** §4.3
says "keep the AccessError catch as a fallback"; the save path's catch is
untouched and is that fallback. The extra one here means a refusal on the
TARGET LIST cannot take step 3 down — the user still gets "New dashboard",
which is the one option that always works for a creator.

Everything else follows §4 literally: the method name and payload shape of
`get_wizard_targets`, the `can_edit` predicate reused rather than reinvented,
the sudo scoped to the provider recordset with `self` untouched,
`dataset.check_access('read')` still first and still as the real user, no ACL
widened, no group granted, no record rule touched, no new server model, and
every §2 non-goal respected (no compose_report surface, no chart editing, no
dashboard management, no sharing, no TV mode, no workspace admin).

---

## 3. Security confirmation for §4.1 — what a creator's RPC can now reach

Measured from the QA creator's own authenticated browser session, not
inferred (`analytics-hub-phase3-evidence/security-probe.txt`):

| Call | Before AH-3 | After AH-3 |
|---|---|---|
| `bi.ai.is_available()` | `AccessError`, swallowed to `False` by AH-1's override | **`true`** — a plain boolean |
| `bi.ai.provider.search_read([], [...])` | `AccessError` | **`AccessError`** |
| `bi.ai.provider.search_count([])` | `AccessError` | **`AccessError`** |
| `bi.ai.log.search_read([], ['id'])` | `AccessError` | **`AccessError`** |
| `bi.ai.nlq_chart(dataset_id, prompt)` | refused at the provider layer | a validated chart config over **that dataset only** |

**No provider record and no key material is exposed.** The only value that
crosses the RPC boundary from the provider layer is the boolean, and — for
`nlq_chart` — a chart config whose every `field_id` has been validated
against the caller's own dataset by the same resolver human-built charts go
through. `_api_key()` is read inside `_complete_*` on a recordset that never
leaves the method; the endpoint, model name, temperature and encrypted key
are not in any response. The `ir.model.access` row for `bi.ai.provider` still
starts at `group_bi_modeler` and was not edited, which is why the three reads
above still refuse.

The sudo is scoped to `self.env['bi.ai.provider'].sudo()` — a recordset, not
`self` — so `bi.ai._log`'s bookkeeping is unchanged in every respect
(`test_ah3_02` proves the dataset check still runs as the real user, and that
it refuses **before** a provider is resolved, by asserting the mocked
completion was never reached).

One bit of disclosure is created deliberately and should be stated rather
than buried: any internal user who can call `bi.ai.is_available` now learns
whether an AI provider is configured on this database, where previously they
got a permission error. That is the intended trade (ledger §5.127b: a
capability probe must have an answer for everyone) and it is one bit, not a
row. If even that is unwanted, the fix is a group gate returning `False`
early — not re-introducing the raise.

---

## 4. Test results — verbatim

Full detail, including the pristine baseline, in
`analytics-hub-phase3-evidence/test-results.txt`.

### biz_bi_cms — `/tmp/ahp3/final_cms.log`, `EXIT:0`

```
2026-08-07 04:38:06,302 2413492 INFO vietuat odoo.tests.stats: biz_bi_cms: 24 tests 6.86s 4827 queries 
2026-08-07 04:38:06,303 2413492 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 18 tests when loading database 'vietuat' 
```

All 18 executed (13 pre-existing + 4 from handover §5 + `test_ah3_04b`);
`grep -ac "FAIL:\|ERROR:\|CRITICAL"` over the whole log: **0**. Mapping to
handover §5: 1 → `test_ah3_01_ai_available_for_creator`,
2 → `test_ah3_02_nlq_permission_shape`, 3 → `test_ah3_03_wizard_targets`,
4 → `test_ah3_04_recents_pruned`, 5 → the thirteen that were already there.

### biz_bi — `/tmp/ahp3/final_bi.log`, `EXIT:1`

```
2026-08-07 04:38:35,130 2413506 INFO vietuat odoo.tests.stats: biz_bi: 75 tests 10.07s 4930 queries 
2026-08-07 04:38:35,130 2413506 ERROR vietuat odoo.tests.result: 5 failed, 1 error(s) of 59 tests when loading database 'vietuat' 
```

**This is the one place the phase does not meet the stated Definition of
Done, and it is not caused by the phase.** The identical six failures occur
with the AH-3 edits reverted. Pristine baseline —
`/tmp/ahp3/baseline.log`, taken after copying `git show HEAD:` versions of
both edited files onto the server and grep-confirming the revert:

```
2026-08-07 04:07:31,130 2410420 INFO vietuat odoo.tests.stats: biz_bi: 75 tests 10.06s 4930 queries 
2026-08-07 04:07:31,131 2410420 ERROR vietuat odoo.tests.result: 5 failed, 1 error(s) of 59 tests when loading database 'vietuat' 
```

Same count, same six names, before and after:
`TestRls.test_column_mask_null` (error),
`TestPipeline.test_dataset_reads_clean_view`,
`TestQueryEngine.test_compare_request_runs`,
`TestRls.test_rls_users_never_share_cache`,
`TestRls.test_row_rule_filters_rows`,
`TestSnapshot.test_snapshot_xlsx_builds`.

Diagnosed (not fixed — fixing them means editing `biz_bi` test files, which
§2's sanction list forbids and which I judged is not an implementer's call to
make unilaterally on a **security** suite): they are the §5.50/§5.95 family.
`biz_bi/tests/common.py` builds its dataset over `res.partner` and expects its
own three rows; this database holds **77** partners with a latitude
(`sum = 897.31`). And `res_country.name` is jsonb —
`{"en_US": "Vietnam", "vi_VN": "Việt Nam"}` — so a row rule built from
`country_a.name` in the caller's language matches nothing in the silver view
and the restricted total returns `None` instead of `30.0`. Every one of the
three RLS failures fails **closed** (the restricted user sees nothing, never
the unrestricted 60.0), so none of them is evidence of a leak. Recommended as
a small follow-up ticket against `biz_bi`: scope the shared fixture's
measures to its own partner ids and match the country by `code`, not by
translated `name`.

### Server health

After the final restart: `ss -lntp | grep -c :8069` → **1**, and
`curl localhost:8069/web/login` → **HTTP:200**.

### i18n

`i18n/vi.po`, 80 → **84** entries. Verified three ways, none of them assumed:

* **shape** — all 84 blocks carry `#. module: biz_bi_cms`, all 84 carry a
  `#:` occurrence, and every `#. odoo-javascript` marker is paired with a
  `#: code:addons/biz_bi_cms/…` occurrence (§5.29 / §5.58 / §5.67);
* **content, both directions** — every msgid matches text in the source file
  its occurrence names (0 unmatched), and every translatable literal in the
  two QWeb templates and both component JS files is in the catalogue
  (0 missing);
* **live loader on the server** — `get_web_translations('biz_bi_cms',
  'vi_VN')['messages']` → **83** messages, with all four new strings
  resolving (`'Your first report starts here'` → `'Báo cáo đầu tiên của bạn
  bắt đầu từ đây'`, etc.), and the model terms still landing
  (`SIDEBAR_ITEM_VI: Phân tích`, `SECTION_VI: PHÂN TÍCH`). The whole hub and
  wizard were then driven under `vi_VN` in the browser (evidence 16–19, 21).

### Assets

Both stylesheets compile under the server's libsass (`sass.compile(filename=…)`
run on vietuat before every one of the five deploys), contain no
`contain:`/`transform:`/`filter:` on any field-bearing wrapper (§5.96 — the
only `transform` is inside a keyframe, as before) and no CSS
`min()`/`max()`/`clamp()` (§5.68).

### PWA

No PWA asset, app shell or shell-injecting module was touched; conventions §3
does not apply and `health_pwa` was not bumped.

---

## 5. The defect this phase found by driving

Staging the first-run screenshot is what exposed it, which is the whole
argument for DoD item 5.

`bi.audit.log.get_recents` (`biz_bi/models/bi_audit_log.py:57-72`) ends with
`d.workspace_id.name`. The `bi.dashboard` read rule grants
`('owner_id','=',user.id)` **on its own**; the `bi.workspace` rule has no such
clause. So a dashboard the user OWNS can live in a workspace they cannot read
— and the moment the QA workspaces were group-scoped, the persona's own
recent dashboard raised `AccessError` on the workspace read, `get_hub_data`
propagated it, and the entire Analytics landing fell back to *"Analytics
access has not been set up for your account yet"* (evidence screenshot 20).
One stale chip, whole page gone, for a configuration any multi-team tenant
reaches on day one.

Fixed inside the sanctioned module: `_hub_recents()` catches `AccessError`
**only** and returns an empty strip, then applies the §4.4 prune to whatever
did come back. Pinned by `test_ah3_04b`, and evidence 21 is the same scenario
afterwards — the first-run card, as intended. Written up as ledger **§5.131**.

---

## 6. Pixel-cycle changelog

Every finding below is a measurement from `evaluate_script` over computed
styles and bounding boxes, taken as the real persona on care.biztinct.com;
before/after screenshots are in the evidence pack (§4 of its README).

### Cycle 1 — the row that was not a row

| Found (measured) | Fixed |
|---|---|
| three cards in one grid row measured **203 / 210 / 179 px** tall (`align-items: start`) | `align-items: stretch`; the list flows from the top and the slack falls to the bottom |
| the counts line sat at **406 / 413 / 413** and the divider with it, because one workspace has no description | the description line is always rendered with a reserved `min-height: 17px`, clamped to one line with a `title` attribute |
| non-8px rhythm: card body `16/18/14`, chip `9/14`, row `6/8` gap `9`, result `9/10`, list gap `1` | 16 / 8·16 / 8 / 8 / 2 |
| **wizard**: the CERTIFIED badge was a sibling of the text column and took ~75px from it, so every two-word dataset name wrapped into a ~100px column | badge moved inside the text column |
| **wizard**: a 180-character dataset description made its card twice as tall as its neighbours | 2-line clamp + `title` attribute |

*Re-audit:* cards **222 / 222 / 222**, counts **408 / 408 / 408**, dividers
**432 / 432 / 432**, body padding `16px`, row padding `8px`.

### Cycle 2 — consistency and optical inset

| Found | Fixed |
|---|---|
| the badge now sat inline for a short name and wrapped under a long one — its position changed card by card down the grid | its own row, `margin-top: auto`, so it is bottom-left in all six |
| the card's content was inset 20px on the left (4px colour bar + 16px padding) and 16px on the right | `padding: 16px 16px 16px 12px` |
| `.bi-hub-page` top padding 28px; recents gap 10px; search input padding 10px (bar 2px taller than the header button) | 24 / 8 / 8 |
| "New dashboard" wrapped onto two lines beside its input | `white-space: nowrap` |
| the wizard footer's Back sat at x=20 and Save at x=1420 while the content column ran 294→1146 | the footer row is now the pane's own box inside a full-width bar |

### Cycle 3 — the last two misalignments

| Found (measured) | Fixed |
|---|---|
| the footer column was 948px (pane + padding) against a 900px pane, so Back's left edge was 24px outside the heading's — visible at 1024 as well | `max-width: 900px`; re-audit: footer **270–1170** = pane **270–1170**, Back's left edge **294** = the heading's **294** |
| the date-range field's 13 chips made the right grid column ~150px taller than the left, leaving a hole under "Split by" that reads as a missing field | `grid-column: 1 / -1`; the chips wrap into 2 rows instead of 4 and the picker block went **~350 → 321 px** |

### Carried through all three cycles

* **Contrast**: every text token measured ≥ **10.05:1** against its own
  background (the theme resolves `--vu-text-secondary` to `#424242`), and the
  primary text 16.1:1 — WCAG AA and AAA on all of it, muted captions
  included. Disabled gallery tiles sit at `opacity .4` and carry their reason
  as a `title`, which is how a disabled control is meant to explain itself.
* **Focus**: one ring, one stylesheet (§5.97) — `--bih-ring` / `--biw-ring`
  (`0 0 0 1px primary, 0 0 0 4px rgba(21,101,192,.16)`) on every interactive
  element in both surfaces, with `outline: none` so nothing draws two
  rectangles. The wizard pane takes focus as a container and shows no ring.
* **Keyboard**: opening the wizard puts `document.activeElement` on
  `.bi-wizard-pane`, so Tab starts inside the new step; a **trusted** Escape
  key press closes the overlay (`wizardStillOpen: false`); Enter in the report
  name saves. No trap framework, as §4.6 allows.
* **Both languages, both widths**: hub and wizard driven under `vi_VN` and
  `en_US` at 1440 and 1024. Vietnamese runs ~30–40% longer and nothing wraps
  badly; the wizard is fully usable at 1024 (evidence 14, 15, 24, 25).

---

## 7. Deferred / not done

* **The six pre-existing `biz_bi` test failures** (§4). Diagnosed, baselined,
  not fixed — out of sanction, and the RLS ones deserve a deliberate decision
  rather than an implementer's edit.
* **Wizard step 1 with zero published datasets** is not stageable here
  without unpublishing six live datasets. The branch is AH-2's, unchanged.
* **AI for creators is now real, but `compose_report` is still modeler-only
  in practice** — not by ACL (it has the same shape as `nlq_chart`) but
  because no surface offers it to a creator. Out of scope by §2.
* **`bi.ai._log`'s audit attribution is uid 1**, because `_log` calls
  `self.env['bi.audit.log'].sudo().log(...)` and `log()` reads `self.env.uid`
  from the sudo'd recordset. Pre-existing, unchanged by this phase (my sudo is
  on the provider recordset only), and out of sanction — but it means
  `ai_request` audit rows do not name the human who asked. Worth a one-line
  fix in `biz_bi` on its next touch.
* **`health_base`'s repo-wide i18n suite and `health_theme`'s dropdown guard**
  were not re-executed on the server (they need `-u health_base` /
  `-u health_theme`, whose upgrade cascade is far riskier than the check);
  both were replicated locally instead, and the theme guard skips glob asset
  entries, which is how this module ships its stylesheets.
* **A pre-existing `health_zalo` error was observed in the server log** while
  the QA persona browsed: `health_zalo.controllers.chat: Error fetching active
  conversations: You are not allowed to access 'Zalo OA Configuration'
  (zalo.config) records`, on a timer, for any CMS-shell user without
  `zalo.config` read access. Different module, already caught and logged by
  its own controller, gone the moment the persona was deleted — flagged, not
  attributed, and worth a ticket (a polling widget should ask once, not log a
  traceback a minute). Zero `biz_bi` / `biz_bi_cms` errors in the same window.
* **`docs/strategy/handovers/analytics-hub-phase{2,3}.md` are untracked** in
  the working tree; they are outside this phase's sanctioned paths, so the
  commit does not add them.

---

## 8. New gotchas — merged into the ledger in this same commit

Per §5.108 (a gotcha that lives only in a phase report does not exist for the
next phase), all four are appended to `HANDOVER-CONVENTIONS.md` §5:

* **§5.131** — a landing page is only as available as its least-entitled
  compartment, and "the user owns this record" does not mean "the user can
  read what the record points at". The recents defect above, generalised.
* **§5.132** — a group change made from a separate `odoo-bin shell` is
  invisible to the running HTTP workers until a restart. §5.114's cache
  clearing is per-process; measured live when a re-granted
  `group_bi_creator` kept reading `False` in the browser while psql showed
  the relation row present.
* **§5.133** — "module X's suite is green" is a hypothesis about a specific
  database. The pristine-baseline recipe (restore from `git show HEAD:`, grep
  the revert, re-run the same tag, compare NAMES not counts) is the way to
  settle whether a failure is yours, and it costs one extra cycle.
* **§5.134** — `code_translations.get_web_translations()` returns a
  `ReadonlyDict`, which is **not** a `dict` subclass, so the usual
  `isinstance(x, dict)` guard measures the wrong object and reports 1 message
  for a catalogue of 83 — a fourth way to conclude a healthy `.po` is dead.
  Also: the import is `from odoo.tools.translate import code_translations`.

---

## 9. Commit

Branch `19.0`, path-scoped to `addons/biz_bi_cms/`, the two sanctioned
`addons/biz_bi/` files, `docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/analytics-hub-phase3*`. The working tree carried
unrelated unstaged changes from another session throughout and none of them
are in this commit.
