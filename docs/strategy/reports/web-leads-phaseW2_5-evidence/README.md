# Phase W2.5 browser evidence — `health_web_leads` 19.0.3.0.0

**Server:** care.biztinct.com (vietuat) · **Date:** 2026-07-29
**Persona:** `crm` (uid 40) — `health_crm.group_health_crm_manager`,
`health_crm.group_health_crm_user`, `health_base.group_healthcare_sales`,
`…_operations_manager`, `…_base`, `sales_team.group_sale_manager`,
`base.group_user`. Deliberately **not** a system administrator and **not** a
user administrator: uid 40 holds exactly ONE of the three operator groups, so
the ACL rows and the group-gated header buttons are being proven, not
bypassed. Group membership read from `res_groups_users_rel`, not from the
addon XML (ledger §5.88).

**Console:** one pre-existing DevTools *issue* notice
(`Incorrect use of <label for=FORM_ELEMENT>`, count 5) and **zero errors** on
every screen. See "Pre-existing, not ours" below for the one dialog that does
appear.

## The navigation path, click by click

Every screen was reached from the CMS shell landing page
(`https://care.biztinct.com/bizapp`) by clicking. No deep links.

| # | File | How it was reached / what it proves |
|---|------|-------------------------------------|
| 01 | `01-cms-sidebar-website-connector.png` | landing → the sidebar now carries **CRM › Website Connector** (`fa fa-globe`, sequence 13) between *Channel Center* (12) and *Contacts*. Ledger §5.69: a backend menuitem alone would have made the whole phase deep-link-only. Channel Center and Contacts still navigate afterwards — the new item is a leaf sibling, not a child. |
| 02 | `02-connector-list-empty.png` | click it → the list action opens for a CRM manager (no `AccessError`), empty, with the *Connect the website in a few minutes* nocontent help. |
| 03 | `03-connector-form-draft.png` | **New** → the form before anything exists. Header offers only *Get credentials* and *Test pipeline*; statusbar sits on **Not connected**; the WordPress-configuration group is hidden; the health strip already reads the truth — *No submission ever received — the website side is not live yet.*; both city maps are pre-filled from the live `ir.config_parameter` rows. |
| 04 | `04-connector-saved-draft.png` | **Save** → record 23. Chatter at the bottom, full width. |
| 05 | `05-secret-shown-once-redacted.png` | **Get credentials** → the sticky show-once notification. **The secret is blacked out in the DOM before the screenshot was taken; the raw capture was deleted, not committed.** Behind it: the statusbar has moved to *Credentials issued*, the header now reads *Rotate secret / Test pipeline / Disconnect*, and OAuth Client resolved to **WordPress pkgdvietuc** with client id `b14edb5f…740a` — i.e. **client 122 was ADOPTED, not duplicated** (chatter: "Provisioning adopted the existing service account and OAuth client — nothing was duplicated."). |
| 06 | `06-connector-credentials-issued.png` | reload → the paste-ready `wp-config.php` block rendered as a monospace multi-line block (the fix described in the report, §5 D3), carrying the client id and the literal placeholder `<the secret you copied when it was shown>`. The pre-existing `res.partner` dialog is visible in this frame; see below. |
| 07 | `07-test-pipeline-ok.png` | **Test pipeline** → *"Pipeline OK — a submission on form 15838 would create a lead in Hà Nội (city from: Form ID Map). Nothing was saved."* plus the honest second line about HTTP auth. The button tooltip is in frame. |
| 08 | `08-disconnect-confirm.png` | **Disconnect** → the confirm dialog ("The OAuth client is archived, not deleted"). |
| 09 | `09-connector-disconnected.png` | confirmed → header collapses to *Test pipeline / Reconnect*, statusbar shows **Disconnected**. `gateway_oauth_client.active` for id 122 verified `f` in psql at this point. |
| 10 | `10-connector-reconnected.png` | **Reconnect** → notification, and the header/statusbar return to *Credentials issued* **without a manual reload** (the `params.next` follow-up — report §5 D4). |
| 11 | `11-city-map-validation.png` | typed `{"15838": "SGN"}` into Form → City Map and saved → *`The Form → City map entry "15838" maps to "SGN", which is not a city. Use "HN" for Hà Nội or "HCM" for Hồ Chí Minh.`* The parameter was re-read from psql immediately afterwards and was **unchanged**. |
| 12 | `12-heartbeat-on-watcher-visible.png` | ticked **Daily Delivery Alert** and saved → the Alert Watcher field appears, chatter logs *"Daily delivery alert switched ON by CRM."*, and `web_leads.heartbeat_enabled` = `True` in psql. |
| 13 | `13-rotate-secret-confirm.png` | **Rotate secret** → the confirm dialog warning that the current secret stops working immediately. |
| 14 | `14-final-state-credentials-issued.png` | after the final rotation (redacted) — the state the tenant is left in. |

## Server-side rows behind these screens

```
web_leads_connector   id 23 | Website connector | company 1 | oauth_client 122
gateway_oauth_client  id 122 | WordPress pkgdvietuc | active t | user 6103 | has_secret t
res_users             id 6103 | svc_web_leads | active t        (ADOPTED, not created)

ir_config_parameter
  web_leads.form_city_map      {"15838": "HN", "15670": "HCM"}      (unchanged)
  web_leads.url_city_map       {"/lien-he-hanoi/": "HN", …}          (unchanged)
  web_leads.heartbeat_enabled  False   ← the STRING, row still exists (§5.36)
  web_leads.heartbeat_user_id  (empty) ← row still exists
```

## Test-pipeline residue (rail R2)

The button was pressed four times across the drive (twice failing before the
D3 fix, twice succeeding). Counted in psql afterwards:

```
leads 476 | touchpoints 0 | care_conversations 170
crm_lead WHERE external_submission_id LIKE 'connector-test-%'          → 0
health_lead_touchpoint WHERE external_event_id LIKE 'connector-test-%' → 0
crm_lead WHERE contact_name = 'Kiểm tra kết nối'                       → 0
crm_lead WHERE phone = '0900000000'                                    → 0
```

`leads` and `care_conversations` are the live totals, identical before and
after. Nothing the synthetic submission touched survived its savepoint.

## About the secret in these screenshots

Rotating a secret on this connector rotates the secret of the **live** OAuth
client 122. That was checked to be harmless before the first click and the
check is recorded here: `health_lead_touchpoint WHERE source_system =
'wordpress'` was **0** and `crm_lead WHERE external_submission_id IS NOT NULL`
was **0** — the WordPress relay has never delivered a single submission, so no
working configuration depended on the old value. The secret was then rotated
once more at the end of the drive and that value discarded, so the string
shown mid-session is dead. Nobody holds a secret for client 122 today, which
is exactly the state before this phase; whoever configures the plugin will
press **Rotate secret** and copy the value then.

## Pre-existing, not ours

Opening **any** chatter as uid 40 raises a dialog:

> Sorry, CRM (id=40) doesn't have 'read' access to: Contact (res.partner)

The traceback is core Odoo, not this module:

```
addons/mail/models/models.py:557 _message_get_suggested_recipients_batch
    ban_emails = [self.env.ref('base.partner_root').email_normalized]
→ AccessError on res.partner
```

Measured, not assumed: `res.partner.read([1])` as uid 40 raises the same
`AccessError` on its own, and the identical `/mail/data` request against a
`crm.lead` thread (id 1219) fails in the same method (line 548). Every
`mail.thread` form is affected for this persona; it is a `res.partner` record-
rule / multi-company condition on this database and is **out of scope for
W2.5**. Flagged in the report as a follow-up.
