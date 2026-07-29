# Handover — Web Leads Phase W2: ops loop, triage surfaces, hardening

**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§2, §4, ledger §5 — esp. §5.1, §5.32, §5.38, §5.42, §5.45, §5.55, §5.58/§5.67/§5.85 po rules).
**Context:** `docs/strategy/website-crm-integration.md` (§5.2, §8, §11, §15) and the W1 review addendum in `docs/strategy/reports/web-leads-phaseW1-report.md` — W2 owes four review deferrals (M3, L2, L4, L5).
**Module:** extend `health_web_leads` (19.0.1.0.1 → 19.0.2.0.0). **Database:** vietuat. **No PWA changes.**

## 1. Goal

Make the W1 pipeline operable and visible: a reconcile endpoint the WP relay drives daily, a pipe-broken heartbeat, the Web-Attribution triage surfaces on the forms ops actually use, the email duplicate guard (so the notification-email door becomes safe to open later), and the four review-deferred hardenings.

## 2. Scope and binding non-goals

**In scope:** reconcile endpoint; heartbeat cron; touchpoint views + Web Attribution on BOTH lead surfaces (stock opportunity form AND Lead Hub Source modal); `web_needs_review` filters; `message_new` email-marker guard; M3 ACL narrowing; L2 audit record_ids; L4 race-branch tests; L5 vi.po completions.

**Non-goals (do not build):**
- No connector UI / credential self-service — Phase W2.5. No Lead Ads endpoints — later phase. No email-ingestion Mode B activation (this phase only makes it SAFE via the marker guard; connecting mailboxes is W2.5+). No reporting pivots, no consent bridge — W3.
- No edit to `health_care_command`'s hook (the spam-conversation noise is accepted — decided at design time; do not "fix" it).
- No Python edits outside `health_web_leads`. Views on other modules' surfaces are **inheritance records in our module**, never file edits.
- Do not rename/renumber W1 fields or change the capture endpoint's contract (Proima may already be coding against it).

## 3. Verified plumbing facts — do not re-derive

1. **Capture controller pattern to clone** for the reconcile route: `addons/health_web_leads/controllers/web_leads.py` (post-fix state) — hand-rolled `@http.route(..., readonly=False)` importing `_gateway_authenticate/_scopes_satisfied/_envelope_response/_write_audit_row` + `register_route()`. Use the SAME pattern for reconcile (scope `web_lead.read`); do NOT experiment with `@api_route` here — consistency beats novelty, and the rate-counter/audit writes make "read-only" a lie anyway (§5.38 family).
2. **Review M1 precedent:** the controller's exception ladder is `ApiError → (UserError, ValidationError, AccessError) → Exception(generic 500)`. Reconcile clones it.
3. **Activity-on-failure precedent** for the heartbeat: `addons/health_api_gateway/models/webhook_subscription.py:46-76` — `activity_schedule('mail.mail_activity_data_todo', ...)` in try/except, and search-first so repeated cron runs don't stack duplicate activities.
4. **Cron shape precedent:** `addons/health_api_gateway/data/gateway_cron.xml` (interval, `active`, model+code). Ship the heartbeat cron ACTIVE but internally gated on `web_leads.heartbeat_enabled` (default `False`, seeded param) — §5.81 lesson: a cron that ships active must be harmless by default.
5. **Lead surfaces (CMS-surfaces rule + review N4):** the ops-facing lead UI is the Lead Hub, not the stock form. The Source spoke modal is `health_landing.view_lead_source_modal` at `addons/health_landing/views/hub_spoke_modal_views.xml:531` (shows `source_id, medium_id, campaign_id, contact_source, healthcare_lead_source, vietnamese_channel, contact_reason_id, lead_reason_id`). The full form (reachable from the hub's centre click with `skip_hub_redirect`) is `health_crm.view_healthcare_opportunity_form` in `addons/health_crm/views/crm_lead_views.xml` — chatter renders bottom full-width in this repo; put the new tab inside the existing notebook, and pick a stable inheritance anchor (a named `page` or field, not a layout div).
6. **§5.42:** `get_view` strips group-gated pages — if you group-gate the Web Attribution tab, the view test must assert with `get_combined_arch`, not `get_view`.
7. **Email routing today:** five `crm.lead` mail aliases exist on vietuat (`info`, `healthcare-leads`, `home-visits`, `clinic-services`, `emergency-care`) but **no `mail_alias_domain` and zero fetchmail servers** — inbound mail cannot reach them yet. The guard you build now is what makes connecting them safe later. `crm.team` aliases are seeded in `addons/health_crm/data/health_crm_teams.xml`.
8. **`message_new` seam:** `crm.lead` inherits `mail.thread` (core `addons/crm/models/crm_lead.py:88-102`). Core `mail.thread.message_new` creates the record for alias mail; overriding it on `crm.lead` in our module and returning an EXISTING lead makes `message_process` post the email onto that lead instead of creating a new one. Marker contract (also going into the Proima spec): the CF7 notification email will carry a final line `[web-lead:<submission_id>]` (and, when possible, header `X-Web-Lead-Submission: <submission_id>`); the WP plugin generates the uuid at `wpcf7_before_send_mail` so the SAME id reaches both the email and the webhook payload.
9. **M3 privilege facts (from the review, live-verified):** `group_web_leads_service` currently implies `sales_team.group_sale_salesman_all_leads`, whose closure reaches `res.partner` create/write (`addons/crm/security/ir.model.access.csv:8`), `account.move(.line)` read (`addons/sale/security/ir.model.access.csv:8-9`), and `health.ews.score` read via `health_base.group_healthcare_base`. The original reason for the salesman group was (a) `crm.lead` ACLs and (b) escaping the personal-leads record rule so dedup sees all leads. A dedicated ACL row for our group achieves both: record rules only restrict members of the rule's own groups, and a user in NO sales group is untouched by the salesman-scoped rules.
10. **Service internals already sudo-shielded** (survive ACL narrowing without edits): `ir.config_parameter` reads, catchment resolution, `utm.*` find-or-create, `res.partner` client-match, `care.conversation` upsert — all `.sudo()` in `models/web_lead_service.py`. The non-sudo surface that the narrowed group must still cover: `crm.lead` search/create/write, `health.lead.touchpoint` search/create, `mail.message` via `message_post` (base.group_user ACL covers it), `ir.sequence` read (base covers it).
11. **Audit enrichment (L2):** `_write_audit_row` accepts `record_ids` (list) — the capture handler currently passes `None`. `process_submission`'s result dict is the seam: add an internal `_lead_id` key, pop it in the controller into the audit dict, never let it into the envelope.
12. **Race-test seam (L4):** the two `except psycopg2.IntegrityError` branches (`models/web_lead_service.py` — create branch and the new merge branch) are unreachable single-threaded; test with `unittest.mock.patch.object` raising `psycopg2.IntegrityError` from `health.lead.touchpoint.create` (merge case) / `crm.lead.create` (create case) and assert the `duplicate` answer. Patch narrowly; don't disable the savepoint.

## 4. Deliverables (exact)

### 4.1 Reconcile endpoint — `POST /api/v1/web/leads/reconcile`, scope `web_lead.read`

Request: `{"date": "YYYY-MM-DD" (optional), "submission_ids": ["...", ...]}` — ids required, non-empty, **max 1000** (422 above). Response `data`:
`{"known": [ids...], "missing": [ids...], "counts": {"created": n, "merged": n}}`
- `known` = id matches a `crm.lead.external_submission_id` OR a `health.lead.touchpoint.external_event_id` (`touchpoint_type='form_submit'`); `missing` = the rest (relay re-posts them idempotently).
- `counts` (only when `date` given, computed over `received_at` on that UTC day): `created` = touchpoints whose id equals their lead's `external_submission_id`; `merged` = the others. **`rejected_spam` is deliberately absent** — no row exists by design; the relay marks those done from the capture reply and must never re-post them. Say this in the endpoint docstring.
- New scope record already exists (`web_lead.read`, seeded in W1) — verify, don't reseed.

### 4.2 Heartbeat cron

`ir.cron` daily (ship `active="True"`, harmless by default): method on `web.lead.service`. Logic: if `web_leads.heartbeat_enabled` param falsy → return. Else newest `health.lead.touchpoint` with `source_system='wordpress'` by `received_at` (NOT `occurred_at` — the question is "did the pipe deliver", and `occurred_at` is sender-controlled); if none within 24h (or none ever), schedule ONE `mail.activity` (search-first dedupe, fact #3) on the user from `web_leads.heartbeat_user_id`; if the param is unset, fall back to gateway-admin users like the webhook-subscription precedent. Seed both params (`heartbeat_enabled` = `False`) in `data/web_leads_params.xml` (noupdate).

### 4.3 Triage surfaces

- `health.lead.touchpoint`: list + form (readonly) views, action, and a menu entry under the CRM menu ops actually uses (match where health_crm hangs its config menus).
- Stock full form: inherit `health_crm.view_healthcare_opportunity_form` — new notebook page "Web Attribution": `city_source`, `city_conflict`, `web_needs_review`, `web_form_id`, `external_submission_id` (readonly), `web_landing_url/web_submit_page_url/web_referrer_url`, `utm_content/utm_term`, click-id fields (readonly, group-gate to ops manager if you prefer — then §5.42 in the test), consent pair, and an embedded `web_touchpoint_ids` list.
- Lead Hub Source modal: inherit `health_landing.view_lead_source_modal` — append `city_source`, `web_form_id`, `web_needs_review`, `city_conflict` after `vietnamese_channel`. Keep it modal-small; the full story lives on the form tab.
- Search-view filters on the lead: "Needs review (web)" (`web_needs_review`), "City conflict", "Web leads" (`mode_of_contact='website'`).

### 4.4 Email duplicate guard

`crm.lead.message_new` override in our module (fact #8): extract marker from `msg_dict` — header `X-Web-Lead-Submission` first, else regex `\[web-lead:([A-Za-z0-9-]{8,64})\]` over body/subject. If a lead with that `external_submission_id` exists → log-note + return that lead (no new record). Unknown/absent marker → `super()`. Never raise from the parser (malformed marker = no marker). Document the Proima-side contract line in the docstring (fact #8).

### 4.5 M3 — ACL narrowing

In `security/web_leads_security.xml` drop the `implied_ids` link to `sales_team.group_sale_salesman_all_leads` (keep `base.group_user` on the USER, not the group). Add `ir.model.access.csv` rows for `group_web_leads_service`: `crm.lead` r/w/c (no unlink), `utm.source` r/c, `utm.medium` r/c, `utm.campaign` r, `health.catchment.province` r, `crm.team` r, `crm.stage` r. (`health.lead.touchpoint` rows exist from W1.) Then prove it: the endpoint HttpCase E2E (existing test_15) must stay green as the narrowed user, and add the negative probes (§5 tests). If create() trips an `AccessError` on a model not listed here, add the minimal READ row and record it in the report — do not re-add any implied group. **Post-deploy on vietuat, re-run the recursive closure query from the W1 review addendum and paste the output — it must no longer contain salesman/partner/account rows.**

### 4.6 L2 + L4 + L5

- L2: `_lead_id` seam (fact #11) — audit rows for `created/merged/duplicate` carry `model='crm.lead'` + `record_ids=[id]`; `rejected_spam` carries none.
- L4: the two mocked race tests (fact #12).
- L5: vi.po — model-terms entries for the `res.groups` name/comment, both `api.key.scope` names/descriptions, and every field `help=` string in the module; plus entries for every new W2 string. No inert entries (§5.85).

## 5. Tests (numbered)

- **W2-T1** reconcile splits known/missing correctly across lead-matched, touchpoint-matched (merged), and absent ids.
- **W2-T2** reconcile counts on a date: 2 created + 1 merged → `{created:2, merged:1}`; ids >1000 → 422; missing `submission_ids` → 422.
- **W2-T3** reconcile auth: token with only `web_lead.write` → 403 (scopes are not interchangeable); no token → 401. (HttpCase, clone test_15/16 hygiene: addCleanup purge, §5.32.)
- **W2-T4** heartbeat: disabled → no activity; enabled + stale (>24h) → exactly one activity; run twice → still one; fresh touchpoint → none.
- **W2-T5** `message_new` with a known marker (header variant AND body variant) → returns the existing lead, lead count unchanged, note posted on it.
- **W2-T6** `message_new` with unknown/absent marker → normal create path (count +1).
- **W2-T7** ACL positive: full capture E2E (create + merge branches) as the narrowed service user — green (this is W1's test_15 plus a merge-arm assertion).
- **W2-T8** ACL negative: the service user gets `AccessError` on `res.partner.create`, `account.move.search`, `health.ews.score.search` (direct, non-sudo).
- **W2-T9** audit rows carry `record_ids` for created/merged/duplicate; none for rejected_spam.
- **W2-T10** race mocks: create-branch and merge-branch `IntegrityError` → both answer `duplicate` (merge case with the candidate's `lead_ref`).
- **W2-T11** view catalogue: both inherited views load; if the tab is group-gated, assert presence via `get_combined_arch` (§5.42).
- **W2-T12** po: the W1 po tests extended to the L5 surfaces; every new msgid present, zero inert.

## 6. Deploy + verify (vietuat)

Standard §2 workflow (scp → `sudo cp` odoo-owned → `systemctl stop odoo-server` → `odoo-bin -c /etc/odoo-server.conf -d vietuat -u health_web_leads --test-enable --test-tags /health_web_leads --stop-after-init --workers=0 --http-port=8169` → start → login 200). Log lives at `/var/log/odoo/odoo-server.log` and needs `grep -a`. Post-deploy: (1) reconcile curl smoke with a `web_lead.read` token — one known id (use a T-created id? no data residue: use a fabricated id → expect `missing`), (2) heartbeat dry-run: enable param, run cron method once from shell, verify ONE activity, then disable + delete the activity, (3) the M3 closure query, (4) **browser evidence**: screenshots of the Web Attribution tab and the Lead Hub Source modal on care.biztinct.com into `docs/strategy/reports/web-leads-phaseW2-evidence/`.

## 7. Report back

1. Test transcript (0 failed of N, methods-executed count via `grep -a`).
2. M3 closure-query output post-narrowing + any extra ACL READ rows you had to add, each justified.
3. Reconcile + heartbeat smoke transcripts; screenshots as §6(4).
4. The exact marker format string as implemented (goes verbatim into the Proima spec).
5. Any deviation, with reason (expected: none — and if a §5.38-family cursor issue bites the reconcile route despite fact #1, STOP and report rather than improvising).

## Kickoff

> Implement Phase W2 of the website lead integration exactly per `docs/strategy/handovers/web-leads-phaseW2.md`. Read `docs/strategy/HANDOVER-CONVENTIONS.md` first (§2, §4, ledger §5 — especially §5.1, §5.32, §5.42, §5.45, §5.55, §5.85). Extend only the `health_web_leads` module; other modules' surfaces are touched only via view-inheritance records inside our module. Run tests W2-T1–T12, deploy to vietuat per §6, and report back the five items in §7.
