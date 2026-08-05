# Phase GL-3 — delegation invites (health_care_command_channels)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST and follow it exactly.
Design context: `docs/strategy/handovers/golive-studio-design.md`.
GL-1 (server, 19.0.8.0.0) and GL-2 (Studio UI, 19.0.9.0.0) are LIVE on
vietuat. This phase adds the Zoho move: "Send this step to the person who
has access" — a tokenized, logged-out page carrying one do-step's
instructions and paste-values, because the person with provider-console
access is often not the person inside Health19.

**This is a PUBLIC endpoint phase. The security rails in D2/D3 are the spec,
not suggestions — treat every one as a test obligation.**

## Scope

Entirely inside **`health_care_command_channels`**:

1. `channel.golive.invite` model (hashed token, expiry, revocation).
2. Operator RPCs: send + revoke; additive `invites` block in
   `golive_state()`.
3. Public page `GET /channels/golive/<token>` (no login) rendering the
   invited step(s): instructions, console deep link, copy chips for
   redirect URI / webhook URLs / verify token. NEVER inputs, NEVER secrets.
4. Invite email (plain, direct `mail.mail` — see D4).
5. Studio UI: invite affordance on do-step canvases + sent/revoke states.
6. Tests, vi.po, browser QA of both the Studio side and the public page.

**Binding non-goals:** no new entry points/menus, no google/microsoft/
voip24h, no change to existing GL-1 RPC semantics (the `invites` key is
additive-only), no mail.template records (D4), no tenant-facing change.
Manifest `19.0.9.0.0 → 19.0.10.0.0`.

## Verified plumbing — do NOT re-derive

- Rate-limit precedent to clone verbatim: `controllers/oauth.py:29-36`
  (`gateway.rate.counter.hit('chub:cb:%s' % ip)` behind a helper; use key
  prefix `chub:inv:%s`).
- Public-page template precedent: `views/oauth_templates.xml`
  (`oauth_styles` + the `oauth_generic` dead-end page — same flat styling,
  same "no detail to strangers" posture).
- Audit: `care.channel.audit._log(event, …, detail=, channel=)`
  never raises; extend `KNOWN_EVENTS` (models/care_channel_audit.py:29)
  with `'golive_invite_sent'`, `'golive_invite_viewed'`,
  `'golive_invite_revoked'` (one comment line).
- Step declarations + values: `_golive_steps()` and the state assembly in
  `models/channel_golive.py` (GL-1). Copy-values resolve from the platform
  app exactly as `golive_state()` does — reuse those internals, do not
  re-implement.
- Studio seam (GL-2 report, verbatim): the invite affordance goes in
  `static/src/golive/golive_studio.xml` **lines ~198–242**, inside the
  `t-else` (non-done) canvas branch, between the deep-link row and the copy
  chips, in a `gl-row`. Gate on `step.kind === 'do'` (never on `verify`).
  Clone `generateVerifyToken()` (`golive_studio.js:655`) as the RPC shape:
  guard `state.busy`, `await this.load()` after, refusals into
  `state.formError` (rendered by `.gl-form-error`). `_isRefusal()`
  (`golive_studio.js:167`) keys the refusal card on `UserError`/
  `AccessError` — raise only those for permission refusals.
  Do NOT put the invite URL in the `copyChips` getter — it gets its own
  small block with its own revoke affordance.
- Fixture rules (GL-1/GL-2 reports): derive test classes from
  `ChannelHubCase` (its `setUpClass` now archives live platform-app rows —
  the D4 booby-trap fix); audit rows are undeletable → assert by DELTA;
  HttpCases `@tagged('post_install','-at_install')`; §2 command flags are
  load-bearing.
- `web.base.url` helper: `channel.platform.app._base_url()`
  (models/channel_platform_app.py:260).

## D1 — Model

`models/channel_golive.py` (extend the GL-1 file):

```python
class ChannelGoliveInvite(models.Model):
    _name = 'channel.golive.invite'
    _description = 'Go-Live Studio Invite'
    _order = 'id desc'
    provider = fields.Selection(PROVIDERS, required=True, index=True)
    step_key = fields.Char(required=True)          # ONE step per invite (v1)
    email = fields.Char(required=True)
    token_hash = fields.Char(required=True, index=True)  # sha256 hexdigest — NEVER the token
    invited_by_id = fields.Many2one('res.users', required=True)
    expires_at = fields.Datetime(required=True)    # now + 14 days
    revoked = fields.Boolean(default=False)
    view_count = fields.Integer(default=0)
    last_viewed_at = fields.Datetime()
    active = fields.Boolean(default=True)
```

Token: `secrets.token_urlsafe(32)`; store `hashlib.sha256(token.encode()).hexdigest()`;
lookup by recomputing the hash and searching `token_hash` (the digest
comparison happens in SQL on the hash — no plaintext ever persisted,
logged, or audited; the URL is built once in the send RPC and goes only
into the email body). No `tracking=True` (Z1). ACL: `base.group_system`
CRUD except unlink (`perm_unlink` 0 — revoke, never erase). The email field
is validated with a plain `@` check, not a strict RFC regex.

## D2 — RPCs (on `channel.platform.app`, operator-gated like GL-1)

- `golive_invite_send(provider, step_key, email)` → `_require_operator()`;
  validate provider/step exists and `kind == 'do'` (ValidationError
  otherwise); **revoke any prior live invite for the same
  (provider, step_key)** — one live invite per step, so a re-send is a
  rotation; create the invite; build
  `<base_url>/channels/golive/<token>`; send the email (D4); audit
  `golive_invite_sent` (detail = provider/step + redacted — NEVER the token
  or the full URL, `detail='meta/webhooks to j***@x.com'`-style); return
  refreshed `golive_state()`.
- `golive_invite_revoke(invite_id)` → operator-gated; sets `revoked`;
  audit `golive_invite_revoked`; returns refreshed state.
- `golive_state()` — additive per-provider key:
  `"invites": [{"id", "step_key", "email", "sent_on", "expires_at",
  "revoked", "expired" (computed bool), "view_count", "last_viewed_at"}]`
  for non-revoked-or-recently-revoked rows (limit: live + the newest
  revoked one per step). No token material, obviously.

## D3 — The public page (the security surface)

`controllers/golive_invite.py`:

```python
@http.route('/channels/golive/<string:token>', type='http', auth='public',
            methods=['GET'], csrf=False, save_session=False, website=False)
```

Order, strictly: (1) rate-limit by IP (clone `_rate_limited`, key
`chub:inv:%s`) → generic dead-end on limit; (2) hash the token, search;
(3) missing / revoked / expired / provider-app-archived are ALL the **same
dead-end page** with the same wording and the same 200 status — a
non-oracle: nothing tells a guesser whether a token ever existed. The
dead-end page (clone `oauth_generic`) says only "This link is no longer
available. Ask the person who sent it for a new one."; (4) on success:
`sudo()` ONLY from here, bump `view_count`/`last_viewed_at`, audit
`golive_invite_viewed` (detail without token), render the page.

Page content (`views/golive_invite_templates.xml`, clone `oauth_styles`
flat styling; standalone page, no website layout, no session, no cookies):
provider name, "Sent by <company> via Health19", the ONE step's `title` +
`body` + console link (`target="_blank" rel="noopener noreferrer"`) + a
static copy block per copy-value (value in a `<code>` element + a JS-free
`<button onclick>`-less approach is impossible for clipboard — a tiny
inline `<script>` with `navigator.clipboard` is allowed here, nothing
else), expiry line ("This link works until <date>"), and the honest
boundary: "This page never contains passwords or secrets. If it asks you
for one, it is not ours." Every dynamic value `t-esc` — never `t-raw`.
Response headers: add `X-Robots-Tag: noindex` (clone the make_response
pattern). **Copy values rendered: `oauth_redirect_uri`, `webhook_urls`
(split per line), `verify_token` — only those the step's `copy_values`
declares. If the verify token does not exist yet, show "Not created yet —
ask the sender to create it in the Studio first" rather than minting one
(a public route must never write config).**

Rails, each one a test: no secret / `client_secret` / ciphertext /
`chs$1$` string can appear in any rendered page; no input elements on the
page; identical dead-end for all four failure modes; rate limit fires; no
new cookie in the response; audit row on every successful view; a view
does not extend expiry.

## D4 — The email

NO `mail.template` record (install render-check gotcha — a template that
fails to render breaks the module install; the messaging module paid for
this). Build the body in Python: render a QWeb view
(`env['ir.qweb']._render('health_care_command_channels.golive_invite_mail',
values)`) with the URL, step title, sender name, expiry date; create
`mail.mail` directly (`auto_delete=True`) and `send()` inside a
try/except that turns SMTP failure into a `UserError` telling the operator
the invite was created but the mail could not be sent — and still return
the URL-bearing state? **No: never return the URL to the client either.**
On mail failure, revoke the invite it just created and tell the operator to
check the outgoing mail server first. The token lives only in the email.

## D5 — Studio UI

On do-step canvases (seam per Verified plumbing): a quiet `gl-row` —
"Someone else has access to this console?" + button "Email them this step".
Click reveals an inline email input + Send (no dialog); success renders the
invite line: "Sent to a@b.com on 5 Aug — works until 19 Aug · Viewed 2×" +
Revoke (ghost) + "Send again" (rotates, per D2). Revoked/expired render
muted with "Send again". Strings through `_t()`, vi.po entries, both
themes, no new poll (invite state arrives with the regular
`golive_state()` loads).

## Tests (extend `tests/test_golive.py`, T189+, derive from ChannelHubCase)

1. Send RPC: non-operator → UserError; wait-step key → ValidationError;
   bad email → ValidationError.
2. Send creates ONE live invite per (provider, step): a re-send revokes the
   prior row; DB holds `token_hash` only — assert the plaintext token
   appears nowhere in the invite row, the audit rows, or the mail body's
   stored copy hash-check (fetch the created `mail.mail` BEFORE send in a
   patched send, assert the URL in it and that its token hashes to
   `token_hash`).
3. Mail failure path: patch `mail.mail.send` to raise → UserError, invite
   revoked, audit trail consistent.
4. (HttpCase) Public page happy path: 200, step title + body present,
   copy values present, `X-Robots-Tag` header, NO `<input`, no secret
   material (assert absence of the stored secret plaintext, `chs$1$`, and
   `client_secret`), `view_count` bumped, `golive_invite_viewed` audit
   delta +1, no `Set-Cookie`.
5. (HttpCase) Non-oracle: bogus token, expired invite, revoked invite,
   archived platform app → FOUR byte-identical bodies and statuses; no
   audit rows, no view_count change.
6. (HttpCase) Rate limit: patch/lower the counter threshold, hammer, assert
   the dead-end appears and no invite lookup happens past the limit.
7. `golive_state()` carries the `invites` block (shape above) and never any
   token material; revoke RPC flips it.
8. Regression: T170–T188 untouched and green.

## i18n + deploy + QA

vi.po for every new string (`#. odoo-python` + `#. odoo-javascript` +
QWeb `model_terms` blocks); `msgfmt --check-format`. Deploy per §2
(`-u health_care_command_channels`, test-tags, workers=0, no --no-http,
HttpCase start-count check). Browser QA (chrome-devtools,
care.biztinct.com, fresh tab): drive send → open the emailed URL pattern
logged-out (take the URL from the mail.mail row on the server BEFORE it is
purged, or patch send in a shell to capture it) → screenshot the public
page light+dark → revoke → confirm dead-end → pixel-audit both the canvas
affordance and the public page. Clean up QA rows (invites are
`perm_unlink=0` — archive them; note audit ids).

## Self-review protocol (MANDATORY — no separate reviewer on this stream)

1. Re-read every changed file against this doc, rail by rail; walk D3's
   ordered checks against the actual controller code line by line.
2. Server-side deploy verification + fresh-tab QA as above.
3. Grep the diff for: token/URL in any log, audit detail, or RPC return;
   `t-raw`; `tracking=True`; any write path reachable from the public
   route other than view_count/last_viewed_at.
4. Report honestly — anything skipped, every deviation with reason.

## Report back

- Test result lines + HttpCase start counts; screenshot list with verdicts.
- The public page's failure-mode proof (the four-identical-bodies check
  output).
- Files created/changed; deviations with reasons; leftover audit ids.
- Anything GL-4 should know (adding google/microsoft/voip24h steps to the
  declarations + Studio with zero framework change is the GL-4 thesis —
  flag anything that would falsify it).
