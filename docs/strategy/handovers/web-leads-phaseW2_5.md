# Phase W2.5 handover — `health_web_leads` Website Connector (self-service onboarding)

**Design:** `docs/strategy/website-crm-integration.md` §15(2) · **Prior phases:** W1
(capture, 19.0.1.0.1) + W2 (ops loop, 19.0.2.0.0) both live and reviewed on
vietuat. **Module:** extend `health_web_leads` only → `19.0.3.0.0`.
**Conventions:** read `docs/strategy/HANDOVER-CONVENTIONS.md` first — §2, §4,
and ledger §5, especially §5.1, §5.16, §5.32, §5.36, §5.45, §5.55, §5.69,
§5.81, §5.85, §5.88–§5.91 (the four new W2 entries).

## 1. What this phase is

Today the website connection is provisioned the way a developer does it: SSH,
hand-created service user, psql. W2.5 turns that into a screen: an
administrator opens **Website Connector**, clicks one button to get
credentials (secret shown once), copies a ready-to-paste WordPress config
block, edits the city maps on screen, runs a pipeline test that cleans up
after itself, watches a health strip, and can rotate or disconnect — with
every action on the record's chatter. This is the SaaS requirement the user
set explicitly: per-clinic onboarding must be minutes, not a developer.

## 2. Binding non-goals

- **NO Mode B email ingestion.** The marker guard (W2) makes it safe *later*;
  there is no mailbox, no `mail.alias.domain`, no fetchmail server on vietuat
  to test against, and building a CF7 email-body parser against imagined mail
  violates data-honesty. Mode B remains designed-only (§15(2)).
- **NO 9th key in `CHANNEL_SELECTION`**, no edit to `care_conversation.py`,
  no edit to the Channel Center module. A web form is not a conversation
  channel (user-approved decision). The known wart stays: `MODE_TO_CHANNEL`
  maps `website→webchat` (`care_conversation.py:63`), so web-form leads show
  under Web chat in the dock — do not "fix" it here.
- **NO OWL client action.** See §3. No new JS at all.
- **NO change to the capture/reconcile HTTP contracts, no gateway file
  edits, no Lead Ads endpoints, no reporting (W3).**
- **NO plaintext secret storage, anywhere, ever** — not on the connector, not
  in a param, not in a log, not in a test assertion message.

## 3. Architecture decision (made — do not re-derive)

**A dedicated singleton model `web.leads.connector` with a form view, header
buttons and the vu-theme auto-skin — the `zalo.config` precedent — NOT an OWL
clone of the Channel Center.** Rationale: every W2.5 function is form-native
(header buttons, computed fields, `CopyClipboardChar`/`CopyClipboardText`
widgets, statusbar); the Center is a 1,000-line OWL component + 689-line
template whose cost and risk (§5.51 CSS ordering, §5.52 shell sizing, §5.82
stepper branches) buys only styling. The theme's `FormCompiler` auto-skins
plain form arch (`health_theme/static/src/js/vu_form_compiler.js:1-43`), so
the screen still looks native. Cross-point the two surfaces the way
`zalo_config_views.xml:23-25` does: an `alert alert-info` on the connector
mentioning the Channel Center covers chat channels, and nothing more.

## 4. Verified plumbing facts (do not re-derive)

1. **OAuth client model** `gateway.oauth.client`
   (`health_api_gateway/models/gateway_oauth_client.py`): `name` :20,
   `client_id` (default `uuid.uuid4().hex`, unique) :21-23,
   `client_secret_hash` (groups `health_api_gateway.group_gateway_admin`)
   :24-27, `allowed_scope_ids` M2M `api.key.scope` :28-30, `user_id`
   **required** :31-34, `token_lifetime` default 3600 :35, `active` :40.
2. **Secret mechanics**: `action_regenerate_secret()` :96-112 generates
   `secrets.token_urlsafe(32)`, hashes via `_set_secret()` :91-94, returns a
   sticky `display_notification` showing the plaintext ONCE. This is also
   the rotate action — there is no separate one. Programmatic provisioning
   shape: `health_web_leads/tests/test_web_leads_endpoint.py:44-50`.
3. **Scopes**: `web_lead.write` / `web_lead.read` seeded in
   `health_web_leads/data/web_leads_scopes.xml:8-18`. Token grant =
   requested ∩ `allowed_scope_ids` codes; empty request ⇒ all allowed
   (`health_api_gateway/controllers/oauth.py:86-93`).
4. **Live credentials on vietuat**: service user `svc_web_leads` (id 6103,
   NO xmlid — hand-created; find by login), OAuth client "WordPress
   pkgdvietuc" id 122. The provisioning action must ADOPT these when they
   exist, never duplicate them.
5. **City maps**: params `web_leads.form_city_map` / `web_leads.url_city_map`
   (constants `web_lead_service.py:64-65`), parsed by `_json_param()`
   :211-227 (returns `{}` on malformed — never breaks capture), consumed by
   `_derive_city()` :251-298. Values are logical `"HN"`/`"HCM"` keys resolved
   by `_resolve_catchment()` :229-246. Seeds are `noupdate="1"`
   (`web_leads_params.xml:16-24`) — the params are the single source of
   truth and STAY so; the connector edits them, the service keeps reading
   them.
6. **Heartbeat**: `PARAM_HEARTBEAT_ENABLED`/`PARAM_HEARTBEAT_USER`
   (`web_lead_service.py:68-69`), `_cron_heartbeat()` :795-815 (falsy-string
   gate `_FALSY_PARAM` :86), `_heartbeat_user()` :817-841,
   `_heartbeat_alert()` :843-885 (model-less activity — ledger §5.89).
   **§5.36: never `set_param(key, False)` — it UNLINKS the param; always
   write the strings `'True'`/`'False'`.**
7. **Health data**: last delivery = max `health.lead.touchpoint.received_at`
   where `source_system = 'wordpress'` (the exact search `_cron_heartbeat`
   already does at :809-811).
8. **Sidebar**: `cms.sidebar.item` fields
   (`health_cms_sidebar/models/cms_sidebar_item.py:4-40`); seed precedent
   with the two §5.69 traps restated:
   `health_web_leads/data/cms_sidebar_items_web_leads.xml`. Section
   `health_cms_sidebar.section_crm`; free sequence 13 (Channel Center = 12,
   Web Touchpoints = 21). Channel Center's own seed + trap notes:
   `health_care_command_channels/data/cms_sidebar_items_channel_center.xml:1-42`.
9. **Form-with-buttons precedent to clone**:
   `health_zalo/views/zalo_config_views.xml:5-108` (header buttons +
   statusbar + info alert). Show-once secret button precedent:
   `health_api_gateway/views/oauth_client_views.xml:23-25`.
10. **Access gate precedent**: `CENTER_GROUPS = ('base.group_system',
    'health_crm.group_health_crm_manager',
    'health_user_admin.group_health_user_admin')`
    (`care_channel_connection.py:142-146`). Mirror this set via ACLs (we
    have no server-side RPC layer to gate).
11. **W2 review LOW findings to fix in passing** (report §10):
    `_heartbeat_user()` fallback `group.user_ids[0]` must become
    `group.user_ids.filtered('active')[:1]`; watcher change must not strand
    the old user's open heartbeat activity (reassign it); T8's tautological
    `assertIsNotNone` on a recordset (test_web_leads_w2.py:359-363) —
    replace with an explicit no-raise comment or a meaningful assert.

## 5. Build spec

### 5.1 Model `web.leads.connector` (new file `models/web_leads_connector.py`)

`_inherit = ['mail.thread', 'mail.activity.mixin']`. Singleton per company:
`company_id` (default current, required) + partial unique index on
`company_id` in `init()` per §5.1 (no `_sql_constraints`). Fields:

- `name` (default "Website connector", required)
- `oauth_client_id` — M2O `gateway.oauth.client`, readonly in UI, tracking.
- `state` — Selection computed (stored): `draft` (no client) /
  `credentials_issued` (client active, no touchpoint yet) / `live` (a
  wordpress touchpoint exists) / `disconnected` (client archived). Statusbar.
- `client_id_display` — related `oauth_client_id.client_id`, readonly, with
  `widget="CopyClipboardChar"`.
- `wp_config_block` — computed Text, `widget="CopyClipboardText"`: the
  paste-ready `wp-config.php` constants block — base URL from
  `web.base.url`, token URL `/oauth/token`, capture URL `/api/v1/web/leads`,
  reconcile URL, `client_id`, and the literal placeholder
  `<the secret you copied when it was shown>`. NEVER a real secret.
- `form_city_map_text` / `url_city_map_text` — Text, computed from the two
  params with inverse writing back (`sudo().set_param` with the JSON string;
  chatter-track the change). Constraint: must parse as a JSON object, every
  value in {"HN","HCM"}; on violation raise `ValidationError` naming the bad
  entry. Help text carries a worked example.
- `heartbeat_enabled` — Boolean computed/inverse over the param (strings
  `'True'`/`'False'`, §5.36). `heartbeat_user_id` — M2O `res.users`
  computed/inverse over the param (store `str(id)`, clear with `'0'` not
  False). Inverse also reassigns any open heartbeat activity to the new
  watcher (fact #11).
- Health strip (computed, non-stored): `last_received_at`,
  `received_7d_count`, `health_note` (plain-language: "No submission ever
  received — the website side is not live yet." / "Last submission N hours
  ago." / "Nothing for over 24 h — check the WordPress relay.").

### 5.2 Actions (header buttons)

- **`action_provision_credentials`** — idempotent adopt-or-create:
  1. Service user: search `res.users` login `svc_web_leads` (active or not);
     if missing, create (internal user, groups: our service group only —
     `base.group_user` comes via the user type). Never touch its password.
  2. Group: ensure membership of `health_web_leads.group_web_leads_service`.
  3. Client: if `oauth_client_id` unset, search for an active
     `gateway.oauth.client` with `user_id` = that user carrying BOTH web_lead
     scopes and adopt it; else create one (`allowed_scope_ids = (6,0,[write,
     read])`, `token_lifetime` 3600). Link it.
  4. Delegate the secret to `oauth_client_id.action_regenerate_secret()` and
     RETURN ITS ACTION (the sticky show-once notification). Chatter: log
     provision/rotate with who and when — never the secret.
  On a connector already in `credentials_issued`/`live`, the same button is
  relabelled **Rotate secret** (two buttons with `invisible` on state, same
  method).
- **`action_test_pipeline`** — validates config with ZERO residue: inside
  `with self.env.cr.savepoint():` build a synthetic payload (submission_id
  `connector-test-<uuid4>`, form_id = first key of the form map or
  `'connector-test'`, name "Kiểm tra kết nối", phone `0900000000`,
  page_url from the url map's first key), call
  `env['web.lead.service'].process_submission(payload)`, capture
  `status` + derived city + `city_source`, then **raise a private sentinel
  exception inside the savepoint so it ALWAYS rolls back** (§5.55 —
  catch the sentinel outside; never roll back the outer transaction).
  Report via a `display_notification`: "Pipeline OK — a submission on form
  15838 would create a lead in Hà Nội (city from form map). Nothing was
  saved." On `ApiError`/exception: warning notification with the message.
  This validates the CITY MAPS the admin just edited, which is the point.
  It does NOT test HTTP auth — say so in the notification's second line
  ("the live test is a real submission from the WordPress plugin"), because
  the CRM cannot know the secret.
- **`action_disconnect`** — `oauth_client_id.active = False` (archive, do
  not delete — audit history), chatter log, state → `disconnected`.
  **`action_reconnect`** — unarchive + advise rotating. Both group-gated in
  the view to the manager groups (fact #10).

### 5.3 Views + reachability

- Form (new `views/web_leads_connector_views.xml`): plain arch, vu-theme
  auto-skin, `<header>` with the buttons + statusbar
  (`draft,credentials_issued,live`). Body groups: Credentials (client id
  copy field + config block), City mapping (the two Text fields + help),
  Health (strip fields + heartbeat toggles), and the Channel-Center
  cross-pointer alert. Chatter at the BOTTOM (project rule).
- Action: `ir.actions.act_window` `list,form` — plus an
  `action_open_connector` server-side helper is NOT needed; a plain action
  is fine since the record count is 0-or-1 per company (list view with
  `create="1"` handles first-run).
- Backend menuitem under the gateway menu (`health_api_gateway` root, beside
  OAuth Clients) for the admin persona, AND the `cms.sidebar.item` seed
  (§4 fact 8): section_crm, sequence 13, name "Website Connector", icon
  `fa fa-plug` is taken by Channel Center — use `fa fa-globe`, childless
  leaf, no `parent_id` field at all, no noupdate, ungated (ACLs govern).
- ACLs (`ir.model.access.csv`): read/write/create for `base.group_system`,
  `health_user_admin.group_health_user_admin`,
  `health_crm.group_health_crm_manager`; NO unlink for anyone but system;
  **no row for `group_web_leads_service`** (the machine account must not
  read its own connector — T9). No other persona sees the model.

### 5.4 Safety rails

R1 The secret plaintext exists only inside
   `action_regenerate_secret`'s notification — grep the diff for
   `token_urlsafe|client_secret` to prove no new storage.
R2 `action_test_pipeline` must leave 0 leads / 0 touchpoints / 0
   care.conversations — asserted in T5 with counts before/after.
R3 Param writes always strings, never Python False (§5.36).
R4 The connector NEVER writes `noupdate` seed files at install for the maps —
   it edits the live params only from the form (the W1 seeds stay the
   install-time defaults).
R5 `init()` partial unique index, not `_sql_constraints` (§5.1).
R6 vi.po: every new field label/help/selection/button/notification string,
   0 inert entries (§5.85, §29); run the §5.90 grep with the expected count.
R7 No edit to any file outside `health_web_leads`.

## 6. Tests (extend `tests/`, new class `TestWebLeadsConnector`)

T1 provision on a fresh env creates user+group+client with both scopes and
   returns the show-once notification action; calling it AGAIN creates
   nothing new (same client id, counts unchanged) — pure rotate.
T2 provision ADOPTS an existing `svc_web_leads` user + existing active
   client with the scopes instead of duplicating (seed them first, mirroring
   vietuat fact #4).
T3 `wp_config_block` contains client_id, /oauth/token, /api/v1/web/leads and
   the placeholder; contains no secret material (assert `token_urlsafe`
   output absent by asserting the block equals its recompute after a rotate
   — the block must not change when the secret does).
T4 city-map inverse: writing valid JSON updates the param and
   `_derive_city` resolves accordingly; invalid JSON → `ValidationError`;
   value `"SGN"` → `ValidationError` naming it; the noupdate seeds are
   untouched by install/upgrade of this phase.
T5 `action_test_pipeline`: succeeds, notification mentions the derived city,
   and lead/touchpoint/conversation counts are IDENTICAL before and after
   (R2). A broken form map (empty) still returns a notification, not a
   crash.
T6 health fields: no touchpoints → draft-ish note; seed a wordpress
   touchpoint → `last_received_at` matches, count correct, state `live`.
T7 heartbeat write-through: toggle True → param string `'True'`; toggle
   False → param string `'False'` and the param row STILL EXISTS; watcher
   change reassigns the open heartbeat activity (create one via
   `_heartbeat_alert` first) and the archived-admin fallback is fixed
   (archive the only gateway admin → fallback skips to `base.user_admin`).
T8 disconnect archives the client; a token issued before still verifies or
   not per gateway behaviour — assert the OAuth `/oauth/token` grant now
   FAILS for the archived client (HttpCase, clone the W1 auth test shape;
   §5.32/§5.86 rules).
T9 ACL matrix: system + user-admin + crm-manager can read/write the
   connector; receptionist gets `AccessError`; `group_web_leads_service`
   gets `AccessError` on read.
T10 xmlids load; sidebar item is a childless leaf; singleton index: second
   connector same company → `IntegrityError`/refusal (savepoint per §5.55).
T11 the W2 LOW test tidy: T8-W2's `assertIsNotNone` replaced (fact #11).
T12 vi.po completeness per R6.

## 7. Deploy + report-back

Deploy per the standard workflow (scp → `/tmp` → sudo cp odoo-owned →
**stop `odoo-server`** → upgrade `-u health_web_leads` with tests →
restart; §5.45 no concurrent odoo-bin; read the RESULT LINE from
`/var/log/odoo/odoo-server.log` with `grep -a`; §5.90 count check).
Browser-verify on care.biztinct.com per the standing browser-QA rule:
drive CMS sidebar → Website Connector as the ops/admin persona, screenshot
the form, the show-once secret notification, and the test-pipeline
notification; evidence folder `docs/strategy/reports/web-leads-phaseW2_5-evidence/`.

Report back: (1) test transcript + executed-count; (2) whether provisioning
adopted user 6103 + client 122 on vietuat (it must — say what it found);
(3) the secret-notification screenshot (redact the secret); (4) test-pipeline
residue proof (counts before/after from psql); (5) any deviation, with the
file:line premise that forced it.

## Kickoff line

Implement Phase W2.5 of the website lead integration exactly per
`docs/strategy/handovers/web-leads-phaseW2_5.md`. Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (§2, §4, ledger §5 —
especially §5.1, §5.36, §5.55, §5.69, §5.81, §5.85, §5.88–§5.91). Extend
only the `health_web_leads` module. Run tests T1–T12, deploy to vietuat per
§7, and report back the five items in §7.
