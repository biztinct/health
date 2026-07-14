# health_cms_clinical — surface the clinical-intelligence layer on the CMS

A consolidation phase that closes the discoverability gap the telemonitoring →
twin arc surfaced: a large body of shipped clinical-intelligence work is
stranded off the `/bizapp` CMS surface care managers actually use. Two masks:
(1) the telemonitoring + twin backend MENUS aren't in the CMS sidebar;
(2) clinically-relevant patient-form TABS (Alert Thresholds, Consents) are
masked on the standalone ops client profile (ledger §5.41 — they inherit the
standard patient form, which the ops profile doesn't render).

This is ONE new **pure data + view glue module** — NO python, NO edits to any
shipped module. It just adds `cms.sidebar.item` records (referencing existing
sections + actions) and two ops-view tab inherits (referencing existing
fields). Low-risk, high-leverage: it unlocks the whole arc onto the real
surface.

Read `HANDOVER-CONVENTIONS.md` first (§4 flat-mono/icons, §5.41 the ops-view
rule, §8/§8.1 evidence-pack). All plumbing facts below are pre-verified — do
not re-derive.

---

## 0. Scope and binding non-goals

**Build — new module `addons/health_cms_clinical` (19.0.1.0.0), data+views only:**
1. `data/cms_sidebar_items.xml` (`noupdate="1"`): a **"Care Intelligence"**
   parent item under the existing CLINICAL section, with children linking to
   the Deterioration Worklist, Deterioration Alerts, Monitoring Devices, and
   NEWS2 Scores actions.
2. `views/ops_profile_tabs.xml`: inherit
   `health_fieldservice.view_health_patient_form_ops` to add **Alert
   Thresholds** and **Consents** tabs (they exist on the standard form; this
   surfaces them on the ops profile — same fix as the twin Trends tab).
3. `i18n/vi.po`, minimal tests, `__manifest__.py`.

**Binding NON-goals:**
- NO python, NO models, NO controllers — pure data + view XML.
- NO edits to health_cms_sidebar, health_telemonitoring, health_twin,
  health_vitals, health_consent, health_fieldservice, or any shipped module.
  Everything is NEW records / NEW inherit views in health_cms_clinical.
- NO new backend actions/menus (the /odoo menus already exist; this only
  surfaces them in the CMS sidebar).
- NO Zalo tab (defer), NO reordering/removing existing sidebar items, NO
  changes to the ops profile's existing pages.
- NO PWA, NO messaging, NO pip.

---

## 1. Verified plumbing facts (do not re-derive)

All paths relative to `addons/`.

**CMS sidebar (model-based, seed-data-driven):**
- Models: `cms.sidebar.section` + `cms.sidebar.item`
  (`health_cms_sidebar/models/`). Item fields:
  `name, section_id (M2O), parent_id (M2O — null=root/expander), sequence,
  icon (FA class string), action_xmlid (Char — the backend action, resolved
  on click), match_action_xmlids, match_models (Char — highlight rules),
  role_ids (M2M access.role — EMPTY = ungated/visible to all; data ACL still
  gates records), active`.
- The CLINICAL section record: `health_cms_sidebar.section_clinical`
  (`data/cms_sidebar_items_clinical.xml:12`, technical_key `clinical`).
- Sibling pattern to CLONE — an expander parent + leaf children
  (`cms_sidebar_items_clinical.xml:28-53`): parent "Vitals & Observations"
  (icon `fa fa-heartbeat`, no action_xmlid → expands) with children
  Observations/Thresholds/Types (each sets `action_xmlid` +
  `match_action_xmlids` + `match_models`).
- Seed files are `noupdate="1"` — NEW item records (new xmlids) in a
  `noupdate="1"` data file ARE created on install/upgrade (noupdate only
  blocks re-writing EXISTING records). So adding items is a normal data-file
  add; no DB cutover needed.
- Rendering: `cms.sidebar.item.get_sidebar_data()`
  (`cms_sidebar_item.py:67-131`) returns items filtered by `access_role_id`
  (admins see all; empty role_ids = ungated). `action_xmlid` is resolved to
  an `ir.actions.act_window` on the frontend at click time.

**Backend action xmlids to link (verified they exist):**
- `health_twin.action_health_twin_risk` — Deterioration Worklist
  (model `health.twin.risk`).
- `health_telemonitoring.action_health_monitor_alert` — Deterioration Alerts
  (model `health.monitor.alert`).
- `health_telemonitoring.action_health_monitor_device` — Monitoring Devices
  (model `health.monitor.device`).
- `health_telemonitoring.action_health_ews_score` — NEWS2 Scores
  (model `health.ews.score`).

**Ops profile view + masked tabs:**
- The real client chart is `health_fieldservice.view_health_patient_form_ops`
  (priority 0, js_class `ops_client_profile_form`); its custom OWL template
  renders the arch via `props.Renderer`, so notebook pages added by inheriting
  THIS view render (ledger §5.41; health_twin's Trends tab proves it). Its
  existing pages: Profile Overview, Bookings, Address Information, Intake
  Notes, Insurance & Billing, Active Packages, Healthcare Relationships,
  Clinical Notes, Financial Summary, Trends. Attach new pages via
  `<xpath expr="//notebook" position="inside">`.
- Masked tab sources to reproduce (their fields live on res.partner; the new
  module depends on their modules so the fields exist):
  - **Alert Thresholds** — `res.partner.vitals_threshold_ids`
    (health_vitals). Existing page content
    (`health_vitals/views/res_partner_views.xml`): editable list of
    `vitals_type_id, severity (badge), min_value, max_value,
    escalation_action, notes, active`. Group
    `health_base.group_healthcare_nurse`.
  - **Consents** — `res.partner.consent_ids` (health_consent). Existing page
    (`health_consent/views/res_partner_views.xml`): a summary + a list of
    consents with a state badge. Group
    `health_base.group_healthcare_base`.

---

## 2. Architecture

`health_cms_clinical` 19.0.1.0.0. `depends`: `['health_cms_sidebar',
'health_telemonitoring', 'health_twin', 'health_vitals', 'health_consent',
'health_fieldservice']`. No `mail`, no web assets, no python beyond `__init__`
(likely empty models/__init__ — the module may have NO models dir at all).

### 2.1 Sidebar items (data/cms_sidebar_items.xml, noupdate="1")

Clone the expander+children shape. A parent expander then four leaves:

```xml
<odoo noupdate="1">
  <record id="item_clin_care_intel" model="cms.sidebar.item">
    <field name="name">Care Intelligence</field>
    <field name="section_id" ref="health_cms_sidebar.section_clinical"/>
    <field name="sequence">15</field>          <!-- sits just after Vitals (10) -->
    <field name="icon">fa fa-line-chart</field>
    <!-- no action_xmlid → expander -->
  </record>

  <record id="item_clin_worklist" model="cms.sidebar.item">
    <field name="name">Deterioration Worklist</field>
    <field name="section_id" ref="health_cms_sidebar.section_clinical"/>
    <field name="parent_id" ref="item_clin_care_intel"/>
    <field name="sequence">16</field>
    <field name="icon">fa fa-line-chart</field>
    <field name="action_xmlid">health_twin.action_health_twin_risk</field>
    <field name="match_action_xmlids">health_twin.action_health_twin_risk</field>
    <field name="match_models">health.twin.risk</field>
  </record>

  <record id="item_clin_alerts" model="cms.sidebar.item">
    <field name="name">Deterioration Alerts</field>
    <field name="section_id" ref="health_cms_sidebar.section_clinical"/>
    <field name="parent_id" ref="item_clin_care_intel"/>
    <field name="sequence">17</field>
    <field name="icon">fa fa-exclamation-triangle</field>
    <field name="action_xmlid">health_telemonitoring.action_health_monitor_alert</field>
    <field name="match_action_xmlids">health_telemonitoring.action_health_monitor_alert</field>
    <field name="match_models">health.monitor.alert</field>
  </record>

  <record id="item_clin_devices" model="cms.sidebar.item">
    <field name="name">Monitoring Devices</field>
    <field name="section_id" ref="health_cms_sidebar.section_clinical"/>
    <field name="parent_id" ref="item_clin_care_intel"/>
    <field name="sequence">18</field>
    <field name="icon">fa fa-heartbeat</field>
    <field name="action_xmlid">health_telemonitoring.action_health_monitor_device</field>
    <field name="match_action_xmlids">health_telemonitoring.action_health_monitor_device</field>
    <field name="match_models">health.monitor.device</field>
  </record>

  <record id="item_clin_news2" model="cms.sidebar.item">
    <field name="name">NEWS2 Scores</field>
    <field name="section_id" ref="health_cms_sidebar.section_clinical"/>
    <field name="parent_id" ref="item_clin_care_intel"/>
    <field name="sequence">19</field>
    <field name="icon">fa fa-heartbeat</field>
    <field name="action_xmlid">health_telemonitoring.action_health_ews_score</field>
    <field name="match_action_xmlids">health_telemonitoring.action_health_ews_score</field>
    <field name="match_models">health.ews.score</field>
  </record>
</odoo>
```
Notes: leave `role_ids` empty (ungated like siblings — the action/model ACL
gates the records). Verify the sibling items' EXACT icon field + any other
required field by reading `cms_sidebar_items_clinical.xml` before writing, and
match them (e.g. if siblings set an `active` field or a `color`, mirror it).
Check whether the leaf `name` values need `&amp;`-escaping (none here do).

### 2.2 Ops profile tabs (views/ops_profile_tabs.xml)

Inherit the ops view; add two pages. Reproduce each masked page's content
(read the two source view files for the exact field list + widgets and copy
the inner content verbatim so the ops tab matches the standard-form tab):

```xml
<record id="view_ops_profile_clinical_tabs" model="ir.ui.view">
  <field name="name">res.partner.form.ops.clinical.tabs</field>
  <field name="model">res.partner</field>
  <field name="inherit_id" ref="health_fieldservice.view_health_patient_form_ops"/>
  <field name="arch" type="xml">
    <xpath expr="//notebook" position="inside">
      <page string="Alert Thresholds" name="vitals_thresholds_ops"
            groups="health_base.group_healthcare_nurse">
        <field name="vitals_threshold_ids">
          <!-- copy the list content from health_vitals/views/res_partner_views.xml -->
        </field>
      </page>
      <page string="Consents" name="consents_ops"
            groups="health_base.group_healthcare_base">
        <field name="consent_ids">
          <!-- copy the list content from health_consent/views/res_partner_views.xml -->
        </field>
      </page>
    </xpath>
  </field>
</record>
```
Match the field widgets/attrs of the source pages exactly (badges, readonly,
etc.). Do NOT invent new fields. If a source page wraps its list in a `<group>`
/ summary, reproduce that too so the ops tab looks like the standard one.

### 2.3 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_cms_clinical | (new module — all) | everything |

NO edits to any other module.

---

## 3. Safety rails (binding)

- Pure additive data + views; the underlying action/model ACLs already gate
  data — sidebar items are ungated by design (matches siblings). Confirm no
  role_ids leaks a record a user's model ACL would otherwise hide (it can't —
  the action opens the model under the user's ACL).
- Flat-mono, FA icons like the siblings (no emoji), no gradients (§4).
- No pip, no messaging. QA fixtures (if any) cleaned + fresh-cursor verified.

## 4. Tests (tests/test_cms_clinical.py; ~4, TransactionCase)

1. The 5 `cms.sidebar.item` records exist, are under
   `section_clinical`, and the 4 leaves' `action_xmlid` each resolve to a
   real `ir.actions.act_window` (`env.ref(xmlid)` succeeds).
2. `get_sidebar_data()` as a healthcare user returns the Care Intelligence
   parent with its 4 children under the CLINICAL section.
3. The ops view composes: `env.ref(
   'health_fieldservice.view_health_patient_form_ops')` + the new inherit →
   `res.partner.get_view(view_id=ops_view_id, view_type='form')` arch contains
   `name="vitals_thresholds_ops"` and `name="consents_ops"`.
4. Module installs clean (implicit — the test suite loading proves the views
   parse and the xpath matched).

(Most verification is the browser evidence pack — a data/view module's real
proof is that the sidebar + tabs render on the CMS.)

## 5. Deploy / verify (conventions §2)

- `-i health_cms_clinical --test-enable --test-tags /health_cms_clinical
  --stop-after-init --workers 0`. Result line; restart; `/web/login` 200.
  A non-matching xpath or bad `ref` FAILS the install — a clean install is
  strong evidence the sidebar refs + ops xpath are correct.
- **Browser evidence pack (§8.1)** to
  `docs/strategy/reports/cms-clinical-surfacing-evidence/`, driven from the
  REAL /bizapp CMS as a healthcare user:
  1. The CMS sidebar CLINICAL section now shows **Care Intelligence**;
     expand it → Deterioration Worklist / Alerts / Devices / NEWS2 Scores.
     Screenshot.
  2. Click **Deterioration Worklist** → the ranked worklist list opens inside
     the CMS. Screenshot. (Seed one high-risk QA patient so a row shows, or
     accept an empty list — note which.)
  3. Open a client profile (ops list → a client) → confirm the **Alert
     Thresholds** and **Consents** tabs now appear alongside Trends.
     Screenshot.
  4. Console clean. Delete any QA rows + fresh-cursor verify (§5.34).
- Reachable client-profile URL for QA: `/bizapp/action-1430/<patient_id>`
  (the ops client list action; opens `view_health_patient_form_ops`).

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/cms-clinical-surfacing-report.md`), plus: (a) the
evidence pack (sidebar + worklist-open + ops tabs), (b) confirmation the
sidebar items resolve on click (not just render), (c) whether the CLINICAL
section ordering looks right (Care Intelligence sequence 15 vs siblings), (d)
QA cleanup fresh-cursor confirmation, (e) any masked tab you found you could
NOT cleanly reproduce (field/widget mismatch) — flag for a follow-up.

Kickoff line: `Implement the phase specified in docs/strategy/handovers/cms-clinical-surfacing.md.`
