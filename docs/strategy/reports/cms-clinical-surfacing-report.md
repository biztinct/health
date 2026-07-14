# health_cms_clinical — Implementation Report

**Phase:** CMS Clinical Surfacing (`docs/strategy/handovers/cms-clinical-surfacing.md`)
**Branch:** 19.0 · **DB:** vietuat · **Date:** 2026-07-14
**Status:** ✅ COMPLETE — deployed, tested (0 failed/0 error), evidence pack committed.

---

## 1. What was built

A new pure **data + view glue module** `addons/health_cms_clinical` (19.0.1.0.0).
No python models, no controllers, no edits to any shipped module — exactly per
the handover non-goals (§0).

File list:

| File | Purpose |
|---|---|
| `__init__.py` | Empty (module has no models). |
| `__manifest__.py` | 19.0.1.0.0, depends on health_cms_sidebar, health_telemonitoring, health_twin, health_vitals, health_consent, health_fieldservice; loads the two data/view files. |
| `data/cms_sidebar_items.xml` (`noupdate="1"`) | "Care Intelligence" expander (seq 15) under `health_cms_sidebar.section_clinical` + 4 leaf children: Deterioration Worklist (→ `health_twin.action_health_twin_risk`), Deterioration Alerts (→ `health_telemonitoring.action_health_monitor_alert`), Monitoring Devices (→ `action_health_monitor_device`), NEWS2 Scores (→ `action_health_ews_score`). Ungated (no `role_ids`), FA icons — cloned field-for-field from the sibling `item_clin_vitals*` expander. |
| `views/ops_profile_tabs.xml` | Inherits `health_fieldservice.view_health_patient_form_ops` (`//notebook` position="inside") to add **Alert Thresholds** (`vitals_thresholds_ops`, group nurse) and **Consents** (`consents_ops`, group base) pages. Field lists + widgets reproduced verbatim from the standard-form source pages. |
| `i18n/vi.po` | Vietnamese catalog for all user-visible strings (each entry carries `#. module: health_cms_clinical` per ledger §5.29). |
| `tests/__init__.py`, `tests/test_cms_clinical.py` | 3 TransactionCase tests (records+action resolution, `get_sidebar_data()` payload, ops-view composition). |

The two ops-tab pages reproduce their sources faithfully:
- **Alert Thresholds** ← `health_vitals/views/res_partner_views.xml`: `vitals_threshold_ids` editable list — `vitals_type_id`, `severity` (badge, danger/warning decorations), `min_value`, `max_value`, `escalation_action`, `notes` (optional show), `active` (optional hide).
- **Consents** ← `health_consent/views/res_partner_views.xml`: a `<group>` with `consent_summary` (readonly) + `consent_ids` readonly list — `name`, `consent_type`, `method`, `granted_by_partner_id` ("Granted By"), `effective_date`, `expiry_date`, `state` (badge, success/warning/danger/info decorations).

---

## 2. Deviations from the handover design

**One deviation — the test only (not the shipped code).**

- **§4 test 3 uses `ops_view.get_combined_arch()`, not `res.partner.get_view(...)['arch']`.**
  Reason: `get_view` runs view post-processing, which **strips `<page groups="...">` nodes** when the calling user (SUPERUSER_ID in tests) is not a member of `group_healthcare_nurse` / `group_healthcare_base`. The first run failed exactly this way — the pages merged correctly but `get_view` removed them before the assert. `get_combined_arch()` applies view inheritance (proving the xpath matched and the pages are present) without the group-based node removal, which is the accurate thing to assert for a data/view module. Actual per-role rendering is proven by the browser evidence pack (where the OM user, who carries the healthcare groups, sees both tabs live). No change to the shipped XML — the pages are correct; only the test's proof mechanism changed. This is a new gotcha (§ below).

Everything else is exactly as specified: sequence 15, the icon set, ungated items, the depends list, the field lists.

---

## 3. Test results (verbatim)

Install with tests, DB vietuat:

```
odoo.tests.stats: health_cms_clinical: 5 tests 0.05s 49 queries
odoo.tests.result: 0 failed, 0 error(s) of 3 tests when loading database 'vietuat'
```

(3 test methods; "5 tests" counts the framework's standard per-class setup entries.)
Server healthy after restart: `curl localhost:8069/web/login` → **HTTP 200**.
Module install log: `loading health_cms_clinical/data/cms_sidebar_items.xml` +
`loading health_cms_clinical/views/ops_profile_tabs.xml` +
`Module health_cms_clinical loaded in 0.78s` with **no** ref/xpath error — a clean
install is itself strong proof the sidebar refs and ops xpath are correct
(a bad ref/xpath fails the install).

---

## 4. Browser evidence pack

Committed to `docs/strategy/reports/cms-clinical-surfacing-evidence/`, driven from
the REAL `/bizapp` CMS as the logged-in **Operations Manager** user (not a deep
link that skips the sidebar):

1. **`01-sidebar-care-intelligence-expanded.png`** — CLINICAL section now shows
   **Care Intelligence** (between Vitals & Observations and Care Plans); clicking
   it expands to reveal Deterioration Worklist / Deterioration Alerts / Monitoring
   Devices / NEWS2 Scores.
2. **`02-deterioration-worklist-open.png`** — clicking **Deterioration Worklist**
   navigates to `action-1675` "Deterioration Worklist" **inside the CMS** — the
   ranked list opens with the default *Critical or High* Risk Band filter and one
   ranked row (score 82, NEWS2 7, 2 open alerts, 1 open critical). ⇒ the sidebar
   item **resolves on click**, not merely renders.
3. **`03-ops-profile-tabs-present.png`** — client profile (An Xu, `action-1430/533`)
   tab bar now shows **Trends, Alert Thresholds, Consents** alongside the existing
   pages.
4. **`04-alert-thresholds-tab.png`** — Alert Thresholds tab open.
5. **`05-consents-tab.png`** — Consents tab open, rendering the summary
   ("service ✗, data_sharing ✓, …") and the consent list with state badges
   (CNS00204 Active, CNS00193 Withdrawn) — identical to the standard-form page.

**Console:** clean on every screen (`list_console_messages` filtered error/warn →
no messages).

### QA fixture + cleanup (§5.34)
The worklist was empty on vietuat (0 `health.twin.risk` rows; running the real
`cron_twin_sweep` produced 0 — no live NEWS2/alert/recent-completed-FSO signals).
To show a populated worklist I seeded ONE QA row (id 112, patient 533 "An Xu",
critical/82). After the screenshots I `unlink()`ed it, committed, and **verified
in a fresh separate shell**: `ROW_112_EXISTS: False`, `TWINRISK_TOTAL_NOW: 0`. No
QA residue remains.

---

## 5. Report-back items (handover §6)

- **(a) Evidence pack** — delivered (sidebar + worklist-open + ops tabs), §4 above.
- **(b) Items resolve on click** — confirmed: Deterioration Worklist opened
  `action-1675` inside the CMS with the ranked list, not just a rendered label.
- **(c) CLINICAL ordering** — correct: Care Intelligence (seq 15) sits between
  Vitals & Observations (10) and Care Plans (20), reading naturally.
- **(d) QA cleanup** — fresh-cursor confirmed (row gone, total 0), §4 above.
- **(e) Masked tabs reproduced cleanly** — both Alert Thresholds and Consents
  reproduced with no field/widget mismatch (Consents renders summary + full list +
  badges live; Alert Thresholds renders its editable list). Nothing to flag for a
  follow-up.

---

## 6. New gotcha (for conventions §5)

**§5.42 (proposed) — `get_view()` STRIPS `<page groups="…">` for a non-member
caller; assert composition with `get_combined_arch()`.** A view-inheritance test
that adds a group-restricted `<page>`/`<field>` and then asserts on
`Model.get_view(...)['arch']` will FAIL when the test user (SUPERUSER_ID in
TransactionCase) is not a member of the referenced group — Odoo's view
post-processing removes group-gated nodes from the returned arch, so the
successfully-merged page appears absent (masking a correct inherit). The fix is to
assert on `view._get_combined_arch()` / `view.get_combined_arch()`, which applies
inheritance (proving the xpath matched) WITHOUT the group-based node removal;
prove actual per-role rendering via the browser pack (a real user who carries the
group). Companion to §5.41 (which is about which VIEW renders on the ops surface);
this is about which NODES survive `get_view` post-processing within a view.

---

## 7. Deferred / not done

Per the binding non-goals: no Zalo tab (deferred), no reordering/removing existing
sidebar items, no new backend actions/menus, no PWA, no messaging, no pip. Nothing
additional deferred.
