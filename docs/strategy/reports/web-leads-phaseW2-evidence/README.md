# Phase W2 browser evidence — `health_web_leads` 19.0.2.0.0

**Server:** care.biztinct.com (vietuat) · **Date:** 2026-07-29
**Persona:** `crm` (uid 40) — Healthcare: Sales + Operations Manager + CRM
User + CRM Manager + Administrator. A real ops account, not a fixture.
**Console:** clean on every screen. The only message across the whole drive is
one pre-existing DevTools *issue* notice ("A form field element should have an
id or name attribute"), which predates this phase and is not an error.

## The navigation path, click by click

Every screen below was reached from the **CMS shell landing page**
(`https://care.biztinct.com/bizapp`) by clicking, never by a deep link. That
matters here more than usual: this phase found that the surface the handover
named is *not* the surface this persona reaches (see report §5, D1).

| # | File | How it was reached |
|---|------|--------------------|
| 01 | `01-cms-contacts-list.png` | landing → sidebar **CRM › Contacts**. The captured lead shows Agent = *Website Lead Relay (service)* — it was written by the narrowed service account over the public API, not by a human. |
| 03 | `03-cms-contacts-web-filters.png` | same screen → search-bar caret. **Needs review (web) · City conflict · Web leads** under Filters, **City Source** under Group By. |
| 04 | `04-cms-contact-form-web-attribution-tab.png` | click the lead row → the **Web Attribution** tab (5th) → Triage / Pages groups, showing City Source = *Form Location Field*, Web Form ID = 15838, External Submission ID = `w2-smoke-real-0001`. |
| 05 | `05-cms-contact-form-touchpoints.png` | same form, scrolled → Campaign detail / Consent claim / Click identifiers / **Touchpoints**: two rows, the created touch (11:59) and the merged one (12:00). |
| 06 | `06-lead-hub-spokes.png` | `/odoo/action-1357` (**Sales & CRM › All Contacts**) → group *Initial Contact* → the lead row → the Lead Hub. |
| 07 | `07-lead-hub-source-modal.png` | hub → **Source** spoke. City Source, Web Form ID, Needs Web Review, City Conflict appended after Vietnamese Channel, modal still modal-small. |
| 08 | `08-cms-sidebar-web-touchpoints-list.png` | landing → sidebar **CRM › Web Touchpoints** (the new `cms.sidebar.item`). Default filter *Form Submissions*; Contacts and Care Command still navigate afterwards (ledger §5.69a checked by hand). |
| 09 | `09-touchpoint-form-readonly.png` | that list → a row. Read-only throughout, raw payload visible under its own tab, and the breadcrumb reads *Website Form Submission · 2026-07-29 03:15:00* rather than `health.lead.touchpoint,98`. |

`02-lead-hub.png` is the same lead opened on the CMS contact form before the
Web Attribution tab shipped — kept as the "before" frame for D1.

## Server-side rows these screens were reading

```
crm_lead 1342 | 01 032422026 | Web: W2 SMOKE TEST | phone 0900000299
  catchment Hà Nội | city_source form_location | web_form_id 15838
  external_submission_id w2-smoke-real-0001 | web_needs_review f | city_conflict f
  create_uid 6103 (svc_web_leads — the NARROWED service account)

health_lead_touchpoint 97 | lead 1342 | form_submit | wordpress
  occurred_at 2026-07-29 02:30:00  received_at 2026-07-29 01:59:55  (created)
health_lead_touchpoint 98 | lead 1342 | form_submit | wordpress
  occurred_at 2026-07-29 03:15:00  received_at 2026-07-29 02:00:17  (merged)
```

## QA fixtures removed

Deleted after the drive and re-verified in a **fresh psql cursor** (ledger
§5.34): 0 leads, 0 touchpoints, 0 care.conversation rows, 0 temporary OAuth
clients, 0 heartbeat activities, 0 heartbeat parameter changes.

The 20 `api.audit.log` rows are **kept on purpose** — the log is append-only
evidence, not a fixture, and those rows are the L2 proof in report §4.
