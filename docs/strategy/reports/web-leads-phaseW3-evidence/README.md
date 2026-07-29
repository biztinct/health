# Phase W3 browser evidence — `health_web_leads` 19.0.4.0.0

**Server:** care.biztinct.com (vietuat) · **Date:** 2026-07-29
**Persona:** `crm` (uid 40) — `base.group_user`, `sales_team.group_sale_manager`
("Administrator" under Sales), `health_crm.group_health_crm_user` +
`…_manager`, `health_base.group_healthcare_sales`, `…_operations_manager`,
`…_base`, `catchment_province_id = 1`. Group membership read from
`res_groups_users_rel` on the live database, not from the addon XML
(ledger §5.88). Deliberately **not** a system administrator.

**Console:** zero errors and zero warnings on every screen captured
(`list_console_messages` filtered to error+warn returned nothing).

**Binding QA rule honoured (handover §6):** *no* conversion was driven, and
**no consent, patient, lead or touchpoint row was created in live data.** The
bridge is proven by the test transcript only. Post-QA counts in the report,
§3(5) — every one of them unchanged, and nothing at all was created in the
three hours around the drive.

## The navigation path, click by click

Every screen was reached from the CMS shell landing page
(`https://care.biztinct.com/bizapp`) by clicking. No deep links.

| # | File | How it was reached / what it proves |
|---|------|-------------------------------------|
| 01 | `01-cms-sidebar-two-new-leaves.png` | landing → the CRM sidebar now carries **Campaign Review** (`fa fa-bullhorn`, seq 22) and **Lead Analysis** (`fa fa-bar-chart`, seq 23) after *Web Touchpoints* (21). Ledger §5.69: a backend menuitem alone would have made both surfaces deep-link-only for this persona. Both are leaf siblings — *Contacts*, *Web Touchpoints* and *Channel Center* all still navigate. |
| 02 | `02-campaign-review-list.png` | click **Campaign Review** → the action opens for a CRM manager with no `AccessError`, showing the nocontent help *"Every campaign string the website sent is already in the CRM register"*. **Honestly empty**: vietuat holds 0 touchpoints, because the WordPress relay has never delivered (see the report's data-honesty note). |
| 03 | `03-lead-analysis-list-grouped.png` | click **Lead Analysis** → the list opens over ALL leads this persona can see (295: 3 + 124 + 166 + 1 + 1) with the list / pivot / graph switcher in the top right. |
| 04 | `04-lead-funnel-pivot.png` | **Pivot** → real grouped counts. Rows = **city** (Hà Nội 2, TPHCM 1, **None 292**) with **Contact Status** nested under each; columns = **mode of contact**, which has exactly one value: **Phone Call**. Total 295. This is the data-honesty baseline the phase exists to make visible — 99% hand-keyed phone, 292 of 295 leads with no city — and the web column starts at zero. |
| 05 | `05-touchpoints-unmatched-campaign-filter.png` | **Web Touchpoints** → search panel → the new **Unmatched campaign** filter sits under *Unknown City*. |
| 06 | `06-lead-hub-source-modal-consent-bridge.png` | **Lead Analysis → a lead** → the Lead Hub → the **Source** spoke → the modal now carries **Consent Bridge** (readonly, empty on this non-web lead) directly under *City Conflict*. This is the §5.91 surface the ops persona actually opens; closed with **Discard**, nothing saved. |
| 07 | `07-lead-funnel-graph.png` | **Graph** → stacked bar by city, one series (*Phone Call*), same 295. |

## The list-header button, and why there is no screenshot of it

`Link seeded campaigns` is a list `<header>` button: it renders only when at
least one row is SELECTED. vietuat holds **zero** `health.lead.touchpoint`
rows, so selecting one would have meant creating live rows (a touchpoint
requires a `lead_id`) — which the handover forbids for QA.

It was proven the honest way instead, through uid 40's own browser session:

```js
get_views([[false,'list'],[false,'search']])   // as uid 40, live RPC
→ { button_visible_for_uid40: true,
    button_string: 'string="Link seeded campaigns"',
    unmatched_filter:  true,
    unmatched_string:  'string="Unmatched campaign"' }
```

That is exactly what the group gate is: the button survives view
post-processing for this persona's groups. Its behaviour is T8; its refusal
for a receptionist is T9.

## Pre-existing, not ours

Clicking **Contacts → All Dates** raises the dialog *"Sorry, CRM (id=40)
doesn't have 'read' access to: Contact (res.partner)"*. This is the exact
defect the W2.5 report already filed (§8 item 1, confirmed live in the W2.5
review addendum): core Odoo reads `base.partner_root` unsudo'd and this
database's `res.partner` rules deny uid 40 partner id 1. Nothing in W3 touches
`res.partner` reads. It is why screen 06 was reached through **Lead Analysis**
rather than through Contacts — a routing detail, not a bypass: both land on
the same Lead Hub. It still deserves its own remediation ticket.
