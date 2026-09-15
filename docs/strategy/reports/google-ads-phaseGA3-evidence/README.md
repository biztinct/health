# GA3 browser evidence — `health_google_ads` 19.0.3.0.0

**Server:** carejiox.com (master `carejiox`) · **Date:** 2026-09-15
**Persona:** `ga3_qa_ops` (uid 9681) — a throwaway clinic operator created for
this pass and **deleted at the end of it** (§3). Groups: `base.group_user`,
`sales_team.group_sale_manager`, `health_crm.group_health_crm_user` +
`…_manager`, `health_base.group_healthcare_sales`,
`…_operations_manager`, `…_base`, catchment Hà Nội. **Deliberately not a
system administrator** — the reporting screens are built for this persona.

**No real Google credential exists anywhere in this pass.** The QA application
carried the throwaway sign-in id
`qa-ga3-throwaway-000000.apps.googleusercontent.com` with the strings
`qa-secret-ga3-throwaway` / `qa-devtoken-ga3-throwaway`, and the account's
stored tokens were `channel_crypto.encrypt(env, 'qa-token')` — real ciphertext
(`chs$1$…`) of a fake string. Google refused them, and that refusal is what
makes step 07 evidence rather than a claim.

**Console:** 0 JavaScript errors and 0 warnings attributable to this phase —
see `console-log.txt`.

---

## 1. The navigation path, click by click

Every screen was reached by clicking. The single literal URL entry is called
out and proves nothing on its own.

| # | File | How it was reached / what it proves |
|---|---|---|
| 01 | `01-login-operator.png` | `https://carejiox.com/web/login` → User ID `ga3_qa_ops` + password. |
| 02 | `02-cms-sidebar-google-ads-leaf.png` | **Log in** → lands on `/bizapp`, the CMS shell. The **Google Ads** leaf sits in **CRM**, between *Web Touchpoints* and *Lead Analysis*. |
| 03 | `03-google-ads-account-list.png` | click **Google Ads** → the account list, inside the CMS chrome. The new **LAST SUCCESSFUL SYNC** column is present and **empty** — nothing has been read yet, and the column says so rather than showing a zero. |
| 04 | `04-campaign-reporting-tab-connected.png` | click the row → tab **Campaign reporting**. The statusbar now carries **Syncing** between *Choose account* and *Connected* (new in GA3). Account currency `VND`, time zone `Asia/Ho_Chi_Minh` — the calendar the figures are counted on. |
| 05 | `05-campaign-figures-section.png` | scrolled to the new **CAMPAIGN FIGURES** section: *Last Successful Sync*, *Last Sync Attempt*, *Sync Asked For*, *Days of Figures Held* **0**, *Enquiries with no matching campaign* **0**, *Fetch Back To* / *Fetched Back To*; the four buttons **Sync now · Open report · Sync history · Fetch older days**; and the two honesty paragraphs (cost per new enquiry is *this system's* number, not Google's; a day with nothing read shows zero). |
| 06 | `06-sync-now-notification.png` | click **Sync now** → the notification *"Sync queued — the numbers refresh within a minute."* and the statusbar moves to **Syncing**. **No HTTP call happened in this request** (rail R7): the button set `sync_requested_at` and nudged the scheduled job, nothing else. |
| 07 | `07-action-required-after-sync.png` | the scheduled job then ran, on its own, and reached Google with the fake tokens. Google answered **HTTP 401 `invalid_client`**, which is `needs_reconnect`: the account moved to **Action required**, and *Reporting Message* reads, in plain words, *"Google refused this request. Try again, and tell the platform operator if it keeps happening."* **That is the honest state, and it is the whole point of the screen.** |
| 08 | `08-campaign-figures-last-attempt.png` | the same section after the failure: *Last Sync Attempt* is stamped, *Last Successful Sync* is still **empty**, and **Sync now** / **Fetch older days** have disappeared (there is nothing to read until somebody signs in again) while **Open report** and **Sync history** remain. |
| 09 | `09-sync-history-run-row.png` | click **Sync history** → one row: *First read · Skipped — sign-in needed · Aug 17 → Sep 15 · 0 campaigns · 0 days written · 0 removed · 1 attempt · `invalid_client`*. The window is the last **30 account-local days** ending today. Opens **inside** the CMS chrome (see §2). |
| 10 | `10-report-empty-zero-vs-unknown.png` | back on the account → **Open report** → the report, inside the chrome, with the filters **Last 30 days** and the grouping **Campaign > Currency** already applied by the button. Honestly empty, and the empty state says *"A day with no figures from Google shows zero spend because nothing has been read for it, not because nothing was spent."* |
| 11 | `11-report-pivot-currency-row.png` | the **Pivot** tab of the same action: the *Campaign > Currency* grouping survives the view switch, so no total can ever add two currencies together (rail R5). |
| 12 | `12-sync-run-form-what-went-wrong.png` | click the run row → the form. Title **First read — 2026-09-15 19:17:00**, the badge **SKIPPED — SIGN-IN NEEDED**, then **WHAT IT READ** (0 / 0 / 0) and **WHAT WENT WRONG** (`invalid_client` plus Google's own words). Every label is a sentence, not an enum name. |
| 13 | `13-channel-center-card-reporting-line.png` | **Channel Center** → the Google Ads card: *Campaign reporting: **ACTION REQUIRED — RECONNECT*** and *"Reporting updated: Not synced"*. Because the newest run is `skipped_reconnect` (not `failed`), the card shows the reconnect state rather than a *"last attempt failed"* suffix — exactly the split rail R8 asks for. |
| 14 | `14-fetch-older-days-wizard.png` | with the account put back to `connected` (§2) → **Fetch older days** → the wizard: *How many days back* **90**, and *"This system normally holds the last 30 days. Older days are fetched in batches of 30 over the next scheduled runs, so Google is never asked for everything at once."* Cancelled — no backfill was queued. |

The one literal URL entry was `/bizapp/action-1789/374`, used to re-open the QA
account after each shell step in §2 — a record the pass had already reached by
clicking twice (steps 02→03).

## 2. The two staged states, named as such

Neither can be reached without a real Google sign-in, and no real Google
credential exists in this session. Both were staged from an `odoo-bin` shell
run through `carejiox-deploy -x`, and both are named here so nothing in the
pack reads as more than it is:

1. **`connected` with tokens** — `access_token_enc` / `refresh_token_enc` set
   to `channel_crypto.encrypt(env, 'qa-token')`, `token_expires_at = False`
   (so the very next call must refresh, which is what reaches Google),
   currency `VND`, zone `Asia/Ho_Chi_Minh`. Steps 04–06 start here.
2. **back to `connected` after the refusal** — only so the wizard in step 14
   could be opened at all; `action_request_backfill` is correctly hidden while
   the account is in `action_required`.

Everything after those two writes is the product's own behaviour: the button,
the scheduled job, the real HTTPS call to Google, the refusal and every screen
that reports it.

## 3. Cleaned up afterwards

`ga3_qa_teardown.py` deleted the QA account, its runs, its campaign rows, its
day rows, the QA application and the QA user, then read the counters back **on
a fresh cursor** (a count on the writing cursor is only a claim about an
uncommitted transaction):

```
FRESH google_ads_platform_config       0
FRESH google_ads_account               0
FRESH google_ads_campaign              0
FRESH google_ads_campaign_day          0
FRESH google_ads_sync_run              0
FRESH res_users ga3_qa_ops             0
```

and independently, through `psql` on all three databases:

```
carejiox           platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
carejiox_template  platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
hhh                platform_config=0 account=0 campaign=0 campaign_day=0 sync_run=0
```

## 4. What was NOT proved here

No real advertising account was read, so **no screenshot in this pack shows a
real campaign, a real spend figure or a real cost per enquiry**. The report,
the pivot and the rollups are proved by the test suite (GA3-T03 … T08, T15),
not by this pass. That needs the real credentials listed in the GA2 report.
