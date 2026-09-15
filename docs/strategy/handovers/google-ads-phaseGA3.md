# GA3 — Google Ads: campaign cache, daily metrics sync, reporting table

**Read with:** `docs/strategy/HANDOVER-CONVENTIONS.md` (binding — §2, §4, §5 esp. §5.1,
§5.9, §5.55, §5.63, §5.74, §5.76, §5.80 **`fields.Integer` is int4**, §5.81 a cron that
ships active must be harmless by default, §5.83 executed-method count, §5.93 pivot
groupbys, §5.178/H78 **a template upgrade switches jobs back on**, H32),
`docs/strategy/google-ads-channel-design.md` §7.2, §8, §12 (GA-T15–T17, T22),
`docs/strategy/handovers/google-ads-phaseGA2.md` + `docs/strategy/reports/
google-ads-phaseGA2-report.md` (the client and account you extend — the report's
deviations are the truth), and GA1's report for the touchpoint field names.

**Modules:**

| Module | Role | Ships to | Version |
|---|---|---|---|
| `health_google_ads` (EDIT) | campaign/day cache, sync engine + cron, report view, rollups, card lines | every database | 19.0.2.0.0 → **19.0.3.0.0** |

No other module is edited. **White-label** and **plain words** rules as before.

---

## 1. Why this phase exists (plain words first)

After GA2 a clinic can connect its advertising account, and the card says "Campaign
reporting: Connected" — but nothing is read. GA3 reads, every day, the last 30 days of
campaign names, spend, clicks and Google-reported conversions into a local cache, and puts
next to them what the CRM knows: how many NEW enquiries each campaign produced and how many
form submissions (including repeat ones from people already in the pipeline). It shows a
cost per new enquiry, computed from our own CRM numbers, labelled as such, because Google's
conversion count uses a different attribution window and need not agree.

Rules the numbers obey (design §8):

- Spend, clicks, impressions and Google conversions come from the cache, on the account's
  local calendar day.
- "New enquiries" counts leads whose FIRST touch was a Google touch on that campaign in the
  range; a submission merged into an older lead is not a new enquiry.
- "Submissions" counts every accepted Google-attributed touch (new or merged), never test
  runs (they are rolled back and never exist).
- Money is never summed across currencies. A campaign with no explicit area mapping shows
  "Spend not allocated to an area" rather than a blended figure.
- A successful sync that returns zero rows is a ZERO; a failed sync leaves the last known
  numbers in place and says "last attempt failed".

Scope in one line: **the reporting the card promised becomes real, honest and revisable.**

## 2. Binding non-goals

- No conversion upload to Google, no ad/budget writes, no Performance-Max asset-group
  metrics, no ad-group or keyword grain — campaign grain only.
- No lifetime totals: the cache holds the rolling window plus whatever backfill an operator
  requested (bounded); every screen names its date range.
- No blended cost per area; no per-area spend for area-restricted staff (v1: report data is
  readable by account-level operators only — design §8's "area-mapped campaigns visible to
  area staff" is deferred and recorded as such).
- No BI dataset (`biz_bi`) — plain views on a SQL-view model, like Lead Analysis.
- No change to GA2's OAuth/refresh kernel; the sync only CALLS the client.
- No edit outside `health_google_ads`.

## 3. Verified plumbing — DO NOT RE-DERIVE

- Google Ads REST `googleAds:search` JSON is **camelCase** and int64 values arrive as
  **strings**: a metrics row looks like
  `{"campaign": {"resourceName": "customers/1/campaigns/2", "id": "2", "name": "…",
  "status": "ENABLED", "advertisingChannelType": "SEARCH"}, "segments": {"date":
  "2026-09-01"}, "metrics": {"impressions": "123", "clicks": "4", "costMicros":
  "1230000", "conversions": 1.5}}`. Fixtures must use these spellings.
- GA2 client: `GoogleAdsClient._search(customer_id, query, login_customer_id)` pages all
  results; `list_campaigns` / `fetch_campaign_days` are declared and raise
  `NotImplementedError` — implement them here. Error class `GoogleAdsError(code,
  retryable, needs_reconnect, detail_redacted)`.
- GA2 account: `reporting_state` enum includes `syncing`/`paused` (unused so far),
  `last_sync_attempt_at`, `last_sync_success_at`, `last_error_code`,
  `reporting_error_redacted`, `account_timezone` (IANA name from Google, e.g.
  `Asia/Ho_Chi_Minh`), `currency_id`, `_internal()`, `_check_operator()`,
  `_reporting_access_token()`, `REPORTING_LOCK_CLASS`.
- GA1 touchpoint fields: `google_ads_origin`, `google_ads_account_id`,
  `google_ads_campaign_id` (Char raw id), `occurred_at` (naive UTC), `company_id`; lead:
  `external_submission_id`, `google_ads_*` first-touch snapshot; the creating touch is the
  one whose `external_event_id == lead.external_submission_id` (`web_lead_service.py`
  `_reconcile_counts` uses exactly this rule).
- SQL-view model precedent: `health_base/models/health_audit_log.py:9-40` (`_auto =
  False`, `init()` with `tools.drop_view_if_exists` + `CREATE OR REPLACE VIEW`).
- Pivot/list/action precedent: `health_web_leads/views/crm_lead_views.xml:316-386`
  (`action_web_leads_funnel`, and §5.93: put the second dimension IN the pivot arch, never
  as a `search_default_` group-by).
- `ir.cron._trigger(at=None)` exists (`/odoo/odoo-server/odoo/addons/base/models/
  ir_cron.py:666`).
- Python 3.10 on the server → `zoneinfo.ZoneInfo` available; `decimal.Decimal` for micros.
- Template rule: after `carejiox-deploy -D carejiox_template -m …`, `select count(*) from
  ir_cron where active` must be 0; if the upgrade re-activated the new cron, run
  `sudo -u postgres psql -d carejiox_template -c "UPDATE ir_cron SET active = false"` and
  say so in the report (runbook §4 step 5 / H78).

## 4. Data model

### 4.1 `google.ads.campaign` (extend)

Add/confirm: `status` Char (ENABLED/PAUSED/REMOVED as Google spells it), `status_label`
compute (plain words: Running / Paused / Removed / Unknown), `advertising_channel_type`
Char, `last_seen_at` Datetime, `source` (`provider` when upserted by sync; a manual row that
the sync later finds is flipped to `provider` and its `name` overwritten with Google's).
Rollups (stored, refreshed by the sync, all readonly): `window_from`, `window_to` (Date),
`spend_30d` Monetary (`currency_id` related to account), `clicks_30d` Integer,
`impressions_30d` Integer, `conversions_30d` Float, `new_enquiries_30d` Integer,
`submissions_30d` Integer, `cost_per_new_enquiry_30d` Float (0.0 when no enquiries),
`cost_per_new_enquiry_display` Char compute ("—" when `new_enquiries_30d == 0`, else the
formatted amount with the currency symbol). Missing rows from a partial sync are never
deleted; a campaign absent from Google keeps its cache and its `last_seen_at`.

### 4.2 `google.ads.campaign.day` (new)

| Field | Definition |
|---|---|
| `account_id` | Many2one required, index, ondelete cascade |
| `company_id` | related `account_id.company_id`, store, index |
| `campaign_id` | Many2one google.ads.campaign, required, index, ondelete cascade |
| `date` | Date, required, index — the ACCOUNT-LOCAL day Google reported (`segments.date`) |
| `currency_id` | Many2one res.currency (copied from the account at write time) |
| `impressions`, `clicks` | Integer (int4 is fine per campaign-day; assert `< 2**31` else store `2**31-1` and set `overflow=True` — §5.80) |
| `overflow` | Boolean |
| `cost_micros` | Char — the exact string Google sent (int64-safe) |
| `spend` | Monetary, stored, computed from `cost_micros` with `Decimal(cost_micros) / Decimal(10**6)` quantized to 6 places → float for storage (exact below 9×10¹⁵ micros; note this bound in the field help) |
| `google_conversions` | Float (fractional) |
| `synced_at` | Datetime |

`init()`: `CREATE UNIQUE INDEX IF NOT EXISTS google_ads_campaign_day_uidx ON
google_ads_campaign_day (account_id, campaign_id, date)`. ACL: read for operators
(CENTER_GROUPS + owner/admin), write/create/unlink `base.group_system` only (the sync runs
sudo). Company record rule.

### 4.3 `google.ads.sync.run` (new; the honesty log)

`account_id`, `company_id` (related stored), `kind` Selection `scheduled|manual|initial|
backfill`, `window_from`, `window_to`, `started_at`, `finished_at`, `state` Selection
`success|failed|skipped_locked|skipped_reconnect`, `attempts` Integer, `campaigns_seen`,
`rows_written`, `rows_removed` Integer, `error_code` Char, `detail_redacted` Char,
`request_id` Char. `_order = 'id desc'`. ACL read operators, write system. Keep the last
200 runs per account (prune inside the cron, oldest first).

### 4.4 `google.ads.campaign.stat` — SQL view (new, `_auto = False`) — kernel (use as-is, then test)

```sql
CREATE OR REPLACE VIEW google_ads_campaign_stat AS (
  WITH tz AS (
    SELECT a.id AS account_id, COALESCE(NULLIF(a.account_timezone, ''), 'UTC') AS zone
    FROM google_ads_account a
  ),
  touches AS (
    SELECT t.google_ads_account_id AS account_id,
           c.id AS campaign_id,
           ((t.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE tz.zone)::date AS day,
           COUNT(*) AS submissions,
           COUNT(*) FILTER (WHERE l.id IS NOT NULL
                              AND l.external_submission_id = t.external_event_id
                              AND l.google_ads_origin IS NOT NULL) AS new_enquiries
    FROM health_lead_touchpoint t
    JOIN tz ON tz.account_id = t.google_ads_account_id
    JOIN google_ads_campaign c
      ON c.account_id = t.google_ads_account_id
     AND c.external_campaign_id = t.google_ads_campaign_id
    LEFT JOIN crm_lead l ON l.id = t.lead_id
    WHERE t.google_ads_origin IS NOT NULL
    GROUP BY 1, 2, 3
  ),
  keys AS (
    SELECT account_id, campaign_id, date AS day FROM google_ads_campaign_day
    UNION
    SELECT account_id, campaign_id, day FROM touches
  )
  SELECT row_number() OVER (ORDER BY k.account_id, k.campaign_id, k.day) AS id,
         k.account_id,
         a.company_id,
         k.campaign_id,
         k.day AS date,
         COALESCE(d.currency_id, a.currency_id) AS currency_id,
         COALESCE(d.impressions, 0) AS impressions,
         COALESCE(d.clicks, 0) AS clicks,
         COALESCE(d.spend, 0.0) AS spend,
         COALESCE(d.google_conversions, 0.0) AS google_conversions,
         COALESCE(t.new_enquiries, 0) AS new_enquiries,
         COALESCE(t.submissions, 0) AS submissions,
         (d.id IS NOT NULL) AS has_metrics
  FROM keys k
  JOIN google_ads_account a ON a.id = k.account_id
  LEFT JOIN google_ads_campaign_day d
    ON d.account_id = k.account_id AND d.campaign_id = k.campaign_id AND d.date = k.day
  LEFT JOIN touches t
    ON t.account_id = k.account_id AND t.campaign_id = k.campaign_id AND t.day = k.day
)
```

Model fields mirror the columns (all readonly): `account_id`, `company_id`, `campaign_id`,
`date`, `currency_id`, `impressions`, `clicks`, `spend` (Monetary), `google_conversions`,
`new_enquiries`, `submissions`, `has_metrics`. `id` is a row number — never store a
reference to it. ACL read for operators only; company record rule. Views: pivot (rows:
`campaign_id` then `currency_id`; cols: `date:month`; measures spend, clicks,
google_conversions, new_enquiries, submissions — `has_metrics` excluded), list (grouped by
campaign by default via the ACTION context `search_default_group_campaign` — group-bys are
fine on a list, §5.93 is about pivots), graph (line: spend and new_enquiries by date),
search (filters: last 30 days (default), last 90 days, this month; group by campaign,
currency, account, date). Action `action_google_ads_campaign_stat` name "Google Ads
report"; a paragraph in the `help` explains: "Cost per new enquiry is shown per campaign
for the last 30 days on the account page. Google conversions and CRM enquiries use
different attribution rules and are not expected to match." Window/freshness: the account
form shows `last_sync_success_at` next to the report button; the list view's header shows
nothing else.

Add to `data/cms_sidebar_items_google_ads.xml` `match_action_xmlids`:
`health_google_ads.action_google_ads_campaign_stat` and `…action_google_ads_sync_runs`,
`match_models` add `google.ads.campaign.stat`.

## 5. The sync engine (`models/google_ads_sync.py`, methods on `google.ads.account`)

Constants: `SYNC_WINDOW_DAYS = 30`, `SYNC_ATTEMPTS = 3`, `SYNC_BACKOFF_SECONDS = (2, 8)`
(cron only), `SYNC_LOCK_CLASS = 0x67617379` ("gasy"), `BACKFILL_MAX_DAYS = 365`,
`BACKFILL_WINDOWS_PER_RUN = 3`, `RUNS_KEPT = 200`.

Client additions (`services/google_ads_client.py`):

```python
Q_CAMPAIGNS = ('SELECT campaign.id, campaign.name, campaign.status, '
               'campaign.advertising_channel_type FROM campaign')
Q_DAYS = ('SELECT campaign.id, segments.date, metrics.impressions, metrics.clicks, '
          'metrics.cost_micros, metrics.conversions FROM campaign '
          "WHERE segments.date BETWEEN '%s' AND '%s'")
```

`list_campaigns(customer_id, login)` → `[{'id': str, 'name', 'status',
'advertising_channel_type'}]`; `fetch_campaign_days(customer_id, login, date_from,
date_to)` → `[{'campaign_id': str, 'date': date, 'impressions': int, 'clicks': int,
'cost_micros': str, 'conversions': float}]` — `date_from/date_to` are `datetime.date`
objects formatted by the client (never user strings), `date_to - date_from <= 366` else
`GoogleAdsError('bad_window')`. Conversions read from `metrics.conversions` only — **the
query is NOT segmented by conversion action** (that would multiply spend rows).

`_sync_window(today_local=None)` → `(date_from, date_to)` = the last 30 account-local
calendar days INCLUDING today, using `ZoneInfo(account_timezone or 'UTC')` on
`fields.Datetime.now()`.

`_sync_reporting(kind='scheduled', window=None)` — the unit of work, one account, called
by the cron and by tests (never by the browser):

1. `pg_try_advisory_xact_lock(SYNC_LOCK_CLASS, id)`; if not acquired → write a run
   `skipped_locked`, return. (Flush first, §5.9.)
2. Require `reporting_state in ('connected', 'syncing')` and `customer_id`; else return
   without a run row.
3. `run = create(kind, window, started_at=now, state='failed', attempts=0)` — created
   FIRST so a crash still leaves an attempt; `last_sync_attempt_at = now`.
4. Fetch phase, up to `SYNC_ATTEMPTS` attempts: `campaigns = client.list_campaigns(...)`,
   `days = client.fetch_campaign_days(...)`; on `GoogleAdsError(retryable)` sleep the
   backoff (only when `kind != 'test'`; tests patch `time.sleep` with a plain function) and
   retry; on `needs_reconnect` → `reporting_state='action_required'`, `last_error_code`,
   `reporting_error_redacted`, run `skipped_reconnect`, return; any other error → run
   `failed` with `error_code`/`detail_redacted`/`request_id`, account `last_error_code`,
   return. **Nothing is written to the cache before both fetches succeeded.**
5. Write phase, inside `with self.env.cr.savepoint():`
   a. upsert campaigns by `(account, external id)` (`source='provider'`, name/status/type,
      `last_seen_at=now`); never delete missing ones.
   b. build the fetched key set `{(campaign_db_id, date)}`; `search` existing day rows of
      this account with `date` in window; delete those whose key is not in the fetched set
      (`rows_removed`); upsert the fetched rows (`rows_written`), `currency_id` = account's,
      `synced_at = now`, `cost_micros` as the string received (validate `^\d{1,20}$`).
   c. refresh the 30-day rollups on every campaign of the account (§4.1) from the cache
      and from the `google.ads.campaign.stat` view (read the view with the same window —
      `new_enquiries`/`submissions` come from there so one definition rules).
   d. account: `last_sync_success_at = now`, `last_error_code = False`,
      `reporting_error_redacted = False`, `reporting_state = 'connected'` (from `syncing`),
      `sync_requested_at = False`.
   e. run: `state='success'`, counters, `finished_at`.
   A failure inside the savepoint rolls back a–e together; the run row (created before the
   savepoint) is then updated to `failed` with the code. Prior cache rows survive.
6. Prune runs beyond `RUNS_KEPT` for this account.

`_cron_sync_reporting()` `@api.model` — iterate `search([('reporting_state','in',
('connected','syncing'))])` sudo; for each: `with self.env.cr.savepoint(): account.
_sync_reporting('scheduled' or 'manual' if sync_requested_at)`; then the backfill queue:
for each account with `backfill_until` set and `backfill_cursor > backfill_until`, up to
`BACKFILL_WINDOWS_PER_RUN` windows of 30 days ending at `backfill_cursor - 1`, each a
`_sync_reporting('backfill', window)`; advance the cursor after each success; clear both
fields when done. Errors per account are contained by the savepoint; the cron never raises.

Cron seed `data/ir_cron.xml`: `ir_cron_google_ads_sync_reporting`, daily, `nextcall` at
03:30 UTC, `active=True`, `noupdate="1"`. Harmless by default (§5.81): with zero connected
accounts it does nothing and logs one info line.

Account actions (operator-gated, company-checked):

- `action_sync_now()` — requires `connected`/`action_required`? No: requires `connected`
  (or `syncing` already → notify "A sync is already queued"); sets `sync_requested_at=now`,
  `reporting_state='syncing'`, then `self.env.ref('health_google_ads.
  ir_cron_google_ads_sync_reporting').sudo()._trigger()`; returns a notification "Sync
  queued — numbers refresh within a minute" with `params.next` reload. **No HTTP in the
  request.** (On the template the cron is inactive; `_trigger` on an inactive cron is a
  no-op — say so in the notification only if `not cron.active`: "Scheduled jobs are off on
  this system.")
- `action_request_backfill()` — opens a tiny wizard `google.ads.backfill.wizard` (`days`
  Integer default 90, max `BACKFILL_MAX_DAYS`) → sets `backfill_until = today_local -
  days`, `backfill_cursor = window_from of the current window`, notifies "Older days will
  be fetched in chunks of 30 over the next runs".
- `action_open_report()` — the stat action with `domain=[('account_id','=',id)]` and
  `context={'search_default_last_30': 1, 'search_default_group_campaign': 1}`.
- `action_open_sync_runs()` — runs list for this account.
- GA2's `action_select_reporting_account(...)`: after `connected`, call the same enqueue as
  `action_sync_now()` with `kind='initial'` semantics (set `sync_requested_at`,
  `reporting_state='syncing'`, `_trigger()`).

Account fields added: `sync_requested_at` Datetime, `backfill_until` Date,
`backfill_cursor` Date, `unresolved_campaign_count` Integer compute (touchpoints of this
account with `google_ads_origin` set whose `google_ads_campaign_id` is empty or matches no
campaign row), `campaign_day_count` Integer compute, `sync_run_ids` One2many.

Card (`_center_card_payload`): reporting row label map adds `syncing` → "Syncing…" (info);
`lines[1]` = "Reporting updated: <since last_sync_success_at | Not synced>" and, when the
newest run failed after a success, append " · last attempt failed (<error_code>)"; when the
newest run is `skipped_reconnect` the row is `action_required` (GA2 already does that).

## 6. Sanctioned edits (exhaustive)

`health_google_ads` (→ 19.0.3.0.0): new `models/google_ads_campaign_day.py`,
`models/google_ads_sync_run.py`, `models/google_ads_campaign_stat.py`,
`models/google_ads_sync.py`, `models/google_ads_backfill_wizard.py`,
`views/google_ads_reporting_views.xml`, `tests/test_reporting.py`,
`tests/test_sync.py`, `tests/test_stat_view.py`; edits to `models/google_ads_account.py`,
`models/google_ads_campaign.py`, `models/channel_center.py`, `services/google_ads_client.py`
(the two methods + constants), `views/google_ads_account_views.xml`, `data/ir_cron.xml`,
`data/cms_sidebar_items_google_ads.xml`, `security/ir.model.access.csv`,
`security/google_ads_security.xml`, `__manifest__.py`, `i18n/vi.po`, `tests/common.py`.

## 7. Safety rails

- R1 **Atomic window replacement**: cache writes happen only after BOTH fetches succeeded,
  inside one savepoint; a failure leaves prior rows intact (T-04/T-05).
- R2 **Never delete a campaign row; never delete a day row outside the fetched window.**
- R3 **Exact micros**: `cost_micros` is the received string; `spend` derives through
  `Decimal`; a 19-digit value survives byte-for-byte (T-07).
- R4 **Local days**: window and touch dates use the account's IANA zone; a touch at
  17:30 UTC on the 14th in `Asia/Ho_Chi_Minh` counts on the 15th (T-08).
- R5 **No mixed-currency sums**: every money-bearing view groups by `currency_id`; the
  pivot arch has `currency_id` as a row (T-11 asserts the arch).
- R6 **One run per account at a time** (advisory lock; T-09 real contention).
- R7 **No HTTP in a browser request**: `action_sync_now` only enqueues (T-10 asserts zero
  client calls and one `_trigger`).
- R8 **Zero vs unknown**: an empty successful run writes a `success` run with
  `rows_written=0` and the card says "Reporting updated: just now"; a failed run keeps the
  old `last_sync_success_at` and the card line says "last attempt failed (code)" (T-12).
- R9 **Operators only** on day/stat/run rows; company rule on all three (T-14).
- R10 **Template stays silent**: after the ritual, `ir_cron` active = 0 there and no
  account/config rows; re-disable if the upgrade re-activated (H78) and report it.
- R11 Provider text through `redact()`; `request_id` is the only raw provider string kept.

## 8. Tests (TransactionCase, `post_install`; HTTP patched at
`google_ads_client._http_post_json`/`_http_get` with plain functions; `time.sleep` patched)

| ID | Design ref | Scenario → result |
|---|---|---|
| GA3-T01 | §5 | Client parsing: camelCase fixture rows (int64 strings, fractional `conversions`) → typed dicts; `campaign.id` kept as `str`; `advertisingChannelType` mapped; a 3-page `nextPageToken` fixture yields all rows. |
| GA3-T02 | §5 | `_sync_window()` for `Asia/Ho_Chi_Minh` at 2026-09-14T17:30Z → `(2026-08-17, 2026-09-15)` (30 days incl. today local); for `UTC` → ends 2026-09-14; unknown zone string → UTC and a logged warning. |
| GA3-T03 | T15 | Happy sync: 2 campaigns × 3 days → 2 campaign rows (`source='provider'`), 6 day rows, run `success` with counters, account `last_sync_success_at` set, `last_error_code` False, rollups filled; a pre-existing MANUAL mapping row for one campaign id is flipped to provider and renamed. |
| GA3-T04 | T15 | Second sync returns revised totals for one day and omits another (campaign, day) inside the window → the revised row updated in place, the omitted row DELETED (`rows_removed=1`); a day row OUTSIDE the window untouched; a campaign absent from Google keeps its row. |
| GA3-T05 | T15 | Page 2 of `fetch_campaign_days` raises HTTP 503 on all 3 attempts → run `failed`, `attempts=3`, `error_code` set, NO cache change (row counts + a sampled value identical), `last_sync_success_at` unchanged, `reporting_state` still `connected`; sleep called with (2, 8). |
| GA3-T06 | T14 | `needs_reconnect` during fetch → run `skipped_reconnect`, account `action_required`, cache untouched, website status unchanged. |
| GA3-T07 | T17 | `cost_micros='12345678901234567890'` → stored string identical; `spend` equals `Decimal('12345678901234.567890')` within float tolerance; `'abc'`/`'-1'` → the row is skipped and counted in `detail_redacted` ("1 malformed row"), run still success. `impressions` 2**31 → stored `2**31-1` + `overflow=True`. |
| GA3-T08 | T17/T22 | Stat view: a lead created by a Google touch (campaign X, account A) at 2026-09-14T17:30Z + a merged second touch from another person's older lead same campaign same UTC instant + one touch whose campaign id matches no campaign row → view row for (A, X, 2026-09-15 local) has `new_enquiries=1`, `submissions=2`; the unmatched touch appears in `account.unresolved_campaign_count` and in no view row. A day with metrics but no touches → `new_enquiries=0`, `has_metrics=True`; a day with touches but no metrics → `has_metrics=False`, spend 0. |
| GA3-T09 | §5 | Lock (REAL): second cursor holds `pg_try_advisory_xact_lock(SYNC_LOCK_CLASS, id)` → `_sync_reporting` writes a `skipped_locked` run and makes no HTTP call; after release, a normal run succeeds. |
| GA3-T10 | §5 | `action_sync_now()` → `sync_requested_at` set, state `syncing`, `ir.cron._trigger` called once (patched plain function), zero HTTP calls; a second press → notification "already queued", no second trigger. As a plain CRM user → `AccessError`. Then `_cron_sync_reporting()` runs it as `kind='manual'` and state returns to `connected`. |
| GA3-T11 | T17 | The stat pivot view arch contains `currency_id` as a `type="row"` field and no measure named `has_metrics`; the list view is grouped by campaign through the action context, not a `search_default_` on the pivot. (Arch assertions via `env.ref(...).arch_db`.) |
| GA3-T12 | T16 | Empty success (0 campaigns) → run `success`, `rows_written=0`, card `lines[1]` starts with "Reporting updated:" and has no "failed"; then a failed run → card `lines[1]` still shows the earlier time AND "last attempt failed (http_503)". |
| GA3-T13 | §5 | Backfill: `days=400` clamps to 365; the cron processes at most 3 windows per run, advances `backfill_cursor`, and clears both fields when the cursor passes `backfill_until`; each window's run has `kind='backfill'`; windows never overlap the rolling window. |
| GA3-T14 | T19 | ACL/rules: `group_health_crm_user` cannot read day/stat/run rows (`AccessError`); a company2 operator reads none of company 1's rows (0 results, no error); the operator cannot `create` a day row directly. |
| GA3-T15 | §4.1 | Rollups: after T-03's data, campaign X `spend_30d`, `clicks_30d`, `new_enquiries_30d`, `submissions_30d` equal the view sums for the window; `cost_per_new_enquiry_30d = spend/new` and its display is "—" when new = 0. |
| GA3-T16 | §5 | Cron isolation: two accounts, the first one's fetch raises a non-retryable error, the second succeeds in the same `_cron_sync_reporting()` call; run prune keeps ≤ 200 rows per account. |
| GA3-T17 | white-label | `fields_get` of the four new models contains no "Odoo"; status labels are plain words. |

Existing suites stay green (`/health_google_ads` GA1+GA2, `/health_web_leads`,
`/health_care_command_channels`).

## 9. Deploy + verify

Same ritual as GA2 §8 (`-m health_google_ads` on `carejiox`, then `-D carejiox_template`,
then `-D hhh`), then:

```bash
ssh VietUcUAT 'sudo -u postgres psql -d carejiox_template -Atc "select count(*) from ir_cron where active"'   # 0 — if not, UPDATE ir_cron SET active=false on the template and REPORT it (H78)
ssh VietUcUAT 'sudo -u postgres psql -d carejiox -Atc "select id, active, nextcall from ir_cron where name ilike '"'"'%Google Ads%'"'"'"'
ssh VietUcUAT 'sudo -u postgres psql -d hhh -Atc "select id, active from ir_cron where name ilike '"'"'%Google Ads%'"'"'"'
ssh VietUcUAT 'carejiox-deploy -m health_google_ads -t /health_google_ads,/health_web_leads,/health_care_command_channels'
```

Browser evidence (`docs/strategy/reports/google-ads-phaseGA3-evidence/`): as the operator
persona on https://carejiox.com, CRM → Google Ads → a QA account you drive to `connected`
by SEEDING tokens through the internal context in an `odoo shell` script run via
`carejiox-deploy -x` (fake `chs$1$` ciphertext of the string `qa-token` encrypted with
`channel_crypto.encrypt` on the master — never a real credential) → press **Sync now** →
the notification → wait for the cron (or trigger it from the shell script) → the run list
shows `failed` with a code (Google refuses fake tokens: `needs_reconnect` → the account
reads "Action required — reconnect"; screenshot the card and the run row: that IS the
honest state) → **Open report** (empty, zero-vs-unknown wording visible) → Sync history →
delete the QA account, runs, config; fresh-cursor zero counts on `google_ads_account`,
`google_ads_sync_run`, `google_ads_campaign_day`, `google_ads_platform_config`. If REAL
credentials are available in the session, run the real initial sync instead and screenshot
real campaign rows, the report pivot and the rollups; state which it was.

## 10. Report-back

1. Commits, versions on the three databases, cron rows per database (id/active), template
   count after re-disable if needed.
2. Deviations with reasoning (in particular anything in the SQL-view kernel you had to
   change to make PostgreSQL accept it — quote the final SQL).
3. Verbatim test result lines + executed-method counts.
4. The live capability table; whether any real sync ran; the exact date window the cache
   holds.
5. Ledger candidates (e.g. `AT TIME ZONE` with a column zone, cron `_trigger` on an inactive
   job, template cron re-activation observed or not).
6. What remains for the owner: real credentials (from GA2's list), the choice of campaigns
   → area mappings (`catchment_id`) and utm campaign links, and whether a 12-month
   backfill should be requested once connected.
