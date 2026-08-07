# AH-2 browser evidence pack — the guided Create Report wizard

Conventions §8.5 / DoD item 5. Everything below was driven live on
**https://care.biztinct.com** (db `vietuat`) against the committed code,
after the final deploy (`/tmp/ahp2/deploy3.log`, `EXIT:0`,
`0 failed, 0 error(s) of 13 tests`).

## Persona

A throwaway user created and deleted the same session:

| | |
|---|---|
| login | `ahp2_qa_ops` (uid **7996**) |
| `access.role` | **Operations Manager** — one of the four Analytics roles |
| BI groups | `biz_bi.group_bi_creator` **only**, and *not* granted by hand: the account was created after the module was installed and the AH-2 `res.users` hook linked the group at create time. That is the gap Phase 1 measured live (`HAS_CREATOR: False`) and this phase closes. |
| later, for one step | `biz_bi.group_bi_modeler` was added temporarily so the AI box would render (see step 9), then removed with the account |
| deleted | yes — `qa-fixture-cleanup.txt` is the fresh-cursor (`psql`) proof (§5.34) |

## The exact click path — from the login page, no deep links

| # | Action | Result | Screenshot |
|---|---|---|---|
| 1 | `https://care.biztinct.com/web/login` → User ID `ahp2_qa_ops` + password → **Log in** | lands on `/bizapp/action-1417`, the CMS shell's *Operations Command Center* | `01-login.png` |
| 2 | scroll the CMS sidebar | an **ANALYTICS** section with one **Analytics** leaf, between *INTEROP & COMPLIANCE* and *ADMIN* | `02-bizapp-shell-analytics-section.png` |
| 3 | click sidebar → **Analytics** | `/bizapp/action-1723` — the Phase-1 hub: header, `＋ Create Report`, search, four workspace cards | `03-hub-landing.png` |
| 4 | click **＋ Create Report** | the wizard opens as a full-viewport overlay on step **1**: six published datasets as cards, `Certified` badges, the step rail showing `1 Choose data / 2 Build / 3 Preview & save`, a ✕, and the footer hint *Pick a dataset to continue* | `04-wizard-step1-datasets.png` |
| 5 | click the **Bookings & Service Orders** card | step **2**. No AI box (correct for a creator — see step 9), the four pickers, and the chart gallery with every type the current selection cannot support **disabled with its reason as the tooltip** (`Bar → "Needs at least 1 dimension(s)"`). Step 1's dot is now a tick and clickable; 2 and 3 are not | `05-wizard-step2-build.png` |
| 6 | Measure = **Total Price**, Break down by = **Facility**, date-range chip = **Last 12 months** | the gallery re-recommends live: **Bar** becomes active, *Stacked* / *Big number* / *Matrix* stay disabled, **Preview** enables | `06-wizard-step2-picked.png` |
| 7 | click **Preview** | step **3** with a real ECharts bar chart of the live data, the name pre-filled *Total Price by Facility*, and the dashboard target list with **New dashboard / My dashboard** pre-selected | `07-wizard-step3-preview.png` |
| 8 | name → `AH2 QA Total Price by Facility`, new dashboard → `AH2 QA Dashboard`, click **Save report** | navigates to `/bizapp/action-1723/action-biz_bi.dashboard` — the new dashboard, the chart on it, **CMS sidebar chrome intact and the Analytics leaf still highlighted** | `08-saved-dashboard-with-cms-chrome.png` |
| 9 | sidebar → **Analytics** again | the hub shows **CONTINUE WHERE YOU LEFT OFF → AH2 QA Dashboard** and General Analytics is now *3 dashboards* | `09-hub-with-new-dashboard-and-recents.png` |
| 10 | *Growth* card → **Create one** (the per-workspace CTA) → **CRM Leads** → **Open in advanced builder** | lands in the existing Explore builder **pre-loaded with CRM Leads**, chrome intact, no error dialog | `10-escape-hatch-explore-with-chrome.png` |
| 11 | (persona granted `group_bi_modeler`, server restarted, re-driven) hub → **＋ Create Report** → **Bookings & Service Orders** | the **Ask in your own words** box now renders above an *OR BUILD IT YOURSELF* divider | `11-wizard-step2-ai-box-visible.png` |
| 12 | type *"total price by service type over the last 6 months"* → **Build it for me** | a **real** OpenAI call (`bi.ai.log` id 27, provider 2, 4 s) returns a config; the wizard materialises it and jumps to step 3 with a live chart and the AI's own title | `12-ai-ask-result-step3.png` |
| 13 | click **Back** | the AI config is visible in the ordinary pickers: measure *Total Price*, break-down *Service Type*, date field *Scheduled Date*, chip **Last 6 months** active — i.e. the user can keep editing it by hand | `13-ai-config-materialized-into-pickers.png` |
| 14 | click ✕ | the wizard closes back to the hub with nothing saved (step 12's report was deliberately not saved) | — |

## Was AI live on vietuat?

**Yes — and it is invisible to the audience the wizard is for.**
`bi.ai.provider` id 2 (OpenAI / gpt-4o-mini) is active, default, and has an
API key, so `bi.ai.is_available()` is `True` for an administrator and the
live `nlq_chart` call in step 12 really did reach OpenAI. But that model's
ACL starts at `biz_bi.group_bi_modeler`, so for a plain **creator** the
probe answers `False` (Phase 1's `biz_bi_cms/models/bi_ai.py` turns the
AccessError into an honest "no") and the box is hidden — steps 5–8 above.
Both halves are captured on purpose. Widening that ACL is a `biz_bi`
decision and out of this phase's sanction.

## Console

`console-log.txt` — the full output per screen. **Zero errors, zero
warnings** on every screen; the single `[issue]` advisory is pre-existing
and measured, not assumed (the wizard contributes zero form fields without
`id`/`name`). It also records, and attributes, the one 502 burst: another
session stopped the Odoo service mid-drive for its own deploy.

## Server-side result

`server-side-rows.txt` — the chart / dashboard / widget / ai-log rows the
drive created, **by id**, including the verbatim `config_json` the wizard
wrote and the exact relative date-range shape
`{"field_id": …, "op": "relative", "value": "last_12_months"}`.

`test-results.txt` — the verbatim `odoo.tests.result` line, the list of
executed test methods, and the migration log line proving
`19.0.1.1.0` ran.

`qa-fixture-cleanup.txt` — everything deleted, and the fresh-cursor proof.
