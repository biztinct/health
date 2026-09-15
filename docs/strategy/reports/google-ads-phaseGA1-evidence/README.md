# GA1 browser evidence — `health_google_ads` 19.0.1.0.0

**Server:** carejiox.com (master `carejiox`) · **Date:** 2026-09-15
**Persona:** `ga1_qa` (uid 9142) — a scoped QA user created for this pass with
**exactly the live `crm` persona's seven groups** (read off `res_groups_users_rel`
for uid 40, not from addon XML — ledger §5.88): `base.group_user`,
`sales_team.group_sale_manager`, `health_crm.group_health_crm_user` +
`…_manager`, `health_base.group_healthcare_sales`, `…_operations_manager`,
`…_base`, catchment TPHCM. **Deliberately NOT a system administrator.**

Why a new persona rather than `crm` itself: no password for `crm` (or for the
admin) was available in the implementing session, and the handover asks for the
tenant persona where possible. The QA user was deleted at the end of the pass
and the deletion verified on a fresh cursor (§4 below).

**Console:** **zero errors and zero warnings on every screen** — the full
console (`includePreservedMessages`, unfiltered, across all three navigations)
returned exactly one entry, a generic DevTools *issue* hint
(`A form field element should have an id or name attribute`) raised by the CMS
shell's own search box. **No pre-existing error to flag on these screens**; in
particular the T-002 chatter `AccessError` dialog known for the `crm` persona
(`docs/strategy/open-tickets.md`) did **not** appear on the Google Ads account
form, whose chatter opened and posted normally.

## The navigation path, click by click

Every screen was reached by clicking, starting from the login page. No deep
links were used for any step that the flow itself provides — the two
`navigate_page` calls in the transcript (§“note” below) only re-entered a page
the pass had already reached by clicking, after a mid-pass redeploy.

| # | File | How it was reached / what it proves |
|---|------|-------------------------------------|
| 01 | `01-login.png` | `https://carejiox.com/web/login` → User ID `ga1_qa` + password |
| 02 | `02-bizapp-landing.png` | **Log in** → lands on `/bizapp` (Operations Center), the CMS shell — NOT `/odoo`. The **Google Ads** leaf is in the CRM sidebar at sequence 22, between *Web Touchpoints* (21) and *Lead Analysis* (23), with the `fa fa-google` icon. Every neighbouring leaf still navigates, so the seed is a SIBLING, not a child (ledger §5.69a). |
| 03 | `03-channel-center-google-ads-card.png` | click **Channel Center** → the grid. The **Google Ads** card is the 6th rendered card and sits **immediately after Facebook**. Chip *SETUP NEEDED*; tagline *"Leads from your advertising campaigns"*; three capability rows — *Website leads · Setup needed*, *Campaign reporting · Not connected*, *Google lead forms · Unavailable for healthcare ads*; two lines — *Last website lead: No leads received yet*, *Reporting updated: Not synced*; buttons **Set up Google Ads** and **View leads**. No "Sent", no "Reply", no composer. DOM read: card order `[zalo, call, email, whatsapp, fb, google_ads, telegram, webchat]`, accent `--cv: #1a73e8`. |
| 04 | `04-account-list-in-cms-chrome.png` | click **Set up Google Ads** → `doAction` opens `health_google_ads.action_google_ads_accounts` **INSIDE the CMS chrome**: sidebar intact, the **Google Ads** leaf highlighted, breadcrumb *Channel Center / Google Ads*. Honestly empty, with the nocontent help *"Set up Google Ads — Add an advertising account so enquiries that come from your Google ads are recognised as such."* |
| 05 | `05-account-form-new.png` | click **New** → the account form: header buttons *Test the website pipeline* / *View leads* / *View touches*, a readonly `reporting_state` statusbar pinned at **Not connected**, and four tabs (Overview, Website leads, Campaign reporting, Google lead forms). |
| 06 | `06-website-leads-tab-final-url-suffix.png` | name + customer id `1234567890` typed → tab **Website leads**. The **Final URL Suffix** renders with the copy-to-clipboard widget and already carries `&h19_gads_customer_id=1234567890`; no `{campaignname}`; no secret. Both explanatory paragraphs render, including the honest *"checks this system only… A full round trip from the website becomes available once the website connection piece is installed."* |
| 07 | `07-account-saved-connector-linked.png` | pick **Website connector** → **Save**. Record id **92**. *Website Leads* flips **Setup needed → Ready for test** and the **Open website connector** button appears. |
| 08 | `08-website-test-notification.png` | click **Test the website pipeline** → sticky notification *"Google Ads: website pipeline OK. Pipeline OK — a Google ad click on form 15838 would be recorded as a Google Ads enquiry, **matched to this account**. Nothing was saved…"*. Evidence written: *Last Successful Test* `Sep 15, 12:56 PM`, *Test Kind* **Server pipeline check**, *Last Test Result* the redacted one-liner. Status flips to **Test passed; awaiting live lead / Partially connected**. *Website Enquiries* stays **0** and *Last Website Lead* stays empty — only a real lead moves those. **Run as the non-admin operator persona**, which is what the `health.lookup.value` ACL fix (report §3 D4) made possible. |
| 09 | `09-chatter-test-logged.png` | scroll down → the chatter is at the **bottom, full width** (never a side column) and carries exactly **one** test message plus the creation note. |
| 10 | `10-view-leads-filter-chip.png` | click **View leads** → the filter chip reads **"First source Google Ads"**. |
| 10b | `10b-view-leads-sample-data-before-fix.png` | **A defect this pass found and fixed.** The same screen rendered **ten greyed-out invented people** (`john.miller@…`, Carrie Helle, Wendi Baltz …). DOM read: `o_view_sample_data = true`, real rows = 0 — Odoo's sample-data placeholder, inherited from the shared opportunity list's `sample="1"`. Harmless decoration elsewhere; on a screen reached one click after a card that says *"No leads received yet"* it reads as ten enquiries the ads produced. Fixed by a primary list view in `health_google_ads` that clears the attribute, plus pinning the same views on `action_view_leads()`. |
| 11 | `11-view-leads-honest-empty.png` | after the fix + a three-database redeploy, the same click: **no sample rows, 0 real rows**, filter chip still *First source Google Ads*. DOM read: `{sample: false, rows: 0, facets: ["First source Google Ads"]}`. |
| 12 | `12-card-after-test-partially-connected.png` | back to **Channel Center** → the card now reads chip **PARTIALLY CONNECTED**, resource line *"GA1 QA account (delete me) — 1234567890"*, *Website leads · **Test passed; awaiting live lead***, *Campaign reporting · Not connected*, *Google lead forms · Unavailable for healthcare ads*, *Last website lead: No leads received yet*. Buttons **Manage** + **View leads**. **The honest chip** — see the report's deviation D6: the handover's §9 script predicted "Setup needed", its own §4.2 defines this state as `partial`; §4.2 is what is implemented, and the capability row underneath keeps the claim honest (never "Receiving", never "Connected"). |
| 13 | `13-google-lead-forms-tab-policy.png` | tab **Google lead forms** → *Google Lead Forms: **Unavailable for healthcare ads*** (readonly for this non-system persona), the policy paragraph *"Google does not allow healthcare advertisers to use Google-hosted lead forms. Website leads and campaign reporting work without them."*, and the working policy link. **No bypass switch anywhere on the screen.** |

*Note on the two `navigate_page` calls:* a redeploy landed between steps 10b and
11, which dropped the SPA's in-memory route. The session survived; the pass
re-entered `/bizapp` and then reached the account **by clicking the sidebar leaf
and the list row**, exactly as in steps 02→04. The one literal URL entry
(`/bizapp/action-1789/92`) re-opened a record the pass had already opened by
clicking twice before; no step was proven by a deep link that skips a flow.

## Server-side rows this pass created, by id

| Row | id | What happened to it |
|---|---|---|
| `google.ads.account` "GA1 QA account (delete me)" | **92** | created (step 05–07), tested (08), **unlinked** at teardown |
| `mail.message` on that account | 2 rows | went with the account |
| `res.users` `ga1_qa` (+ its partner) | **9142** | created before the pass, **unlinked** at teardown |
| `crm.lead` | none | the synthetic test rolls back; count 481 before **and** after |
| `health.lead.touchpoint` | none | count 0 before **and** after |

**Deleted, not archived** (handover §9): the customer-id unique index is
database-wide and ignores `active`, so an archived QA row would have reserved
`1234567890` permanently.

## Fresh-cursor verification after teardown

Run in a separate `psql` session, after the shell that made the change had
exited (ledger §5.34 — never trust a revert from the cursor that made it):

```
[carejiox]           gads_accounts 0 | gads_campaigns 0 | leads 481 | touchpoints 0 | qa_user 0 | gads_chatter 0
[carejiox_template]  gads_accounts 0 | gads_campaigns 0 | leads   0 | touchpoints 0 | qa_user 0 | gads_chatter 0
[hhh]                gads_accounts 0 | gads_campaigns 0 | leads   0 | touchpoints 0 | qa_user 0 | gads_chatter 0
```

`leads 481` on the master is the pre-QA count, measured before the test button
was pressed. Nothing was created and nothing was left behind on any database.

## Screenshots created outside this folder

None. Every capture in this pass was written directly into this folder.
