# Phase GL-2 — the Go-Live Studio UI (health_care_command_channels)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST and follow it exactly.
Design context: `docs/strategy/handovers/golive-studio-design.md`.
Server contract: phase GL-1 is LIVE on vietuat (module 19.0.8.0.0) — the
`golive_state()` payload below is the frozen contract; build against it,
never re-shape it.

## Scope

The operator-facing Studio, entirely inside **`health_care_command_channels`**:

1. New OWL client action `channel_golive_studio` in `static/src/golive/`
   (js + xml + css/scss), full-screen: journey-map home + per-provider
   milestone flow for **meta** and **zalo**.
2. Entry points: `ir.actions.client` record + menuitem
   (`base.group_system`, under `health_care_command.menu_care_command_config`),
   a CMS sidebar ADMIN leaf, an operator-only banner strip on the existing
   Channel Center, and a "Open Go-Live Studio" header button on the raw
   platform-app form.
3. Stylized SVG console illustrations per do-step.
4. vi.po for every new UI string; tests; chrome-devtools browser QA with a
   pixel-audit pass.

**Binding non-goals:** NO invites/delegation (GL-3), NO google/microsoft/
voip24h flows (GL-4), NO change to any GL-1 server method's payload shape
(additive-only if something is truly missing — record it as a deviation),
NO tenant-facing behaviour change in the Channel Center beyond the operator
banner, NO PWA files (no PWA version bump needed — `web.assets_backend`
only). Manifest bump `19.0.8.0.0 → 19.0.9.0.0`.

## The GL-1 contract (verified live — trust this)

`golive_state()` → **list** of provider dicts in `('meta','zalo')` order:

```json
{"provider": "meta", "app_id": 903, "client_id": "1234…", "secret_hint": "••••demo",
 "preflight": {"status": "pass", "at": "…", "detail": "Viet Uc Care (go-live)"},
 "last_handshake_at": "… | false",
 "channels": ["fb", "whatsapp"], "platform_ready": {"fb": true, "whatsapp": true},
 "progress": {"business_verification": {"marked": true, "marked_on": "2026-08-05"}},
 "values": {"oauth_redirect_uri": "…", "webhook_urls": "WhatsApp: …\nMessenger: …",
            "verify_token": "…", "es_config_id": "…", "flb_config_id": "…"},
 "steps": [{"key": "create_app", "kind": "do", "verify": "manual",
            "status": "done", "marked_on": false, "title": "…", "body": "…",
            "console": "https://… | false", "console_label": "…",
            "copy_values": [], "est": "…",
            "inputs": [{"name": "client_id", "label": "…", "secret": false,
                        "regex": "^\\d{10,20}$", "error": "…"}]}, …]}
```

- `status` ∈ `done | todo | waiting | fail`. `console` is `false` until
  `{app_id}` is resolvable. `values` carries `verify_token`/`es_config_id`/
  `flb_config_id` for **meta only**; zalo has the two URL keys.
- RPCs (all on `channel.platform.app`, `@api.model`, operator-gated, each
  returns the refreshed full state): `golive_state()`,
  `golive_submit(provider, step_key, payload)` (payload = declared input
  names only; server validates regex and raises ValidationError with the
  human `error` string), `golive_mark(provider, step_key, marked)`.
- **Render the "Mark as submitted" affordance ONLY where `kind == 'wait'`.**
  `create_app`/`config_ids` are do/manual with derived status; the server
  accepts an inert mark on them — do not offer one (GL-1 report, finding 1).
- Meta steps: create_app · store_secret (verify `preflight`) ·
  business_verification (wait) · app_review (wait) · webhooks (verify
  `handshake`) · config_ids (two inputs) · done. Zalo: create_app ·
  credentials (2 inputs, one secret) · oauth_redirect · webhook (verify
  `handshake`) · done.
- `golive_state()['zalo']['channels']` is `['zalo','zns']` — ONE provider
  card; present ZNS as a capability line ("ZNS notifications ride this same
  app"), never a second journey.
- A non-operator calling any RPC gets a UserError — catch it and render the
  honest refusal screen (see Access below), never an error dialog.

## Verified plumbing — do NOT re-derive

- UI kit to clone: `static/src/center/` — component + registry line
  `registry.category("actions").add("channel_center", ChannelCenter)`
  (channel_center.js:1141), visibility-gated polling (:166-216 — interval
  torn down on tab hide), popup/copy helpers (`copyWebhookUrl` pattern),
  `cc-*`/`tone-*`/`st-*` class system, `ic-*` data-URI mask icons declared in
  `channel_center.css` (plain CSS first in the bundle — libsass mangles
  data-URIs inside .scss, ledger §5.51). Assets go in `web.assets_backend`
  exactly like the center block in `__manifest__.py`.
- Client action + menu precedent: `views/channel_center_views.xml`
  (`action_channel_center`, tag `channel_center`, target current; menuitem
  under `health_care_command.menu_care_command_config`).
- CMS sidebar: ADMIN section is `health_cms_sidebar.section_admin`; leaf
  precedent `health_cms_sidebar/data/cms_sidebar_items_admin.xml:98`
  (`item_admin_data_lifecycle` — icon IS font-awesome there, platform rule).
  This module's own leaf precedent with the sibling-not-child trap +
  action_tag matching: `data/cms_sidebar_items_channel_center.xml`. NO
  noupdate. **Sidebar role gating lives in DB rows, not XML** — ship the
  leaf ungated like `item_channel_center`; the component itself renders the
  server's refusal honestly.
- Raw platform-app form: `views/platform_app_views.xml`
  (`view_channel_platform_app_form`) — add the header button there.
- Channel Center banner seam: `channel_center.js` `load()` /
  `onWillStart` + the header block in `channel_center.xml:13-25`. Sanctioned
  edit: ONE banner element + the minimal JS to fetch its data (call
  `golive_state` in try/catch on setup; UserError ⇒ not an operator ⇒ render
  nothing; never let the catch break the tenant view).
- Test fixture rules from GL-1 (tests/test_golive.py): archive existing
  `channel.platform.app` + `channel.golive.progress` rows in `setUp`
  (`with_context(active_test=False)`, precedent test_platform_go_live.py:68);
  `care.channel.audit` is append-only — count handshake rows by DELTA only;
  patch `models.channel_platform_app.meta_app_identity` with a plain
  function (never autospec); HttpCases `@tagged('post_install','-at_install')`
  and the §2 command (no `--no-http`, `--workers=0`) is load-bearing.

## D1 — Component structure (`static/src/golive/`)

Files: `golive_studio.css` (icons/mask data-URIs, plain CSS), 
`golive_studio.scss`, `golive_studio.js`, `golive_studio.xml`. One
component, three screens driven by local state
(`{view: 'home' | provider, …}`):

**Home — the journey map.** Header (title + one-line promise + Refresh,
clone `cc-top`). One large card per provider from the state list: provider
name, the channels it unlocks as chips (with `tone-ok` when
`platform_ready[channel]`), a **progress ring** (SVG circle,
`done / total` steps, flat mono stroke — no gradients), the current-step
title as "Next: …", est time line ("Meta: one to three weeks, mostly
waiting on Meta's reviewers" — derive from the wait steps' `est`), a
"what you'll need" collapsible (`<details>`) with the prerequisites, and a
Continue/Start button. Cards keep working when `app_id` is false (nothing
exists yet — that IS step one).

**Provider flow.** Left milestone rail (clone `cc-steps` typography,
vertical): number bubble + title per step, class by `status`
(`done`/`on`/`waiting`/`fail`/todo); wait-kind steps show a small clock
glyph and `marked_on` date when waiting. Clicking a rail item jumps to it
(free navigation — statuses are server-derived, nothing to guard). Main
canvas per step:

- title + body (server strings, `t-esc` — never markup),
- the SVG console illustration (D2) when the step has a `console`,
- deep-link button (`cc-btn primary` style, `target="_blank" rel="noopener
  noreferrer"`) with `console_label`; hidden while `console` is false with
  the honest line "Finish the App ID step first — then this button opens
  the right page of the app.",
- copy chips for each `copy_values` key: label + truncated mono value +
  Copy button (clipboard API, "Copied ✓" flip, clone `copySnippet`).
  `webhook_urls` is a multi-line value — render one chip per line (split on
  `\n`, label before the colon),
- inputs: text/password per `secret` flag, client-side regex pre-check
  (mirror the server rule; show the declared `error` under the field on
  mismatch), Save button → `golive_submit`; on server ValidationError show
  its message inline (it IS the human explanation), never a crash dialog.
  When a secret is already stored show `secret_hint` + "A secret is
  already saved." (clone the Zalo-secret pattern),
- wait steps: "Mark as submitted" / "Not submitted yet" toggle →
  `golive_mark`; body already explains the wait,
- verify moments: `store_secret` — after submit the refreshed state carries
  `preflight`; render pass as `cc-ok` with `preflight.detail` (the app's
  real name), fail as `cc-alert bad` with the redacted detail and a "Check
  again" that re-submits nothing but re-fetches state. `webhooks`/`webhook`
  — while status is not done, poll `golive_state` every 5s (visible-tab
  only, clone the center's interval discipline) and show
  "Waiting for the provider's check to reach us…" (`cc-wait`); the moment
  `status` flips, render the green flash (a one-shot CSS transition on the
  milestone — `prefers-reduced-motion` respected) and stop polling. Poll
  ONLY while a handshake step is the open step.
- `done` step: calm full-canvas completion screen — flat mono, big check,
  the server's body copy, chips of the now-ready channels, and one button
  "Open the Channel Center" (`actionService.doAction('health_care_command_channels.action_channel_center')`).

**Access.** On setup, call `golive_state()` once; a UserError renders a
single centered honest card: "The Go-Live Studio is for the platform
operator. Ask your Health19 administrator…" — no error dialog, no retry
storm. All strings through `_t()`.

## D2 — Console illustrations

One stylized SVG per distinct console screen (meta: creation, settings-basic,
security-center, app-review, webhooks, configurations; zalo: app-create,
settings, webhook) as inline QWeb sub-templates in `golive_studio.xml`
(inline so `currentColor`/CSS vars theme them; no static img files, no
external requests). Rules: generic flat-mono panels — a window chrome bar,
grey placeholder rows, ONE highlighted field/button in the studio accent
with a small pointer arrow; **no provider logos, wordmarks or trade dress**
(a labelled caption like "Meta App Dashboard → Settings → Basic" carries the
orientation instead); every `<svg>` gets `role="img"` + `aria-label`;
target ~360×200 viewBox, stroke-based, `vector-effect:
non-scaling-stroke`. These are diagrams, not replicas — invest the polish
in the ONE highlighted element per screen.

## D3 — Entry points

1. `views/golive_studio_views.xml`: `ir.actions.client`
   `action_channel_golive_studio` (tag `channel_golive_studio`, target
   `current`) + menuitem "Go-Live Studio" under
   `health_care_command.menu_care_command_config`,
   `groups="base.group_system"`, sequence 45 (above Platform Applications).
2. `data/cms_sidebar_items_golive.xml`: leaf "Channel Go-Live", section
   `health_cms_sidebar.section_admin`, sequence 93, icon `fa fa-rocket`,
   `action_xmlid` + `action_tag`/`match_action_tags`
   `channel_golive_studio`, `parent_id` explicitly `eval="False"`, NO
   noupdate — clone `item_channel_center`'s structure and comments.
3. `views/platform_app_views.xml`: header button "Open Go-Live Studio"
   (`type="action"`, `%(action_channel_golive_studio)d`) — visible always
   (the form is already system-only).
4. Channel Center banner: one `cc-golive-strip` element under the header in
   `channel_center.xml` — "N of 2 providers ready — Open the Go-Live
   Studio" + button (doAction) — rendered only when the operator probe
   succeeded (D1 Access pattern; store the summary in component state;
   failure = silently absent). Count "ready" = provider dicts whose `done`
   step is `done`.

## Safety rails (binding)

- Never render server strings as markup: `t-esc` everywhere (an escaped
  `<script>` written into a template is served live — ledger §5.64 is
  exactly this module's history).
- No secret value ever held in component state longer than the input field
  needs; clear the field after a successful submit; input `type="password"`
  + `autocomplete="off" spellcheck="false"` for `secret: true` (clone
  `cc_token`).
- The tenant Channel Center must be byte-identical for non-operators
  (banner probe failure = render nothing, and the probe's catch must be
  airtight).
- External links: always `target="_blank" rel="noopener noreferrer"`.
- Flat mono only; no gradients; no emoji; no new font; respect
  `prefers-reduced-motion`; both themes via the existing token overrides.
- Poll interval ≥5s, torn down on tab hide, component destroy, and step
  navigation — never more than ONE live interval.

## Tests — extend `tests/test_golive.py` (+ new tour file)

1. (TransactionCase) `action_channel_golive_studio` exists with tag
   `channel_golive_studio`; menuitem carries `base.group_system`; sidebar
   leaf row exists with matching action_tag.
2. (TransactionCase) assets: the four golive files are listed under
   `web.assets_backend` in the manifest (read the manifest dict — cheap
   tripwire against a lost bundle line).
3. (HttpCase, post_install) minimal OWL tour as the admin user: open the
   Studio action, assert the journey map renders both provider cards and
   the meta card's Start opens the milestone rail with 7 items, then step 1
   shows the App ID input. (Clone the lightest existing tour pattern in the
   codebase — `registry.category("web_tour.tours")`; keep it to ONE tour.)
4. (HttpCase) same route as a non-system CRM-manager user: the refusal card
   renders (probe the DOM marker class), no crash.
5. (TransactionCase) the Channel Center action is untouched
   (`action_channel_center` tag unchanged) — regression tripwire for the
   banner edit.

Numbered T183+ following the module convention.

## i18n

Every `_t()` string into `i18n/vi.po` with `#. odoo-javascript` comment
blocks; `msgfmt --check-format` before deploy. Server strings from GL-1 are
already translated — do not duplicate them client-side; always render the
server's `title`/`body`/`error` verbatim.

## Deploy + verify (conventions §2 verbatim)

scp → sudo cp → upgrade `-u health_care_command_channels --test-enable
--test-tags /health_care_command_channels --workers=0` (no `--no-http`),
own `--logfile` + spare port; confirm HttpCase start counts; restart;
`/web/login` 200.

## Browser QA (MANDATORY, chrome-devtools MCP, care.biztinct.com)

Fresh tab (stale-action trap), real login. Evidence pack of screenshots:
1. Journey map — both cards, progress rings, chips (light AND dark theme).
2. Meta flow — every one of the 7 canvases, including: console button
   hidden pre-app-id with its honest line; copy chip flip on click; the
   secret field with hint after entry; a wait step marked (date renders);
   the refusal card as a non-operator; the celebration canvas (drive state
   by entering a real-format dummy app id + secret — preflight will FAIL
   against Meta with a dummy: verify the fail rendering honestly, that IS
   the fail-state QA; do not fake a pass).
3. Zalo flow — the 5 canvases, ZNS capability line present, webhook step
   polling indicator visible.
4. Channel Center as operator (banner present) and as CRM manager (banner
   absent, view identical to pre-GL-2).
5. Pixel-audit pass: rail alignment, chip padding, ring stroke, focus
   states — iterate until clean, per the standing pixel-validation rule.
Then CLEAN UP every row your QA created (platform-app rows with dummy ids:
delete via unlink as admin — they are archived-or-test rows, sanctioned;
progress rows likewise). Audit rows cannot be deleted — leave them, note
the ids in the report.

## Self-review protocol (MANDATORY — no separate reviewer on this stream)

1. Re-read every changed file against this doc, D-section by D-section,
   rail by rail, explicitly.
2. Verify the deployed copy server-side (`diff` spot files), service up,
   fresh-tab QA done above.
3. Grep the diff for: any `t-raw`/`t-out` on server strings, any secret in
   state/logs, any edit to center files beyond the sanctioned banner seam.
4. Report honestly — anything skipped, any deviation with reason.

## Report back

- Test result lines + HttpCase/tour start counts.
- The screenshot evidence list with one-line verdicts (and where they are
  saved locally).
- Any additive change you needed to the GL-1 payload (should be none).
- Deviations with reasons; leftover QA artifacts (audit row ids).
- Anything GL-3 should know (component seams for the invite button, which
  will live on the do-step canvas).
