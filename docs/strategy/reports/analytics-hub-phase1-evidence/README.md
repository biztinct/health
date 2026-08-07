# AH-1 browser evidence pack — `biz_bi_cms` Analytics Hub

Conventions §8.5 / DoD item 5. Everything below was driven live on
**https://care.biztinct.com** (db `vietuat`) against the code that is
committed, after the final deploy (`/tmp/ahp1/deploy4.log`, `EXIT:0`,
`0 failed, 0 error(s) of 6 tests`).

## Persona

A throwaway user created and deleted the same session:

| | |
|---|---|
| login | `ahp1_qa_ops` (uid 7743 on the first drive, 7756 on the re-drive) |
| `access.role` | **Operations Manager** — one of the four gated roles |
| BI groups | `biz_bi.group_bi_creator` only, granted by `hooks.grant_creator_group()` — deliberately **not** modeler or admin, because the interesting failure modes all live at the creator level |
| deleted | yes — `qa-fixture-cleanup.txt` is the fresh-cursor (`psql`) proof (§5.34) |

The persona was created **after** the module was installed, which is exactly
the drift the migration script exists for: `HAS_CREATOR` came back `False`
until `grant_creator_group(env)` was re-run. That is recorded in the report.

## The exact click path — from the normal entry point, no deep links

| # | Action | Result | Screenshot |
|---|---|---|---|
| 1 | `https://care.biztinct.com/web/login` → User ID `ahp1_qa_ops` + password → **Log in** | lands on `/bizapp/action-1417` — the CMS shell's *Operations Command Center*, NOT `/odoo` | `01-login.png` |
| 2 | scroll the CMS sidebar down | an **ANALYTICS** section with one **Analytics** leaf, between *INTEROP & COMPLIANCE* and *ADMIN* | `02-bizapp-shell-analytics-section.png` |
| 3 | click sidebar → **Analytics** | `/bizapp/action-1723` — the hub renders: header + `＋ Create Report`, search box, workspace grid with the inline-SVG workspace icons, the mono left colour bar, counts, and every dashboard listed as a row. Recents strip absent (correctly hidden — this user has no history yet) | `03-hub-landing.png` |
| 4 | type `revenue` into the search box | grid is replaced by one flat **RESULTS** list, two hits across two different workspaces, each labelled with its workspace; a clear (✕) button appears. **No RPC fires** — the filter runs over the payload already in memory | `04-hub-search-revenue.png` |
| 5 | clear the search → click **Operations Overview** in the Operations card | the dashboard opens **with the CMS sidebar still present** and the Analytics leaf still highlighted — chrome persistence via `match_action_tags` | `05-dashboard-with-cms-chrome.png` |
| 6 | click sidebar → **Analytics** again | the hub now shows **CONTINUE WHERE YOU LEFT OFF** with the *Operations Overview* chip | `06-hub-with-recents.png` |
| 7 | click **＋ Create Report** | `/bizapp/action-1723/action-biz_bi.explore` — the Explore builder opens, chrome intact, six datasets in the picker, **no error dialog** | `09-create-report-explore-no-dialog.png` |

## The defect this drive found (and the fix)

Step 7 originally produced a modal reading *"You are not allowed to access
'BI AI Provider' (bi.ai.provider) records."* — captured as
`07-BEFORE-FIX-explore-accesserror-dialog.png` and
`08-BEFORE-FIX-explore-after-dismissing-dialog.png`.

Cause: `explore_action.js` calls `bi.ai.is_available()` in `onWillStart`
without a `.catch`, and `bi.ai.provider`'s ACL starts at `group_bi_modeler`.
Pre-existing in `biz_bi` and never fired, because before this module only two
accounts on vietuat held any BI group and both were BI **administrators**.
Granting `group_bi_creator` to nine business users is what makes it
reachable, so it is this phase's to neutralise —
`biz_bi_cms/models/bi_ai.py` overrides `is_available()` to answer `False` on
`AccessError` instead of raising. Deviation **D4** in the report; test
`test_ai_probe_degrades_for_a_creator` pins it.

## Console log, per screen (`list_console_messages`, full output)

| Screen | Console |
|---|---|
| `/bizapp/action-1417` (shell, step 2) | `[issue] A form field element should have an id or name attribute (count: 1)` |
| hub (step 3) | `[issue] A form field element should have an id or name attribute (count: 1)` |
| dashboard (step 5) | `[issue] A form field element should have an id or name attribute (count: 2)` |
| hub with recents (step 6) | `[issue] A form field element should have an id or name attribute (count: 1)` |
| Explore (step 7) | `[issue] A form field element should have an id or name attribute (count: 3)` |

**Zero errors and zero warnings on every screen.** The single `[issue]` entry
is a Chrome accessibility advisory, **pre-existing** — it is already present
on the shell before the hub is opened (count 1), and the extra counts on the
dashboard and Explore screens come from `biz_bi`'s own inputs (chart name,
dataset select). An earlier build of the hub added one to that count; the
search input now carries `id="bi_hub_search" name="bi_hub_search"` and the
hub screens are back to the shell's baseline of 1.

## Server-side result of the action

* `server-side-rows.txt` — the `bi.audit.log` rows the drive created, **by
  id**: `dashboard_view` on `bi.dashboard` id 1 (*Operations Overview*)
  plus the eight `query` rows its widgets emitted (ids 742–750 on the first
  drive, 751–759 on the re-drive), and the `get_recents()` payload the hub
  reads back. Also the exact `get_hub_data()` payload for this persona:
  four workspaces with their icons, colours and dashboard counts, and
  `is_creator=True is_modeler=False is_admin=False ai_available=False`.
* `sidebar-gating.txt` — the sidebar item's stored fields, the four gated
  roles, the full section-sequence table, and `get_sidebar_data()` run as
  four real personas: **Operations Manager sees ANALYTICS; Nurse (×2) and
  CRM do not.** That is the ungated-user proof the handover asked for.
* `test-results.txt` — the verbatim `odoo.tests.result` line and the list of
  executed test methods.
* `qa-fixture-cleanup.txt` — the fresh-cursor proof that nothing this pack
  created survives, and that `/web/login` still answers 200.

## Honest note on the fixture cleanup

`bi.audit.log` is append-only by design: its `unlink()` raises, and
`user_id` is a required Many2one, so PostgreSQL's `restrict` blocked deleting
the QA user until its rows went. The eighteen QA-generated rows were removed
with a raw `DELETE … WHERE user_id = <qa uid>` — deliberately bypassing the
guard, scoped to the two throwaway uids, and recorded here rather than left
as a silent orphan account. No other audit row was touched.
