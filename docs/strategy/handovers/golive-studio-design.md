# Channel Go-Live Studio — design (guided provider onboarding, Zoho-style)

Stream owner: Fable (design + review) · Implementer: Opus per phase · Decided 2026-08-05.

## Why

The Channel Connection Center status report (docs/care-command-center/channel-center-status.html)
shows every channel blocked on **manual external provider steps** — create a
Meta Business app, pass App Review, register a Zalo app, publish a Google
consent screen, register an Entra app, capture the VoIP24h contract. Today
those steps exist only as a static HTML checklist on the raw
`channel.platform.app` form (`PROVIDER_EXTERNAL_STEPS`,
models/channel_platform_app.py:93), reachable by URL only, readable only by a
developer.

The **tenant** side already has a guided stepper (Calls/Telegram/Zalo/Meta
wizards in `static/src/center/`). The missing piece is the **operator plane**:
nothing guides the human who must create the provider apps. That human is not
technical. Zoho solves this with guided channel setup — numbered steps, deep
links into the provider console, copy chips, paste-back fields, live
verification, and "invite the person who has access". This stream builds that:
the **Channel Go-Live Studio**.

**Decisions (user, 2026-08-05):** phased Fable→Opus workflow · audience =
operator team only (`base.group_system`) — tenants keep the existing Connect
wizard (the true-SaaS / Zoho model: one provider app per deployment) · v1
covers **Meta + Zalo** · delegation feature is **in v1**. Bar: "extremely WOW,
out of this world, very easy for the user."

## Product design

New OWL client action `channel_golive_studio` (`static/src/golive/`),
full-screen, entered from:
(a) a new CMS sidebar ADMIN leaf "Channel Go-Live",
(b) an operator-only banner on the Channel Center ("2 of 5 providers ready —
    Open Go-Live Studio"),
(c) a button on the raw platform-app form (which survives as the expert
    escape hatch).

**Home = journey map.** One card per provider: progress ring, the channels it
unlocks, honest time estimate ("Meta: ~1–3 weeks, mostly waiting on Meta's
reviewers"), "what you'll need before you start" prerequisites, Resume.

**Per-provider flow** — left milestone rail + one milestone per canvas screen:

- Three milestone kinds: *you-do* steps, *we-check* steps (auto-verify), and
  *provider-review waits* (Business Verification, App Review, ZNS template
  review) rendered as amber waiting states with "submitted on …" dates and
  "Check again" — waits are state, not errors (house rule).
- Canvas per step: plain-language title/body (clone the `_center_guide_texts`
  voice), an **illustrated console replica** (stylized flat-mono SVG of the
  provider screen with the relevant field highlighted — maintainable, unlike
  screenshots), a **deep-link button** to the *exact* console page (app-id
  substituted once known), **copy chips** for every value we generate
  (redirect URI, webhook URLs, auto-minted verify token), **paste-back
  fields** with format validation (secret via the existing write-only path).
- **Live proof moments** (the signature WOW): the instant app-id + secret are
  both in, Meta preflight auto-runs and the step flips green with the app's
  real name. When the operator clicks "Verify and save" in Meta's webhook
  dialog, our challenge endpoint logs the handshake and the polling Studio
  flips the milestone green *while they watch*. Same for Zalo's first
  verified event.
- Completion: flat-mono celebration, "WhatsApp and Messenger are now available
  to every clinic", one-click handoff into the tenant Connect wizard.

**Meta milestones (7):** create Business-type app (paste App ID) → store
secret (auto-preflight) → Business Verification (wait) → App Review for the 5
permissions (wait) → redirect URI + both webhook URLs + verify token (live
handshake detector) → Embedded Signup + Login-for-Business config ids →
done.
**Zalo milestones (5):** create app + link OA → paste id/secret → OAuth
redirect URI → the ONE webhook URL (first-verified-event detector; say out
loud that every tenant OA shares it) → done.

**Delegation (Zoho's best move):** any *you-do* step offers "Send this to the
person who has access" → `channel.golive.invite` (hashed token, provider,
included step keys, 14-day expiry, revocable) → public page
`/channels/golive/<token>` with that step's instructions, replica and copy
chips (redirect URI / webhook URLs / verify token). **Never client secrets** —
those are always pasted by a logged-in operator. Every view audit-logged and
rate-limited; expired/revoked tokens get an honest dead-end page.

**Visual system:** vu tokens, flat single colors only (no gradients), `ic-*`
CSS-mask SVG icons (no emoji / no font-awesome except the sidebar leaf icon,
which is font-awesome by platform rule), milestone rail typography mirrors
`cc-steps`, light + dark via the existing token overrides.

## Architecture

1. **Step declarations, server-side + translatable** — `_golive_steps()` on
   `channel.platform.app`: per provider an ordered list of
   `{key, kind: do|check|wait, title, body, console (template w/ {app_id}),
   copy_values, inputs: [{name, regex, error}], verify:
   preflight|handshake|manual, est}`. Structured successor of
   `PROVIDER_EXTERNAL_STEPS` (which it replaces as the checklist source for
   migrated providers so the raw form and the Studio cannot drift).
2. **Progress** — `channel.golive.progress`: one row per provider,
   `steps_json` (per-step marks + submitted-on dates). Convenience state only;
   **truth stays derived** (client_id present, preflight pass, handshake seen
   ⇒ green regardless of steps_json).
3. **RPC surface** — `golive_state()` / `golive_submit(provider, step,
   payload)` / `golive_mark(provider, step, value)`, all
   `_require_operator()`-gated, writes routed through the existing writers
   (`action_set_secret`, extra_json merge, `action_preflight`,
   `action_generate_verify_token`).
4. **Handshake detection** — Meta challenge handler (controllers/meta.py:47)
   and Zalo webhook (controllers/zalo.py:68, first verified event only) log a
   `webhook_handshake` row in `care.channel.audit`; `golive_state()` surfaces
   it; the Studio polls (~5s, visible-tab only, like the Center).
5. **Invites** — `channel.golive.invite` + public controller +
   `mail.template` (install-render gotcha applies). Token stored hashed.

## Phases

- **GL-0** (Fable, done with this commit): status HTML + this design doc into
  the repo.
- **GL-1 — server framework** (Opus): golive-studio-phaseGL1.md.
- **GL-2 — the Studio UI** (Opus): OWL client action, journey home, Meta +
  Zalo flows, SVG replicas, entry points, vi.po; browser QA incl. a real
  Meta-dashboard handshake against UAT.
- **GL-3 — delegation** (Opus): invite model, tokenized public page, email,
  audit + rate limit, revoke UI.
- **GL-4** (later): Google / Microsoft / VoIP24h flows on the same framework.

**Review model for THIS stream (user decision 2026-08-05):** no separate
Fable review pass. Each phase ends with Opus running the **self-review
protocol** written into its handover: re-read every changed file against the
spec top-to-bottom, run the full numbered test list on UAT, verify the deploy
independently (fresh tab, real login), and report results honestly —
including anything skipped or failing.

## End-to-end verification

1. GL-1: module test suite green on UAT config.
2. GL-2: chrome-devtools QA on care.biztinct.com — real (test) Meta app id +
   secret → preflight flips green; "Verify and save" in the real Meta
   dashboard pointed at UAT → handshake milestone flips live. Pixel-audit.
3. GL-3: invite round trip (send / open logged-out / copy / expire / revoke);
   no secret ever renders; audit rows present.
4. Tenant cards flip from "Not available yet" once Meta/Zalo rows are complete
   (`platform_ready`, zero glue).
