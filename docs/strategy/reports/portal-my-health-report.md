# Phase 4E — Portal "My Health": problem list + recent vitals — REPORT

**Module:** `health_portal` 19.0.1.3.0 → **19.0.1.4.0** · **Branch:** 19.0 ·
**Server:** vietuat · **Date:** 2026-07-19 · **Model:** Opus 4.8

## What shipped (file list — health_portal ONLY, §2.1 sanction list)
1. `__manifest__.py` — version `19.0.1.4.0`; `depends += health_condition,
   health_vitals`.
2. `controllers/portal_public.py` — ONE new route
   `GET /my/care/<string:token>/health` — exact clone of `portal_records`
   (`_guard` → `_record_access('health', ip)` → render).
3. `models/health_portal_access.py` — new 4E render-context block (no existing
   method touched): `_conditions()`, `_conditions_rows()`, `_vitals()`,
   `_vital_value()` (static), `_vitals_rows()`, `_health_ctx()`.
4. `views/portal_templates.xml` — new `portal_health` template (two sections:
   "Chẩn đoán đang theo dõi" + "Sinh hiệu gần đây", empty states, all
   `t-esc`); one hub nav link "Sức khỏe của tôi →" added above the Records link.
5. `tests/test_portal.py` — 4E fixtures (`_icd10`, `_condition`, `_vtype`,
   `_obs`) + two new classes `TestPortalHealth` (6 cases) and
   `TestPortalHealthHttp` (2 cases).

No other module was edited. Grepped the diff for
`is_abnormal|alert_level|news2|threshold|risk`: every hit is in a test assert,
a comment, or the pre-existing (unrelated) strategy-report HTML — none in the
render context or template (§3 rail satisfied).

## Design decisions / deviations
- **Panel join (§2.3 "declare which you shipped"):** shipped the **slash-join
  for shared-unit panels** — BP renders `120/80` with a single `mmHg` unit.
  Children are `.sorted('id')` (creation order = systolic then diastolic;
  the model `_order` is datetime-desc which would otherwise flip them to
  `80/120`). Mixed-unit panels fall back to `; `-joined "label value unit"
  pairs with the row unit blanked. Children are excluded from the top-level
  list by the `('parent_id','=',False)` search filter, so they never
  double-appear.
- **`recorded_date` formatting:** it is a `Date` (no tz), so `_conditions_rows`
  formats it directly with `%d/%m/%Y` — NO `_VN_OFFSET` (offset is only applied
  to the `Datetime` `effective_datetime` in `_vitals_rows`).
- **No new `vi.po` entries:** the template Vietnamese is inline QWeb and the new
  Python methods use no `_()` wrapped user-visible strings, so there were no new
  translatable msgids to add. The existing `i18n/vi.po` is unchanged and still
  covers the module's Python/field strings. (This is the honest state — no
  dead/placeholder entries were added just to touch the file.)
- **No PWA bump:** portal website surface, not health_pwa (per §0 non-goal).

## Test results (verbatim)
Deploy: `-u health_portal --test-enable --test-tags /health_portal
--stop-after-init --workers 0` (NO `--no-http` — HttpCase present).

```
0 failed, 0 error(s) of 32 tests when loading database 'vietuat'
EXIT:0    HTTP:200 (/web/login)
```

(First run was `1 failed of 32`: `test_01` asserted an exact `display_vi`, but
vietuat's seeded `I10` carries `Tăng huyết áp vô căn (nguyên phát)`; my
`_icd10` fixture preserves an existing display_vi. Relaxed the assert to a
substring + code check — which is also more faithful to what the patient
actually sees. Re-run: clean.)

The 8 handover test cases map to: T1→`test_01`, T2→`test_02`, T3→`test_03`,
T4→`test_04`, T5→`test_05`, T6→`test_06`, T7→`test_07`, T8→`test_08`.

## Browser evidence pack
`docs/strategy/reports/portal-my-health-evidence/` (README + 3 screenshots),
real drive on Demo Patient 861 from the hub:
- `01` hub shows the new "Sức khỏe của tôi →" link.
- `02` /health: **2 active diagnoses in Vietnamese** (I10, E11, "từ 08/07/2026")
  + **honest empty vitals state** (861 has 0 observations).
- `03` invalid-token /health → neutral page, byte-identical, no PHI.
- Console: only the pre-existing Quirks-Mode notice (shared shell), no errors.

## Real 861 render counts (data-honesty)
Active conditions **2** (I10, E11); recent top-level vitals **0** → empty state.
No prod data seeded.

## Deferred (unchanged from handover non-goals)
Risk communication, portal writes, patient messaging, resolved/inactive
condition history — all out of scope for 4E.

## Proposed ledger gotcha (§5 candidate)
**A portal/read fixture that reuses a REAL seeded `medical.code` (or any
seeded reference row) inherits its live display fields — assert on the stable
key (`code`) or a substring, never the exact `display_vi`.** vietuat's `I10`
is seeded as `Tăng huyết áp vô căn (nguyên phát)`; a `get('icd10','I10')`-style
"ensure" helper that only fills a MISSING `display_vi` leaves the seeded value
in place, so `assertEqual(label, 'Tăng huyết áp vô căn')` RED-lights a correct
render. Test the invariant you own (the ICD-10 code, the scoping, the ordering),
substring-match anything sourced from seed data.
