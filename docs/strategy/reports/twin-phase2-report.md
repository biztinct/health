# health_twin — Phase 2 report: Vitals & NEWS2 Trend Charts

**Module:** health_twin 19.0.1.0.1 → **19.0.2.0.0**
**Server:** vietuat (care.biztinct.com), Odoo 19 CE. **Branch:** 19.0.
**Scope:** the client-trajectory view — an ECharts small-multiples "Trends"
tab on the patient chart (BP / HR / SpO₂ / temperature / weight / NEWS2 over
time, with the patient's own alert-threshold bands overlaid), fed by one ORM
data method. Backend-only; **no PWA changes / no PWA bump** (handover §0).

---

## 1. What was built (file list)

**New files (health_twin):**
- `static/src/js/twin_trend_charts.js` — the OWL **view-widget**
  (`registry.category("view_widgets").add("twin_trend_charts", …)`), cloned
  from `health_crm/contact_timeline.js` + the biz_bi `chart_renderer.js`
  ECharts lifecycle. Reads `this.props.record.resId`, one `orm.call(
  'health.twin.risk','chart_series',[resId, days])`, inits one ECharts line
  chart per panel, theme-var palette, threshold `markLine` + NEWS2 `markArea`,
  7/30/90-day selector, per-panel empty states, ResizeObserver.
- `static/src/xml/twin_trend_charts.xml` — template `health_twin.TwinTrendCharts`.
- `static/src/scss/twin_trend_charts.scss` — flat-mono, `--vu-*`-token styles.

**Edited files (health_twin — all within the sanctioned-edits table):**
- `models/health_twin_risk.py` — added the `chart_series(patient_id, days)`
  `@api.model` data facade (+ `_clamp_range_days`) and the panel/zone
  constants. **No other model logic touched.**
- `views/res_partner_views.xml` — **new** file: inherits
  `health_base.view_health_patient_form`, adds the nurse-gated **"Trends"**
  page hosting `<widget name="twin_trend_charts"/>`.
- `__manifest__.py` — version → 19.0.2.0.0; `depends += biz_bi` (ECharts
  stack); registered the new view + the `web.assets_backend` bundle.
- `i18n/vi.po` — new user-visible strings (panel titles, header, empty states).
- `tests/test_twin_charts.py` (+ `tests/__init__.py`) — 8 TransactionCase tests.

---

## 2. Test results (verbatim)

Deploy per conventions §2 — `-u health_twin` (biz_bi already installed; the
new dep edge upgraded cleanly, no `-u biz_bi` needed), TransactionCase only:

```
2026-07-14 09:58:11,691 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 29 tests when loading database 'vietuat'
```

29 = 21 pre-existing health_twin tests + **8 new** `TestTwinCharts`
(test_01_happy_path, test_02_threshold_bands, test_03_range_clamp_and_window,
test_04_no_cross_catchment_leak, test_05_empty_patient,
test_06_news2_history_superseded, test_07_spo2_union,
test_08_glucose_present_when_recorded — all Started + suite green). No prior
tests regressed.

Server healthy after final restart: `curl localhost:8069/web/login` → **HTTP:200**.

---

## 3. Live `chart_series` RPC round-trip (browser, seeded patient 8729)

`chart_series(8729, 30)` over the web RPC returned (abridged):

```
range_days: 30
panels:
  bp      Blood Pressure  mmHg  series[Systolic×7, Diastolic×7]  bands:0
  hr      Heart Rate      bpm   series[Heart Rate×7]             bands:1 (warning 60–90)
  spo2    SpO₂            %     series[SpO₂×7]                   bands:0
  temp    Temperature     °C    series[Temperature×7]           bands:0
  weight  Weight          kg    series[Weight×7]                bands:0
  news2   NEWS2                 series[NEWS2×7]     band_zones:3 [[0,4,success],[5,6,warning],[7,20,danger]]
hr points: [["2026-07-02 10:01:01",88], … ,["2026-07-14 10:01:01",78]]  (oldest-first, [iso,value])
```

`chart_series(8729, 999)` → `range_days: 90`; `…, 5` → `7`; omitted → `30`.
`window.echarts` present = **5.5.1** (from biz_bi). See §5 for the render shots.

---

## 4. Deviations from the handover (with reasons)

1. **Widget registry value shape** — handover §2.2 wrote `{Component: …}`; the
   in-repo `view_widgets` precedent (contact_timeline) and Odoo 19 use
   `{component: …}` (lowercase). Followed the working precedent. No interface
   change.
2. **AccessError guard added to `chart_series`** (small, additive). Under the
   user env, reading a *cross-catchment* `patient.is_patient` raises
   `AccessError` (res.partner is catchment-scoped), not just empty rows. Wrapped
   the patient read in try/except → returns the empty envelope. This *preserves*
   the handover's "no cross-catchment leak, not sudo" contract (§3) and makes
   it a clean empty result instead of a 500. Nothing else changed.
3. **Panel titles wrapped in `_()`** at emit time (not stored translated) so
   vi.po can cover them — the constant list stays a plain class attribute.
4. **Browser evidence entry point** — the handover's "open a patient → Trends
   tab" flow is **not reachable** on vietuat, for a reason outside this phase's
   sanctioned scope (see §6). The widget was instead exercised through its own
   `_palette()`/`_buildOption()` (pulled live from the registry) against the
   live `chart_series` RPC, in light + dark. This is a deviation in *how the
   evidence was captured*, not in the widget. No unsanctioned files were
   touched to produce it.

No architecture/model/field/interface was renamed or redesigned. No edits to
biz_bi / health_vitals / health_telemonitoring / health_base / health_pwa. No
PWA bump (backend-only). No pip.

---

## 5. Evidence pack

`docs/strategy/reports/twin-phase2-evidence/`:
- `01-trends-light-30d.png` — 6 panels, **light** theme, 30-day range: flat-mono
  blue lines, the HR **"warning max"** dashed threshold line at 90, BP 2-series
  legend, NEWS2 zone shading, per-panel units.
- `02-trends-dark-90d.png` — same widget, **dark** theme + 90-day range: lines
  flip to accent-blue `#42A5F5`, axis to white-72% — proving the ECharts colours
  are read live from the `--vu-*` vars and follow `[data-theme='dark']`.
- `console-log.txt` — no widget console errors (light or dark).
- `README.md` — the full drive narrative + the honest entry-point caveat.

**QA cleanup (§5.34):** seeded QA patient 8729 (42 obs + 7 NEWS2 + 1 HR
threshold + 1 cron-computed twin row) and user `twin_qa_trends` **deleted**;
**fresh-cursor verified** in a separate shell — `patient_exists=False`,
`user_exists=False`, `obs=0 scores=0 thr=0 twin=0`.

---

## 6. Report-back items (handover §6)

- **(a) Evidence incl. dark-mode shot** — done (§5). The CSS-var palette
  follows the theme with no reload.
- **(b) biz_bi / ECharts load path** — **depending on `biz_bi` sufficed**;
  `window.echarts` (5.5.1) is present on `web.assets_backend` with load order
  honoured by the new dep edge. **No `loadJS` needed**, no second echarts copy.
- **(c) Tab-visibility / resize** — inits charts in a `useEffect` that fires
  after the panel DOM is patched, **guards zero-size hosts**, and a
  rAF-coalesced `ResizeObserver` both **re-inits skipped charts** and resizes
  live ones. In Odoo 19 the Notebook mounts only the *active* page's content,
  so the widget mounts fresh (already visible) on tab-open — first-open sizing
  is correct without a manual nudge; the zero-size guard + observer are the
  belt-and-braces for the edge case.
- **(d) QA cleanup fresh-cursor** — confirmed (§5).
- **(e) New gotcha** — see §7.

### ⚠️ Discoverability finding (the entry-point caveat — needs a follow-up outside this phase)

The Trends tab lands (correctly, per the sanctioned-edits table) on
**`health_base.view_health_patient_form`** — the *standard* patient form.
`get_view()` for that view as a nurse **does** contain the `twin_trends` page
+ the `twin_trend_charts` widget (server-confirmed). **But** this deployment's
real patient surface is a *separate, standalone* res.partner form,
**`health_fieldservice.view_health_patient_form_ops`** (js_class
`ops_client_profile_form`, **priority 0** → the default patient form; the ops
client list forces it via `form_view_ref`). That curated view has its own nine
hand-authored pages and does **not** inherit `view_health_patient_form`, so
**none** of the standard form's clinical inherit pages surface there — not the
new Trends tab, and not the pre-existing health_vitals **"Alert Thresholds" /
"Vitals"** tabs either. This is the already-tracked **CMS-sidebar
discoverability gap**.

**Consequence:** the Trends widget is complete, correct and rendering, but a
care manager on the CMS client profile will not *see* it until it is also
wired into `view_health_patient_form_ops` (or that form is made to inherit the
standard one). That is a **`health_fieldservice`** edit — **outside this
phase's sanctioned files** — so it is flagged here for a follow-up phase, not
done. Same one-line fix would restore health_vitals' Alert Thresholds/Vitals
tabs on the CMS profile too.

---

## 7. New gotcha (for conventions §5)

**§5.41 — On vietuat the "patient form" a user actually opens is a *standalone*
curated view (`view_health_patient_form_ops`, priority 0), NOT
`view_health_patient_form`; a page added by inheriting the standard form is
invisible on the CMS client profile.** `health_fieldservice`'s
`ops_client_profile_form` is a `priority="0"` primary res.partner form with
its own hand-authored notebook and `js_class="ops_client_profile_form"`; the
ops client list opens it via `context={'form_view_ref': '…_ops'}`, and it wins
view resolution even for direct `/action-<id>/<res_id>` URLs. It does **not**
inherit `view_health_patient_form`, so every clinical tab added by inheriting
the standard form (health_vitals Alert Thresholds/Vitals, health_twin Trends)
is present in `get_view()` yet **absent from the surface users see**. Verify a
patient-form tab by checking **which view actually renders** (its js_class /
page set), not just that `get_view` contains your page — and budget a
`health_fieldservice` edit to surface it on the ops profile. Corollary: the
standard `view_health_patient_form` may not even open cleanly in this build
(a CMS Zalo systray-chat poll raises AccessError for non-Zalo users and
crashes the action transition) — it is effectively not a maintained surface.
Also (minor, §5.16 family): `res.users` groups write is `group_ids`, not
`groups_id`, in Odoo 19.

---

## 8. Deferred / not done
- Wiring the Trends tab into the CMS ops-profile view (health_fieldservice —
  outside sanctioned scope; §6/§7).
- PWA trend view (handover non-goal — PWA already ships SVG sparklines).
- Predictive/forecast overlay, what-if, risk-history table (later twin phases).
