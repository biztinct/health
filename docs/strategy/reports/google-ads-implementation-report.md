# Google Ads integration — implementation report (GA1–GA3)

Date: 2026-09-15. Orchestrated by Fable (design + handovers), implemented by Opus agents
per phase, each self-reviewed against its handover's rails and test table (the stream runs
the no-Fable-bulk-review model). Per-phase reports carry the full detail:
`google-ads-phaseGA1-report.md`, `google-ads-phaseGA2-report.md`,
`google-ads-phaseGA3-report.md`, each with an evidence folder beside it.

## 1. Commits and deployed state

| Item | Value |
|---|---|
| Design baseline | `551c9c22` (design docs, other session) |
| GA1 | `faee5a2f` feat(google-ads): GA1 — acquisition card + website-lead attribution |
| Docs | `7ddc0aaa` GA2/GA3 handovers + ledger §5.183–§5.184 |
| GA2 | `e827698d` feat(google-ads): GA2 — reporting sign-in, encrypted credentials, read-only client |
| Cross-stream fix | `ce224fb7` test(channels): two stale literals broken by `03103e07` (VoIP24h fail-safe, other session) |
| Docs | `101c7f0b` ledger §5.185–§5.188 |
| GA3 | `57ffd5e2` feat(google-ads): GA3 — campaign cache, daily sync, reporting table |
| Final docs | this report + ledger §5.189–§5.194 |

Unrelated concurrent work preserved: `03103e07` ("Make VoIP24h setup fail-safe") landed on
the branch between GA1 and GA2 and is untouched apart from the two test literals above.

Deployed (shared addons tree, every database upgraded in one sitting per phase):

| Database | `health_google_ads` | `health_care_command_channels` | `health_web_leads` | Google Ads crons |
|---|---|---|---|---|
| `carejiox` (master, carejiox.com) | 19.0.3.0.0 | 19.0.12.3.0 | 19.0.5.0.0 | 159 + 160 active |
| `carejiox_template` | 19.0.3.0.0 | 19.0.12.3.0 | 19.0.5.0.0 | 79 + 80 inactive; **0 active crons** |
| `hhh` (hhh.carejiox.com) | 19.0.3.0.0 | 19.0.12.3.0 | 19.0.5.0.0 | 79 + 80 active |

The template holds 0 rows of platform config / account / campaign / day / sync-run; no
credential of any kind is stored on any database. Practice clones `vietuat` and
`codex_fb_center_reply` were never touched. `/web/login` answers 200 for both hostnames.

## 2. What was built, by phase

**GA1 — card + website attribution.** `health_google_ads` (new): `google.ads.account`,
`google.ads.campaign` (manual mapping rows), attribution fields on `crm.lead` and
`health.lead.touchpoint` (account, customer/campaign/ad-group/creative ids as strings,
origin, match status, time basis), pure classification helpers, company-safe account
resolution (explicit customer id → unique campaign mapping → unmatched; never first-of-many),
first-touch immutability on merge, CRM filters "First source Google Ads" / "Google Ads
influenced", the rolled-back server pipeline test with stored evidence, EN/VI views, CMS
sidebar leaf. Seams added: `_center_extra_cards()` hook + `external_action` card dispatch in
`health_care_command_channels`; `_lead_extra_vals`/`_touchpoint_extra_vals` hooks, the
never-persisted `wbraid`/`gbraid` fix and a stored touchpoint `company_id` in
`health_web_leads`.

**GA2 — reporting sign-in.** `google.ads.platform.config` (operator-only; client id/secret +
developer token encrypted with the channel recipe), `google.ads.oauth.session` (hashed
single-use state, PKCE, 10-minute expiry, purge cron), callback served by the existing
`/channel_hub/oauth/callback/<provider>` route through an ORM override of
`care.channel.oauth.session._handle_callback` (zero edits to the channels module), token
refresh under an advisory lock, account discovery including manager → child enumeration,
validation with the manager context, duplicate-binding refusal across companies,
reconnect/disconnect (local tokens only, no revoke). Read-only client pinned to **API v25**
(released 2026-07-22, sunset August 2027, per Google's sunset-dates page read 2026-09-15).

**GA3 — reporting cache and report.** `google.ads.campaign.day` (exact `cost_micros` string
+ Monetary spend via Decimal), `google.ads.sync.run` (every attempt logged: success / failed /
skipped-locked / skipped-reconnect), SQL view `google.ads.campaign.stat` (day grain in the
account's own time zone; new enquiries = leads whose creating touch was a Google touch;
submissions = every Google-attributed touch incl. merges), atomic 30-day window replacement
(nothing written until both fetches succeed; stale rows inside the window removed, nothing
outside touched, campaigns never deleted), 3 attempts with backoff in the cron only, "Sync
now" enqueues via `ir.cron._trigger()` (no HTTP in a browser request), bounded backfill
(≤ 365 days, 3 windows per run), 30-day rollups per campaign incl. cost per new enquiry
(dash when zero), list/pivot/graph report grouped by currency, sync history. Nightly job
03:30 UTC; harmless with zero connected accounts.

## 3. Reasoned deviations from the design (all recorded in the phase reports)

- Deployed website round-trip test session (design §6.3) deferred: the WordPress relay has
  never been installed (0 touchpoints on every database); the server-side rolled-back proof
  ships and the screen says so.
- Native Google lead forms (design §10) not built: Google's lead-form policy forbids
  healthcare advertisers; the card and account page say "Unavailable for healthcare ads",
  `native_eligibility` is system-write-only and no tenant switch exists.
- Tenant relay of the Google callback not built: the hub bounces `meta` only; each
  database's redirect address must be registered in the Google Cloud console.
- Area-level spend visibility for area-restricted staff deferred: report rows are readable by
  account-level operators (CRM manager, clinic admin, healthcare admin, owner) only.
- Card chip reads "Partially connected" after a server pipeline test (the normative data
  model §4.2 of the GA1 handover won over its browser script).
- `fields.Monetary` rounds to currency precision (VND: none) → exactness is asserted on the
  `cost_micros` string and its Decimal derivation, not the money column.

## 4. Tests actually executed (master database, wrapper runs)

| Phase | Result line (verbatim) | Executed methods |
|---|---|---|
| GA1 | `0 failed, 0 error(s) of 343 tests when loading database 'carejiox'` | 343 (google_ads 57, channels 264 incl. 4 forced count-pin edits, web_leads 88 test reports) |
| GA2 | `2 failed, 0 error(s) of 395 tests` — both from `03103e07` (pristine baseline: same 2 of 343); GA2's 52 methods all green | 395 |
| GA3 | `0 failed, 0 error(s) of 428 tests when loading database 'carejiox'` (after `ce224fb7` reached the server) | 428 (google_ads 134, channels 220, web_leads 74; 7 HttpCase classes started) |
| i18n gate | `0 failed, 0 error(s) of 5 tests` after each `.po` edit (286 msgids, 0 duplicates) | — |

Deployed browser passes (chrome-devtools on https://carejiox.com, click-by-click from the
CMS sidebar, console logs, QA rows deleted and fresh-cursor-verified): GA1 (13 shots),
GA2 (15 shots incl. the captured authorization request Google received), GA3 (14 shots:
Sync now → job ran → Google refused the fake token → "Action required — reconnect" and a
`Skipped — sign-in needed` run row). Personas: operator (CRM manager) and administrator.

## 5. Capability table (live, 2026-09-15)

| Capability | Configured | Tested | Live |
|---|---|---|---|
| Website leads with Google attribution | Yes — server side complete; account draft needs a connector link per company | Unit + rolled-back pipeline test in the browser | **Awaiting** the website relay (never installed) and the final-URL suffix on the campaigns |
| Campaign reporting sign-in | Software complete; **no platform application row on any database** | Unit (52) + browser to Google's door + real token-endpoint refusal | **Not connected** — needs real credentials |
| Campaign cache / report / nightly job | Software complete; job active on master and hhh, off on the template | Unit (33) + browser (honest failure path) | **No real sync has ever run**; every database holds zero days of figures |
| Google lead forms | Deliberately unavailable | Policy text only | Blocked by Google policy for healthcare |

## 6. External inputs still open (owner)

1. Google Cloud OAuth client (web application, Ads API enabled) with these exact redirect
   addresses: `https://carejiox.com/channel_hub/oauth/callback/google_ads` and
   `https://hhh.carejiox.com/channel_hub/oauth/callback/google_ads` (one per clinic system).
2. Google Ads developer token and its access level (test-accounts-only cannot read real
   accounts).
3. Which Google login manages the ads; the ten-digit customer id(s), one per advertised
   entity.
4. Which website form serves which city (today 15838 → Hanoi, 15670 → HCMC), and the
   WordPress relay installation by the website team, plus the final-URL suffix on campaigns.
5. Campaign → area and campaign → utm campaign mappings; whether to request 12 months of
   history once connected; who may see spend beyond the current operator groups.

## 7. Migration, rollback, hygiene

- Schema is additive (new tables, nullable columns, one stored computed `company_id` on the
  touchpoint back-filled over 0 rows). Unique indexes: customer id database-wide, campaign
  per account, day per (account, campaign, date).
- Rollback: disconnect reporting on any connected account (clears local tokens), deploy the
  prior build with the wrapper; do not uninstall or drop columns. Website capture does not
  depend on any Google state.
- Screenshots: only the committed evidence folders remain; every temporary capture was
  deleted by the implementing agents (verified in each phase report).
- Two pre-existing live defects found and fixed on the way: the website lead endpoint had
  been answering 403 to every submission since the dropdown-vocabulary conversion (service
  group lacked a lookup ACL, ledger §5.184); the shared opportunity list injected sample
  people into the "Google Ads leads" screen. Ledger entries §5.183–§5.194 added.
