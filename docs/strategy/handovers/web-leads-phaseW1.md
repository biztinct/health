# Handover — Web Leads Phase W1: `health_web_leads` schema + capture endpoint

**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§2 deploy+test workflow, §4 module conventions, §5 gotcha ledger, §8 definition of done).
**Design context:** `docs/strategy/website-crm-integration.md` (the umbrella design; this phase implements its §4, §5.1, §8, §9).
**Database:** `vietuat`. **No PWA changes in this phase — no version bump.**

## 1. Goal

New module **`health_web_leads`**: attribution fields on `crm.lead`, a `health.lead.touchpoint` child model, and an authenticated endpoint `POST /api/v1/web/leads` on the existing API-gateway rails that turns WordPress contact-form submissions into leads — idempotent, spam-gated, city-resolved, deduplicated. WordPress will call this endpoint (Proima builds that side separately); nothing in this phase touches WordPress, GTM, Zalo, Meta, or VoIP.

## 2. Scope and binding non-goals

**In scope:** module skeleton; `crm.lead` extension fields; `health.lead.touchpoint`; all `init()` indexes; scope + security records; the capture endpoint with the full §6 algorithm; config-parameter city maps; tests; vi.po.

**Non-goals (do not build):**
- No reconcile endpoint, no heartbeat cron, no form-view tab/filters — Phase W2.
- No reporting views, no consent→`health.consent` materialisation — Phase W3.
- No click/beacon endpoints; touchpoint types `click_to_call/zalo_click/messenger_click/call_cdr` are **declared Selection values only** — nothing writes them.
- No edits to `health_crm`, `health_api_gateway`, `health_care_command`, or any other existing module. Everything lives in `health_web_leads`. (If you believe an edit elsewhere is unavoidable, STOP and report back instead.)
- No auto-linking of leads to `res.partner`/patients — see §7 rail R4.
- No `website_crm`, no Odoo website module usage.

## 3. Verified plumbing facts — do not re-derive

1. **Gateway decorator**: `@api_route(path, methods, scopes, summary, ...)` at `addons/health_api_gateway/controllers/gateway.py:255-360`. It handles OAuth/bearer auth → scope check (403) → rate limit (429) → `request.update_env(user=service_user)` → JSON parse (400) → payload validation (422) → response envelope `{success, timestamp, data|error}` (`_envelope_response` gateway.py:43-65) → append-only audit row written in `finally` on a fresh cursor. Clone the import + usage style from `addons/health_api_gateway/controllers/api_v1.py` (e.g. the routes at :130, :228 with `scopes=('booking.write',)`). Enrich the audit row via `_audit_touch(model, record_ids)` (gateway.py:386-396).
2. **Payload validation**: `_validate_payload` (gateway.py:363-383) accepts a JSON-schema-style dict with `required` keys — use `{'required': ['submission_id', 'form_id']}`; enforce "≥1 of phone/email" in the handler (422 via the gateway's error path).
3. **Scopes**: model `api.key.scope` (`addons/health_api_gateway/models/api_key_scope.py:8`, `code` unique). Ship `web_lead.write` and `web_lead.read` as records in **our own** `data/web_leads_scopes.xml` — do not edit the gateway's seed file.
4. **OAuth client**: `gateway.oauth.client` (`addons/health_api_gateway/models/gateway_oauth_client.py:15`) — has `user_id` (service user the token acts as), `allowed_scope_ids`, `token_lifetime`. Token endpoint `POST /oauth/token` (client credentials, `controllers/oauth.py:49`). The client row + service user are created **manually post-deploy** (§10), not in data files; tests create their own.
5. **Lead create path**: `crm.lead.create()` (`addons/health_crm/models/crm_lead.py:883-924`) normalizes phone (raises on invalid), defaults `team_id`, generates `unique_contact_code` for `type='opportunity'`. **`_generate_unique_contact_code` (crm_lead.py:1227-1283) reads `catchment_province_id` from the create vals** — pass it in vals or the code gets the `'99'` orphan prefix. `crm.lead` has **no `mobile` field** in this build (ledger §5.16) — phone only.
6. **Phone/email normalization**: `normalize_vn_phone` (`addons/health_base/models/phone_utils.py:7`) **raises `ValidationError` on non-empty invalid input** (ledger §5.15). Clone the `_safe_phone` wrapper idiom from `addons/health_self_booking/models/health_selfbook_invite.py:28-32` (returns falsy on invalid). Email: lower/strip, require `@` (clone `care.conversation._safe_email`, `addons/health_care_command/models/care_conversation.py:303-307` — but implement locally; no care_command dependency).
7. **care.conversation upsert (merge path only)**: `_find_or_create_for(anchor, signal)` at `addons/health_care_command/models/care_conversation.py:344-389`. Anchor dict `{'lead_id': id, 'phone_normalized': p, 'email_normalized': e}`; signal `{'inbound': True, 'event_at': occurred_at, 'set_status': 'needs_reply', 'unread': 1}` — clone the shape from `_care_ingest_lead` (`health_care_command/models/hooks.py:95-109`). Call **defensively**: `if 'care.conversation' in self.env`, inside `cr.savepoint()` + try/except so it can never break the request. The **create** path needs nothing — the existing lead-create hook ingests automatically.
8. **Idempotency precedent to clone**: partial unique index + search-first — `addons/health_care_command_channels/models/care_channel_message.py:101-119`; `init()` unique-index pattern — `addons/health_api_gateway/models/gateway_token.py:32-38`.
9. **Catchment records**: xmlids `health_base.catchment_province_hanoi`, `health_base.catchment_province_hcm` (`addons/health_base/data/health_catchment_province_data.xml`). **Live vietuat rows have codes `01` (Hanoi) / `02` (HCMC)**, not the seed file's `HN`/`HCM` (noupdate=1, DB predates file). Resolve by `env.ref(..., raise_if_not_found=False)` first, fall back to `search([('code','in',('HN','01'))])` / `(('HCM','02'))`. Report back what `env.ref` returns on vietuat (§9).
10. **Existing lead fields to write, not recreate**: `mode_of_contact='website'`, `contact_source='website_form'`, `healthcare_lead_source='website_form'`, `vietnamese_channel='website'`, `contact_status` (default `'active'`; `'spam'` on the spam-listed path), `is_spam_caller`, `type='opportunity'`, `description`. utm m2o: `source_id/medium_id/campaign_id` (utm.mixin via core crm).
11. **Spam-list check precedent**: `crm.lead` spam machinery — `contact_status='spam'` rows + `is_spam_caller` phone propagation (`crm_lead.py:1911-1974`). Check: `search_count([('phone','=',phone),('contact_status','=','spam')], limit=1)`.
12. **Possible-existing-client note internals**: clone the partner-matching arms of `check_contact_duplicates` (`crm_lead.py:2926-3000`): partner `phone ilike last-9-digits` / `email =ilike` → if hit, `message_post` a note naming the partner's `patient_code`; **never** write `partner_id`.

## 4. Module structure

```
addons/health_web_leads/
  __manifest__.py            # depends: ['health_crm', 'health_api_gateway', 'health_base']
  models/__init__.py
  models/crm_lead.py         # _inherit crm.lead — fields §5.1 + init() indexes
  models/lead_touchpoint.py  # health.lead.touchpoint §5.2 + init() indexes
  models/web_lead_service.py # AbstractModel web.lead.service — process_submission() §6
  controllers/__init__.py
  controllers/web_leads.py   # the @api_route endpoint (thin: parse → service → envelope)
  data/web_leads_scopes.xml  # api.key.scope: web_lead.write, web_lead.read
  data/web_leads_params.xml  # ir.config_parameter: web_leads.form_city_map, web_leads.url_city_map
  security/web_leads_security.xml   # group_web_leads_service
  security/ir.model.access.csv
  i18n/vi.po
  tests/__init__.py
  tests/test_web_lead_service.py    # T1–T14 (TransactionCase)
  tests/test_web_leads_endpoint.py  # T15–T16 (HttpCase)
```

Business logic goes in the **service AbstractModel**, not the controller — testable via TransactionCase without HTTP.

## 5. Data model (exact)

### 5.1 `crm.lead` extension (`models/crm_lead.py`)

Char unless noted: `utm_content`, `utm_term`, `gclid`, `fbclid`, `fbc`, `fbp`, `ga_client_id`, `web_landing_url`, `web_submit_page_url`, `web_referrer_url`, `web_form_id`, `external_submission_id` (copy=False, readonly), `web_consent_text_version`; Selection `city_source` = `form_location / form_id / page_url / campaign_prefix / clicked_phone / zalo_oa / facebook_page / manual / unknown`; Boolean `city_conflict`, `web_needs_review`, `web_consent_marketing`; One2many `web_touchpoint_ids` → touchpoint.

`init()` (ledger §5.1 — `_sql_constraints` do not materialize):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS crm_lead_external_submission_uidx
  ON crm_lead (external_submission_id) WHERE external_submission_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS crm_lead_phone_idx ON crm_lead (phone);
CREATE INDEX IF NOT EXISTS crm_lead_email_from_idx ON crm_lead (email_from);
```

### 5.2 `health.lead.touchpoint` (`models/lead_touchpoint.py`)

`lead_id` (M2o crm.lead, required, index=True, ondelete='cascade'); `occurred_at` (Datetime, required, index — **from payload `submitted_at`, never server now**; fall back to now only when absent); `received_at` (Datetime, default now); `touchpoint_type` (Selection: `form_submit`, `manual`, plus reserved `click_to_call`, `zalo_click`, `messenger_click`, `call_cdr`; required); `source_system` (Selection: `wordpress`, `manual`); `catchment_province_id` (M2o health.catchment.province); `city_source` (same Selection as lead); `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `fbclid`, `page_url`, `referrer_url` (Char); `external_event_id` (Char); `raw_payload` (Text — handler truncates to 8192 chars before create).

`init()`:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS health_lead_touchpoint_ext_uidx
  ON health_lead_touchpoint (touchpoint_type, external_event_id)
  WHERE external_event_id IS NOT NULL;
```
`_order = 'occurred_at desc, id desc'`.

### 5.3 Security

- Group `health_web_leads.group_web_leads_service` ("Web Leads Service").
- `ir.model.access.csv`: touchpoint — service group create/read; `health_base.group_healthcare_operations_manager` (clone the exact group xmlid other modules reference) read/write; no unlink for anyone but system. Lead access for the service user rides existing `crm.lead` ACLs granted by its groups — give the service group the minimal existing CRM user group needed for lead create (check what `health_crm` ACLs require; prefer adding our group to the ACL of nothing — instead assign the service *user* the standard internal-user + the existing CRM access group post-deploy, §10).
- The endpoint itself is gated by scope `web_lead.write`, so ACL breadth beyond create-lead is the thing to minimize, not the route.

### 5.4 Config parameters (`data/web_leads_params.xml`, noupdate="1")

```
web_leads.form_city_map = {"15838": "HN", "15670": "HCM"}
web_leads.url_city_map  = {"/lien-he-hanoi/": "HN", "/dich-vu-tai-hn/": "HN",
  "/doi-ngu-tai-ha-noi/": "HN", "/lien-he-tphcm/": "HCM",
  "/dich-vu-tai-tphcm/": "HCM", "/doi-ngu-tai-tphcm/": "HCM"}
```
Values `"HN"`/`"HCM"` are logical keys resolved through the catchment resolver (fact #9), never DB ids.

## 6. Endpoint algorithm (implement exactly; design doc §9.1)

`POST /api/v1/web/leads`, `scopes=('web_lead.write',)`. Handler: parse → `env['web.lead.service'].process_submission(payload)` → envelope.

```
process_submission(p):
  # A. Idempotency — search-first (unique indexes are the race backstop)
  lead = Lead.search([('external_submission_id','=',p['submission_id'])], limit=1)
  if lead: return {'status':'duplicate','lead_ref':lead.unique_contact_code,...}
  tp = TP.search([('touchpoint_type','=','form_submit'),
                  ('external_event_id','=',p['submission_id'])], limit=1)
  if tp: return duplicate(tp.lead_id)

  # B. Identity (untrusted): phone=_safe_phone(p.phone); email=_safe_email(p.email)
  if not phone and not email: raise 422 via gateway error path

  # C. Spam gate: honeypot_filled or token_ok is False → return {'status':'rejected_spam'}
  #    (audit row only — NO lead). Spam-listed phone (fact #11) → spam_hit=True,
  #    lead still created below with contact_status='spam', is_spam_caller=True.

  # D. City (BEFORE create — fact #5): precedence
  #    location string (diacritic-insensitive: 'ha noi|hn' → HN; 'ho chi minh|hcm|sai gon' → HCM)
  #    > form_city_map[form_id] > url_city_map prefix match on page_url then landing_url
  #    > utm_campaign startswith 'hn_'/'hcm_'. Record city_source; unknown → catchment=False,
  #    city_source='unknown', web_needs_review=True.

  # E. Dedup — LEAD-TO-LEAD ONLY:
  open_dom = [('type','=','opportunity'),('contact_status','in',('active','lead','booking'))]
  cand = phone and Lead.search(open_dom+[('phone','=',phone)],order='write_date desc',limit=1)
  if not cand and email: cand = Lead.search(open_dom+[('email_from','=ilike',email)],...)
  merge = cand and (cand.contact_status=='booking'
                    or cand.write_date >= now()-timedelta(days=60)) \
               and names_match(p.name, cand.contact_name or cand.name)  # casefold+strip diacritics;
                    # OR exact email equality when both sides have email
  with self.env.cr.savepoint():                                   # ledger §5.55
    if merge:
        TP.create(tp_vals(cand, p))
        if tp_city and cand.catchment_province_id and tp_city != cand.catchment_province_id:
            cand.write({'city_conflict':True,'web_needs_review':True})
        cand.message_post(body=_("Repeat web enquiry ..."))       # translated
        _upsert_care_conversation(cand, phone, email, p)          # fact #7, defensive
        return {'status':'merged', ...}
    try:
        lead = Lead.create({... §5.1 fields, catchment in vals,
                            'phone': phone or False,              # NEVER raw invalid phone
                            'description': message (+ "\nPhone (unverified): <raw>" if invalid),
                            'name': "Web: %s" % (p.name or phone or email),
                            'contact_status': 'spam' if spam_hit else 'active',
                            'is_spam_caller': spam_hit,
                            'web_needs_review': invalid_phone or not catchment or shared_phone_hit})
        TP.create(tp_vals(lead, p))
        if shared_phone_hit: reciprocal message_post on both leads
        if partner_match(phone,email): lead.message_post("Possible existing client: <patient_code>")
        return {'status':'created', ...}
    except psycopg2 IntegrityError caught OUTSIDE the savepoint:  # race on the unique index
        pass
  lead = Lead.search([('external_submission_id','=',p['submission_id'])], limit=1)
  return duplicate(lead)
```

UTM handling in `tp_vals`/lead vals: raw strings always stored; `source_id`/`medium_id` find-or-create after sanitize (≤64 chars, strip control chars, reject values containing `://`); `campaign_id` **find-only** by exact-insensitive name — no auto-create ever.

## 7. Safety rails (binding)

- **R1** Never call `normalize_vn_phone` directly on payload data — `_safe_phone` only (§5.15).
- **R2** City resolved before `Lead.create()`; `catchment_province_id` in vals (fact #5).
- **R3** Spam/honeypot → HTTP 200 with `rejected_spam`; never 4xx (retry loop + bot oracle).
- **R4** Never write `partner_id`/`patient_id` from payload identity; chatter note only (anti-pattern: `care_channel_message.py:175-185`).
- **R5** Merge path must upsert `care.conversation` defensively (fact #7) — the create hook does not fire on merge.
- **R6** Every write happens inside the request's transaction with the savepoint pattern above; the care-conversation upsert gets its own inner savepoint.
- **R7** `occurred_at` from payload `submitted_at` (parse ISO-8601 with tz → store naive UTC per Odoo convention); `received_at` = server now.
- **R8** `raw_payload` truncated to 8 KB before create; never log payload bodies (gateway audit already excludes bodies).
- **R9** All user-visible strings (chatter notes, field labels, selection labels) translated; complete `i18n/vi.po` including model-occurrence entries (green-build §5.87 lesson: no inert entries).
- **R10** No `Date.today()`-style bare calls in Selection defaults or lambdas that break registry load; follow §4 module conventions.

## 8. Tests (numbered; TransactionCase on the service model, HttpCase only for T15–T16)

Fixtures: create catchment HN/HCM records if absent (or resolve existing), a base payload helper `_payload(**overrides)`.

- **T1** Valid HN submission (form 15838, location "Hà Nội") → `created`; catchment=HN; `city_source='form_location'`; `unique_contact_code` prefix matches HN catchment code; touchpoint row exists with `occurred_at` == payload `submitted_at`.
- **T2** Empty location, form 15670 → `city_source='form_id'`, catchment=HCM.
- **T3** Shared form 15615, no location, neutral URL, no campaign → `created`, catchment False, `city_source='unknown'`, `web_needs_review=True`.
- **T4** Exact replay (same `submission_id`) → `duplicate`, same `lead_ref`; lead count unchanged; touchpoint count unchanged.
- **T5** Race path: pre-create a lead with the `external_submission_id`, then call service → `duplicate` (exercises the re-search branch).
- **T6** Open lead (status `lead`, write_date now) same normalized phone (`0912345678` vs payload `+84 912 345 678`), same name → `merged`; touchpoint appended to it; no new lead; if `care.conversation` in env: a conversation for the lead is `needs_reply`.
- **T7** Same phone, different name ("Nguyễn Văn B" vs "Trần Thị C") → `created` new lead; both leads have cross-reference chatter; new lead `web_needs_review=True`.
- **T8** Merge where touchpoint city=HCM but lead city=HN → `merged`, lead catchment unchanged, `city_conflict=True`.
- **T9** Invalid phone (`123`) + valid email → `created`; `phone` False; raw `123` in description; `web_needs_review=True`.
- **T10** No phone, no email → gateway 422 error (service raises the designated exception).
- **T11** `honeypot_filled=true` → `rejected_spam`; **zero** new `crm.lead` rows.
- **T12** Phone matches an existing `contact_status='spam'` lead → `created` with `contact_status='spam'`, `is_spam_caller=True`.
- **T13** `utm_campaign='zzz_unknown_junk'` → `campaign_id` empty, raw stored on lead+touchpoint; `utm_source='google'` creates/reuses a `utm.source`; a source value containing `http://` is not materialized as m2o.
- **T14** Candidate lead in `lost_booking` with same phone/name → **not** merged; new lead created.
- **T15** (HttpCase) Full round-trip: create scope+client+service user in setUp, fetch token via `/oauth/token`, POST a valid payload → 200 envelope `success=true`, `data.status='created'`. Follow the gateway's own HttpCase precedent in `addons/health_api_gateway/tests/` if present; remember §5.32 (HttpCase side-effects — pin with addCleanup) and run per §2 workflow (no `--no-http`, `--workers=0` — ledger/HttpCase note).
- **T16** (HttpCase) Token whose client lacks `web_lead.write` → 403; no token → 401.

## 9. Report-back items

1. `env.ref('health_base.catchment_province_hanoi' / '..._hcm')` results **on vietuat** (id + code) — confirms fact #9's fallback is/isn't needed.
2. `company_id` of a lead created through the endpoint on vietuat (expect VIET UC id 1 — the service user's company).
3. Full test transcript (`0 failed of N`), including the HttpCase invocation line used.
4. The curl smoke transcript from §10.
5. Any deviation from this handover, with reason (expected: none).

## 10. Deploy + verify (vietuat, per HANDOVER-CONVENTIONS §2 / [[reference_deploy_workflow]])

1. `scp` module to `/tmp` on VietUcUAT → `sudo cp -r` into the addons path with odoo ownership.
2. Upgrade: `sudo -u odoo odoo-bin -d vietuat -u health_web_leads --stop-after-init` (never while another odoo-bin runs — ledger §5.45), then restart the service.
3. Post-deploy ops (document the exact clicks/shell in your report):
   - Create internal user `svc_web_leads` (no login password needed beyond a random one; add groups: internal user, the CRM access group identified in §5.3, `group_web_leads_service`).
   - Create `gateway.oauth.client` "WordPress pkgdvietuc" → user `svc_web_leads`, allowed scopes `web_lead.write`, `web_lead.read`; regenerate + capture the secret once.
4. Curl smoke: (a) `POST /oauth/token` → token; (b) POST with `"anti_spam": {"honeypot_filled": true}` → 200 `rejected_spam` and **no lead created** (auth+validation proven with zero data residue); (c) one real payload with name "W1 SMOKE TEST" → `created`, then verify in the UI: lead exists, catchment set, touchpoint attached, `web_needs_review` behaviour correct, care.conversation row present; leave it flagged for ops or mark spam via the existing action.
5. Confirm the audit trail: `api.audit.log` rows for the three calls.

## Kickoff

Paste into the Opus session:

> Implement Phase W1 of the website lead integration exactly per `docs/strategy/handovers/web-leads-phaseW1.md`. Read `docs/strategy/HANDOVER-CONVENTIONS.md` first (§2, §4, and ledger §5 — especially §5.1, §5.15, §5.16, §5.32, §5.45, §5.55). Build only the `health_web_leads` module; do not modify any existing module. Run the numbered tests T1–T16, deploy to vietuat per §10, and report back the five items in §9.
