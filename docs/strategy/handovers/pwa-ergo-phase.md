# Handover: PWA Ergonomic Modes — Glove + Sunlight (`health_pwa_ergo`)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; the gotcha ledger now has 16 entries — read all). This is Tier
1b: two industry-first quick wins from the strategy bank, UX-081 (glove
mode) and UX-083 (sunlight theme). Field nurses wear nitrile gloves and
read the phone outdoors at noon — both modes attack real usability
failures no home-care competitor addresses.

## 0. Scope

One NEW module `addons/health_pwa_ergo`. Pure front-of-house: CSS + a
small JS toggle, injected into the PWA shell. **Zero server business
logic. app.js is NEVER modified. health_pwa is NEVER modified except
the version bump.**

1. **Glove mode** (`html.vu-glove`): ≥64px hit targets, doubled
   spacing, type scale up one step, stronger contrast, no
   hover-dependent affordances.
2. **Sunlight mode** (`html.vu-sunlight`): maximum-contrast pure-mono
   palette, heavier weights, tints/shadows removed — plus optional
   auto-switching (sensor when available, time-window fallback).
3. A small mode toggle UI the nurse can reach in one tap.

⇒ **PWA bump required: 1.5.0 → 1.6.0** in all 5 places + manifest
`.18 → .19` (conventions §3), deploy health_pwa alongside.

**Non-goals (binding):** swipe-only/swipe-verb interactions (that is
the day-strip redesign, a later phase — it needs app.js surgery);
per-facility server-side defaults (deferred — modes are device-local
this phase); any backend theme (vu.theme/Theme Studio) changes; dark
mode (`color-scheme: light` is forced in app.css and stays).

## 1. Verified plumbing facts (do not re-derive)

- The PWA is Vue 3 + Quasar in ONE monolithic file
  `health_pwa/static/src/js/app.js` (~7,000 lines). Treat it as
  read-only reference.
- CSS custom properties already gate most of what glove mode needs:
  - `health_pwa/static/src/css/mobile.css` `:root` (line ~4):
    `--touch-target: 44px`, `--mobile-padding`, `--mobile-margin`,
    `--bottom-nav-height`, `--mobile-font-*` scale.
  - `health_pwa/static/src/css/app.css` `:root` (line ~450): brand
    palette, status-tint triplets (`--st-*-ac/bg/tx`), font weights.
  Overriding these variables under a mode class does much of the work;
  component-level rules cover the rest.
- Shell CSS links live in `health_pwa/views/pwa_templates.xml` L32–34
  (`app.css`, `mobile.css`, `health.css`, all with
  `?v=#{pwa_asset_version}`). Inject the module stylesheet AFTER
  `health.css` so the cascade wins without specificity hacks.
- QWeb shell-inherit precedent:
  `health_consent/views/pwa_shell_inherit.xml` (xpath on the router.js
  script tag). Same pattern, but xpath the `health.css` link for the
  stylesheet and add scripts after router.js.
- The service worker runtime-caches same-origin static responses
  (`cache.put` in pwa_templates.xml ~L963) — the module's CSS/JS are
  offline-available after the first online load. Do NOT edit the SW
  or its `STATIC_CACHE_URLS` list (that is health_pwa surgery; the
  version bump alone rotates the cache).

## 2. Architecture

### 2.1 Mode classes on `<html>`, not `<body>`

`vu-glove` and `vu-sunlight` are independent, composable classes on
`document.documentElement`. They go on `<html>` because the no-FOUC
boot script (below) runs in `<head>`, before `<body>` exists.

### 2.2 No-FOUC boot script

The QWeb inherit adds a TINY inline `<script>` in `<head>` (before the
stylesheets) that reads `localStorage.vu_ergo_modes` and applies the
classes immediately — a nurse who chose glove mode must never see a
44px flash. Keep it under ~15 lines, try/except-wrapped (localStorage
can throw in private mode).

### 2.3 `static/src/css/ergo.css`

One file, three sections, mono flat colors throughout (no gradients):

- `html.vu-glove` — variable overrides first
  (`--touch-target: 64px`, padding/margin scale ×~1.6, font scale up
  one step, `--bottom-nav-height` up to ~76px), then component rules:
  buttons/inputs/selects/checkbox+radio boxes/bottom-nav items/list
  rows/dialog actions all `min-height: 64px` with grown gaps; fatter
  focus/active states (`:active` scale or background flip — gloved
  hands get no hover). Audit the today/visit/quote/payment screens'
  main classes in app.css and cover them explicitly; state in the
  report which selectors you bumped.
- `html.vu-sunlight` — palette collapse: pure `#ffffff` grounds,
  `#000000` text, weights +100..200 (body ≥500, headings 700+),
  ALL box-shadows off, ALL status/background tints replaced by 2px
  solid black borders + the existing icon/text (color tints wash out
  at 100k lux — information must survive in pure black/white). Links/
  primary actions become black-bordered, black-on-white or inverted
  white-on-black blocks. Aim for WCAG AAA (≥7:1) on body text; compute
  and report the ratios of every remaining color pair.
- `html.vu-glove.vu-sunlight` — verify composition; add explicit rules
  only where the two collide.

### 2.4 `static/src/js/ergo.js` (window global, plain JS)

`window.healthErgo` with `get()/set(modes)/toggleSheet()`:

- State: `{glove: false, sunlight: 'off'|'on'|'auto'}` persisted in
  `localStorage.vu_ergo_modes`. Device-local by design (nurse phones
  are personal devices).
- Toggle UI: a small fixed pill button (bottom corner, above the
  bottom nav, `env(safe-area-inset-bottom)`-aware, ~48px, itself
  64px in glove mode) opening a self-rendered bottom sheet with two
  controls: "Chế độ găng tay (Glove mode)" on/off and "Chế độ ngoài
  trời (Sunlight)" off/on/auto. Self-contained DOM built by ergo.js —
  no Vue integration, no app.js hooks. Inline SVG icons
  (currentColor), NO emoji. Labels vi-first with the en gloss in
  parentheses (PWA precedent).
- Sunlight `auto`:
  - `'AmbientLightSensor' in window` → use it (Generic Sensor API is
    behind a Chrome flag on Android — treat availability as the
    exception, never a requirement): on ≥ 10,000 lux, off < 5,000
    (hysteresis), 30s debounce, full try/except including the
    constructor and `onerror` (permissions policy can reject at
    runtime).
  - Otherwise: time-window fallback — sunlight on between 09:00 and
    16:00 device-local, re-evaluated on `visibilitychange` and every
    15 min.
  - `auto` decisions only ADD/REMOVE the class; they never overwrite
    the stored preference.

### 2.5 `views/pwa_shell_inherit.xml`

Head: no-FOUC inline script + `ergo.css` link (after health.css).
Body/scripts: `ergo.js` after router.js (consent-module pattern), both
with `?v=#{pwa_asset_version}`.

## 3. Module skeleton

`__manifest__.py` depends `['health_pwa']` only. Data: the shell
inherit. No models, no security, no crons, no config params this
phase. `i18n/vi.po` for the manifest strings (the UI strings are
vi-first hardcoded in JS, PWA precedent).

## 4. Tests (`tests/test_pwa_ergo.py`)

Front-end-heavy phase — the Python surface is the shell render:

1. HttpCase: GET the PWA shell (inspect how health_pwa's own tests or
   the consent module authenticate to it; demo user + `url_open`).
   Assert the response contains `ergo.css?v=1.6.0`, `ergo.js?v=1.6.0`,
   and the `vu_ergo_modes` boot-script marker.
2. Assert the served shell version strings are 1.6.0 (guards the
   5-place bump).
3. Static sanity: read ergo.css from the module and assert
   `html.vu-glove` sets `--touch-target: 64px` (cheap regression pin).

Tag `@tagged('post_install', '-at_install')` (conventions §6).

## 5. Deploy & verify

- `-i health_pwa_ergo -u health_pwa --test-tags /health_pwa_ergo`.
- Served shell shows 1.6.0; `window.healthErgo` exists; toggle pill
  renders on the today screen.
- Describe (DOM-inspect via curl/grep is fine) the glove and sunlight
  DOM/CSS effects in the report; the user will eyeball on a real
  phone — list exactly what to look at (pill position, 64px nav,
  sunlight borders).
- Conventions §8: vi.po, commit+push on 19.0, full report.

## 6. Report-back extras

(a) the selector list bumped to 64px in glove mode; (b) the sunlight
palette's computed contrast ratios; (c) which sunlight-auto path a
stock Chrome/Android gets (expected: time-window fallback — confirm
your reasoning against the sensor-flag reality); (d) confirmation the
health_pwa diff is the version bump ONLY (paste `git diff --stat`);
(e) any new ledger-grade gotcha.
