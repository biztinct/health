# Phase W2.5 report — `health_web_leads` Website Connector

**Module:** `health_web_leads` 19.0.2.0.0 → **19.0.3.0.0** · **Server:**
vietuat (care.biztinct.com) · **Date:** 2026-07-29
**Handover:** `docs/strategy/handovers/web-leads-phaseW2_5.md`
**Evidence pack:** `docs/strategy/reports/web-leads-phaseW2_5-evidence/`

Provisioning the website connection used to be a developer job: SSH, a
hand-made service user, `psql` for the city maps. It is now one screen. An
administrator opens **CRM › Website Connector**, presses one button to get
credentials (secret shown once), copies a ready-to-paste `wp-config.php`
block, edits the city maps on screen with validation, runs a pipeline test
that cleans up after itself, watches a delivery-health strip, and can rotate,
disconnect or reconnect — every action on the record's chatter.

---

## 1. What was built

| File | Change |
|------|--------|
| `models/web_leads_connector.py` | **new**, 600 lines — the `web.leads.connector` model: singleton-per-company (`init()` partial unique index, §5.1), computed `state`, the `wp-config.php` block, the two city-map windows onto the parameters, the heartbeat switch + watcher, the health strip, and the five actions. |
| `models/__init__.py` | import the new model. |
| `models/web_lead_service.py` | one W2-review LOW fix: `_heartbeat_user()`'s gateway-admin fallback filters on `active`. |
| `views/web_leads_connector_views.xml` | **new** — plain form arch (vu-theme auto-skin), header buttons + statusbar, list, action, backend menuitem under the API-Gateway root. |
| `data/cms_sidebar_items_web_leads.xml` | `+` the `cms.sidebar.item` leaf — section CRM, sequence 13, `fa fa-globe`. |
| `security/ir.model.access.csv` | `+3` rows: `base.group_system` (with unlink), `health_user_admin.group_health_user_admin`, `health_crm.group_health_crm_manager` (no unlink). **No row for `group_web_leads_service`.** |
| `i18n/vi.po` | `+118` entries (145 → 205 msgids, +452 lines): every new field label, help, selection, button, confirm, group title, prose block and notification. |
| `tests/test_web_leads_connector.py` | **new** — `TestWebLeadsConnector` (13 methods) + `TestWebLeadsConnectorHttp` (T8). |
| `tests/test_web_leads_w2.py` | T11 — the tautological `assertIsNotNone` on a recordset replaced. |
| `tests/__init__.py`, `__manifest__.py` | wiring, version, `health_user_admin` dependency, description. |

Nothing outside `health_web_leads` was edited (rail R7).

---

## 2. Test results

```
2026-07-29 03:15:44 INFO vietuat odoo.tests.result:
    0 failed, 0 error(s) of 52 tests when loading database 'vietuat'
EXIT:0            HTTP:200
executed methods: 52          FAIL:/ERROR: setUpClass lines: 0
```

52 = 38 pre-existing (W1 + W2) + 14 new. **Counted, not assumed** (§5.83 /
§5.90): `grep -aoc "Starting Test.*\.test_"` returns 52, matching the method
count, and both `HttpCase` classes ran (`--workers=0`, no `--no-http`).

| Handover test | Method | Notes |
|---|---|---|
| T1 | `test_w25_01_provision_then_rotate` | user + group + client + both scopes + show-once action; second call = pure rotate (same client, counts unchanged, new hash). Also asserts the `params.next` reload seam. |
| T2 | `test_w25_02_provision_adopts_the_live_credentials` | stages "connector with no client yet", asserts the existing user + client are adopted and neither table grew. |
| T3 | `test_w25_03_wp_config_block` | client id, `/oauth/token`, `/api/v1/web/leads`, `/…/reconcile`, the placeholder — and the block is **byte-identical after a rotate**, which is what proves it carries no secret material. |
| T4 | `test_w25_04_city_maps` | write-through + `_derive_city` resolves; `SGN` → `ValidationError` naming it; four malformed inputs refused; a refusal leaves the parameter untouched; both seeds still `noupdate=1`. |
| T5 | `test_w25_05_test_pipeline_is_residue_free` | notification names the derived city; lead/touchpoint/conversation/message counts identical before and after; an empty map reports instead of crashing. |
| T5b | `test_w25_05b_test_pipeline_runs_for_a_real_operator` | **added after the browser drive** — runs the button as a CRM manager, and asserts up front that the persona still cannot create touchpoints (or the test would pass for the wrong reason). |
| T6 | `test_w25_06_health_strip_and_state` | never-received → `draft`-ish note + `credentials_issued`; a WordPress touchpoint → `last_received_at`, count, `live`; backdated 48 h → the stale note. |
| T7 | `test_w25_07_heartbeat_write_through` | `'True'`/`'False'` strings, **row survives the off-switch**, watcher change moves the single open activity, clearing writes `'0'`. |
| T7b | `test_w25_07b_heartbeat_fallback_never_returns_an_archived_admin` | drives both ambient contexts — see §6. |
| T8 | `test_w25_08_disconnect_stops_the_token_grant` (HttpCase) | 200 → disconnect → **401 `invalid_client`** → reconnect → 200; client archived, never deleted. |
| T9 | `test_w25_09_acl_matrix` | system / user-admin / crm-manager read+write; receptionist and `group_web_leads_service` get `AccessError` — and the live `res_groups_implied_rel` closure is checked first so a §5.88-style inverted edge fails with a readable message. |
| T10 | `test_w25_10_catalogue_sidebar_and_singleton` | 5 xmlids, sidebar leaf with no children and a distinct sequence, `get_view` renders both views, second connector for the same company → `IntegrityError` inside a savepoint. |
| T11 | `test_w2_08_acl_negative` (edited) | the W2 tidy. |
| T12 | `test_w25_12_po_covers_the_new_surfaces` + `_12b` | 25 named msgids present, every block well-formed, and a runtime code translation + a model-term field label both proven non-English under `vi_VN`. |

---

## 3. Report-back items

### (1) Test transcript + executed count
Above. `0 failed, 0 error(s) of 52 tests`, 52 methods executed, EXIT:0.

### (2) Did provisioning adopt user 6103 and client 122 on vietuat?
**Yes — measured, on the live screen.** Before the drive:
`res_users` id **6103** `svc_web_leads` active; `gateway_oauth_client` id
**122** "WordPress pkgdvietuc", active, `user_id = 6103`, carrying **both**
`web_lead.write` and `web_lead.read`. After pressing *Get credentials* as
uid 40:

```
web_leads_connector 23 → oauth_client_id 122
chatter: "Provisioning adopted the existing service account and OAuth
          client — nothing was duplicated."
res_users  WHERE login='svc_web_leads'  → still exactly 1 row (6103)
gateway_oauth_client                     → no new row
```

The screen shows OAuth Client = *WordPress pkgdvietuc*, Client ID =
`b14edb5f623d4ceeb57e50317850740a`. The adoption match is structural
(active + owned by the service user + both scopes) because 6103 and 122 have
no xmlid.

### (3) Secret-notification screenshot
`evidence/05-secret-shown-once-redacted.png` — the sticky notification, secret
blacked out **in the DOM before capture**; the raw screenshot was deleted, not
committed. Rotating rotates the *live* client 122, so it was checked to be
harmless first (0 WordPress touchpoints, 0 web leads ever — the relay has
never delivered), and the secret was rotated once more at the end of the drive
with that value discarded. Nobody holds a secret for client 122 today, which
is the same state as before this phase.

### (4) Test-pipeline residue proof
From psql after four presses of the button:

```
leads 476 | touchpoints 0 | care_conversations 170     (live totals, unchanged)
crm_lead              external_submission_id LIKE 'connector-test-%'  → 0
health_lead_touchpoint external_event_id     LIKE 'connector-test-%'  → 0
crm_lead              contact_name = 'Kiểm tra kết nối'               → 0
crm_lead              phone = '0900000000'                            → 0
```

### (5) Deviations
Four, all in §5.

---

## 4. Design notes worth keeping

**The secret exists in exactly one place.** `action_provision_credentials`
delegates to `gateway.oauth.client.action_regenerate_secret()` and returns its
action unchanged (plus a `next`). This module never calls `token_urlsafe`,
never stores a secret, never logs one, and never asserts on one — R1 is
grep-checkable: the diff contains no `token_urlsafe` and no
`client_secret_hash` write.

**The parameters stay the single source of truth.** The two map fields and the
two heartbeat fields are non-stored computes with inverses over
`ir.config_parameter`. Nothing is duplicated into a column, `web.lead.service`
keeps reading the parameters, and the W1 `noupdate="1"` seeds remain the
install-time defaults (T4 asserts both seeds are still `noupdate`). Validation
lives in the inverse rather than in `@api.constrains`, because
`@api.constrains` never fires for a non-stored field — that is the only hook a
bad value passes through.

**The pipeline test is a savepoint that always rolls back.** The happy path
raises a private sentinel inside `with self.env.cr.savepoint():` and catches it
immediately outside (§5.55: the savepoint, not the `try`, is what keeps the
outer transaction usable). `cr.savepoint()` clears the precommit queue on the
way out but **not** the ORM cache, so the handler calls `env.invalidate_all()`
afterwards — otherwise the environment keeps believing in a lead the database
has already forgotten.

**Parameter writes are strings, always** (§5.36). `'True'` / `'False'` for the
switch, `str(id)` or `'0'` for the watcher. Verified live: switching the alert
off left `web_leads.heartbeat_enabled = 'False'` **with the row still
present**. The falsy set is imported from `web_lead_service` rather than
retyped, so the screen cannot disagree with the cron about what "off" means.

---

## 5. Deviations from the handover

**D1 — `state` is a NON-stored compute (handover §5.1 said "computed
(stored)").** `live` means "a WordPress touchpoint exists", and touchpoints are
written by the capture endpoint in a transaction this model has no
`@api.depends` path to. A stored field would say `credentials_issued` for ever
after the first real submission — the single most visible field on the screen,
permanently wrong. A non-stored compute is simply right every time it is read,
and `widget="statusbar"` renders a computed Selection fine (core precedent:
`account.lock_exception.state`, `account_lock_exception_views.xml:11`).
Verified in the browser across all four states.

**D2 — `base.group_user` is granted EXPLICITLY when the service user is
created (handover §5.2 said "our service group only — `base.group_user` comes
via the user type").** On Odoo 19 membership of `base.group_user` *is* what
makes an account an internal user; the capture path needs what hangs off it
(`mail.message`, `ir.sequence`, `res.partner` read), and both the W1 and W2
fixtures grant it explicitly (`test_web_leads_endpoint.py:41`). Provisioning
therefore ensures `{base.group_user, group_web_leads_service}` and touches
nothing else. On vietuat this is a no-op: 6103 already has both.

**D3 — `action_test_pipeline` runs the synthetic submission as the CONNECTOR'S
SERVICE USER, not as the operator who pressed the button.** Found by driving
the screen, not by a test: a CRM manager has `perm_create = 0` on
`health.lead.touchpoint` (`security/ir.model.access.csv:2-10`), so the button
answered *"You are not allowed to create 'Lead Touchpoint'"* for the exact
persona the screen exists for — while every test passed, because tests run as
uid 1, which is `su` (§5.4 in the flesh). Running as the service user is also
the better test: it exercises the rights the relay actually has, so an ACL
regression on the service account now surfaces here. Before credentials exist
there is no service user and the run falls back to `sudo()`. `T5b` is the test
that would have caught it, and it asserts the precondition (the operator still
cannot create touchpoints) so it cannot silently stop testing anything.

**D4 — the three state-changing actions return `params.next`.** `state` is
derived from the OAuth client, so an action that returns only a notification
leaves the header and statusbar showing the *previous* state — found by
pressing **Disconnect** and watching the buttons not move. The web client's
`display_notification` handler returns `params.next` as its follow-up action,
and a client-side `act_window` keeps the sticky notification on screen (which
the show-once secret depends on — verified in the browser). T1 and T8 assert
the seam so it cannot be dropped silently.

**Minor (not a design deviation): `CopyClipboardText` renders into a bare
`<span>`**, which Odoo's `.o_field_text{white-space:pre-wrap}` rule does not
reach — so the paste-ready block displayed as one collapsed paragraph. The
clipboard copy was always correct (it copies the field *value*); this is about
what the admin sees. Fixed with `class="text-prewrap font-monospace"`, both
utilities confirmed present in the served bundle by reading `document.
styleSheets` in the browser rather than assuming.

---

## 6. New gotcha — a ledger correction, not an addition

**Ledger §5.89's closing caveat and handover fact #11 are wrong about
`res.groups.user_ids` on Odoo 19.** Both say a `user_ids[0]` fallback "does
not apply the active filter" because a relational read carries
`active_test=False`. Measured on vietuat with the relation row present in
`res_groups_users_rel` and the user archived:

```
group.user_ids.ids                                   → []
group.with_context(active_test=False).user_ids.ids   → [6146]
SELECT uid FROM res_groups_users_rel WHERE gid = …   → 6146
```

`res.groups.user_ids` honours the **caller's** `active_test`, so in an ordinary
context the archived member is already invisible — the un-guarded
`_heartbeat_user()` was safe on the cron's own path. It would break the moment
it were called from any environment carrying `active_test=False`, which is not
this module's to assume, so the `.filtered('active')` guard from the W2 review
is kept. `T7b` drives **both** ambient contexts, so the guard is exercised
where it matters instead of asserted where it never fires. Suggested ledger
wording: *the `active_test` behaviour of an x2many read is the caller's, not
the field's — measure it on the target database before writing either "it
filters" or "it doesn't" into a finding.*

---

## 7. Non-goals honoured

No Mode B email ingestion. No 9th `CHANNEL_SELECTION` key, no
`care_conversation.py` edit, no Channel Center edit (the `MODE_TO_CHANNEL`
`website→webchat` wart is untouched). No OWL client action and **no new JS at
all**. No change to the capture/reconcile HTTP contracts, no gateway file
edits, no Lead Ads endpoints, no reporting. No plaintext secret storage
anywhere.

---

## 8. Follow-ups for the reviewer

1. **Pre-existing, blocks nothing here:** every `mail.thread` chatter raises an
   `AccessError` dialog for uid 40 — core Odoo's
   `_message_get_suggested_recipients_batch` reads `base.partner_root` without
   sudo (`addons/mail/models/models.py:557`) and this database's `res.partner`
   rules deny uid 40 partner id 1. Reproduced identically on a `crm.lead`
   thread (line 548), and `res.partner.read([1])` fails on its own. It is a
   `res.partner` record-rule / multi-company condition, not a W2.5 defect.
2. **The tenant is left provisioned**: connector 23 → client 122, secret
   rotated and discarded, heartbeat OFF, city maps at their seeded values. The
   connector record is product configuration, not a QA fixture, so it was kept
   deliberately; every actual fixture (test users, synthetic leads) is gone —
   verified in a fresh cursor (§5.34).
3. `web_leads.heartbeat_user_id` is still empty. Once the relay is live, ops
   should name a watcher and switch the alert on from this screen.
