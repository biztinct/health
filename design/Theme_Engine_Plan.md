# Việt Úc Theme Engine — Audit & Architecture Plan

**Phase 0 deliverable — no code has been changed.** This document is (1) a complete UI/UX audit of the existing `health_theme` module, grounded in source review **and** live inspection of the running UAT instance (vietuat, Chrome, 1440×900 and 768×900), and (2) the full architecture for evolving `health_theme` into a configurable Theme Engine with presets, a preview playground, and a safe test → publish → discard flow.

**Locked decisions** (agreed before this document was written):

| Decision | Value |
|---|---|
| Scope | Admin designs/tests/publishes one company-wide theme. No per-user themes. |
| Dark mode | **Not needed.** Tokens stay dark-ready; the existing `[data-theme='dark']` block remains untouched; no dark palette is built. |
| Surface | Backend web client only. `health_pwa` untouched. |
| MUK modules | Replaced. (Verified live: `muk_web_theme` / `muk_web_colors` are **not installed** in vietuat — they exist only as repo folders. No uninstall migration needed; just never deploy them and remove from the repo when convenient.) |
| Presets | Free palettes allowed; Việt Úc Deep Blue `#1565C0` stays the shipped default; logo colors (Hibiscus Red/Orange, Leaf Green) stay reserved. |
| Safety | Every change previewed in a playground first; explicit Publish or Discard; nothing breaks existing functionality; no core hacks. |
| Form paths | Both first-class: VU-engine forms **and** native forms (dialogs, `vu-form-native` opt-outs, Settings, kill-switch-off). One published theme must restyle both coherently. |

---

## 1. Executive summary

`health_theme` is already a serious, production-grade theme — far beyond a color skin. Its strongest assets are architectural: an 80+ variable CSS custom-property token system (`--vu-*`), a fail-closed form engine that never renames Odoo's structural anchors, a mono-color "Indigo Workspace" design language for forms, and self-contained OWL widgets. The live UAT app already looks closer to a modern SaaS product than stock Odoo: the booking form (hero + stat strip + progress rail + card sections) and the custom Reschedule wizard are genuinely Linear/ClickUp-class screens.

**What's missing is not visual quality — it's a theming *system*:**

1. **Zero runtime configurability.** Every color, font, radius, and density value is baked at SCSS compile time. Changing the primary color requires editing SCSS and redeploying.
2. **Three disconnected token families.** `--vu-*` (brand), `--vuf-*` (form engine, hardcoded hexes, different radii, different font — Inter vs Segoe), and `--bi-*` (biz_bi, falls back to `--vu-*`). A theme change today would restyle only part of the UI.
3. **A tail of off-system styling** in `backend.scss`: gradient badges and statusbar buttons (violating the project's own flat-mono rule), stock-Bootstrap `#0d6efd` gradients instead of brand `#1565C0`, a 15-color icon map keyed on button-name substrings, and 343 `!important`s.

The proposed Theme Engine converts the *existing* token system into a runtime-configurable one (no SCSS rebuild on publish), unifies the three token families under one semantic layer, and adds a Theme Studio client action (token editor + full component playground + preset picker + Preview/Publish/Discard). Because the tokens already exist, this is an evolution, not a rewrite — the highest-risk asset (the form compiler patch) is **not touched at all**.

---

## 2. How this audit was grounded

- **Live inspection (UAT, vietuat):** Operations Center dashboard, Booking Queue calendar + list, VU-engine booking form BK1238 (desktop + 768px), custom Reschedule wizard, native Settings app, Contacts list + contact form, native "Add Contact" dialog, many2one dropdown, home/apps menu, chatter, notebook tabs.
- **Source deep-read:** `primary_variables.scss` (366 L), `backend.scss` (1,549 L), `vu_tokens.scss` (103 L), `vu_form_compiler.js` (188 L) in full; structure-level passes of `vu_form_engine.scss` (1,099 L), `state_system.scss`, and the remaining SCSS/JS; manifest, templates, `ir_http.py`.
- Items rated from code only (not seen live) are marked *(inferred)*.

---

## 3. Component-by-component audit

Ratings: ★1 poor → ★5 excellent. Verdicts: **KEEP** (do not touch), **TOKEN** (keep design, reroute hardcoded values through theme tokens — near-zero visual change), **IMPROVE** (targeted upgrade), **REDESIGN** (rebuild the piece).

### 3.1 Foundations

| Area | Rating | Verdict | Evidence & reasoning |
|---|---|---|---|
| Design tokens (`--vu-*`) | ★★★★½ | **KEEP** (extend) | 80+ custom properties covering surfaces, text, borders, brand, status, workflow states, type scale, spacing, radii, shadows, transitions (`primary_variables.scss:203-293`). This is exactly the foundation a theme engine needs. Extend with the missing knobs (density, sidebar width, navbar height, card style) — don't restructure. |
| Form-engine tokens (`--vuf-*`) | ★★★½ | **TOKEN** | Well-designed mono palette, but hardcoded hexes disconnected from `--vu-*` (`vu_tokens.scss:11-83`). Radii disagree with brand tokens (12px vs 8px md). Font is Inter while brand body is Segoe UI — two type systems ship today. Re-derive every `--vuf-*` from the semantic layer (`--vuf-primary: var(--vu-brand-primary)` etc.). Visual change ≈ zero; theme changes then reach VU forms automatically. |
| Typography | ★★★★ | **KEEP** (unify) | Montserrat headings / Segoe body / 13px compact base is coherent, dense, professional — appropriate for a data-heavy clinic back office. Live rendering confirms good hierarchy. Only fix: one body font across brand + engine (choose per theme via token). Keep the compact 13px as the "Comfortable" density value. |
| Spacing | ★★★★ | **KEEP** | Consistent 4px-based scale in both token families; live spot-checks of cards/forms show consistent rhythm. Becomes the "density" axis of the engine (multiplier on the space scale). |
| Color system | ★★★★ | **KEEP** (govern) | Disciplined palette: logo colors reserved, Deep Blue UI, healthcare-grade state colors, 7-state workflow scale — live UI matches the guide. Gaps: `backend.scss` leaks off-palette hexes (`#0d6efd`, `#6f42c1`, `#20c997`, 15+ more) — reroute through tokens. |
| Icons (hf-wt-ico / Lucide CSS-mask) | ★★★★ | **KEEP** (consolidate) | CSS-mask + `currentColor` is the right technique (recolors with theme for free). Gaps: icon files split across `health_theme` (20) and `health_base` (22) with 6 duplicates; `backend.scss` hardcodes 22 per-icon color/tint pairs (lines 359-577) that should derive from tokens; stock multicolor Odoo app icons and one emoji-style glyph (Operations dashboard "Active Now") still appear. Consolidate into one icon set in `health_theme` + tokenized tint. |
| Shadows / elevation | ★★★★ | **KEEP** | Two coherent shadow scales (brand sm/md/lg + engine layered-soft). Map both to one tokenized "shadow depth" knob. |
| Animations | ★★★★ | **KEEP** (one removal) | Tasteful: 120/200ms transitions, fade-up, `prefers-reduced-motion` honored (`vu_tokens.scss:96-103`). One violation: the statusbar-button "shine sweep" gradient animation + `translateY(-2px)` hover (`backend.scss:927-950`) — flashy, off-system, and a gradient. Remove with the statusbar-button cleanup. |

### 3.2 Navigation & chrome

| Area | Rating | Verdict | Evidence & reasoning |
|---|---|---|---|
| Top navbar | ★★★★ | **TOKEN** | Flat Deep Blue, clean systray, correct contrast (observed live). Height/color become tokens (`--vu-navbar-height`, `--vu-navbar-bg`). |
| CMS sidebar (health_cms_sidebar) | ★★★★ | **TOKEN** + **IMPROVE** | Dark navy grouped sidebar is the strongest SaaS signal in the app. Two issues observed live: (a) width is fixed — at 768px it consumes 220px and crushes content (calendar day cells ~30px, unusable); needs collapse-to-icons below ~1024px and a width token; (b) colors are its own hardcoded set — must consume theme tokens so presets restyle it. |
| Apps/home menu | ★★ | **REDESIGN** | Observed live: a plain white text dropdown — no icons, no search, no grouping, scrollbar through the middle. Weakest chrome element vs any modern SaaS (Slack/Teams/Monday all have rich launchers). Replace with a grid launcher (app icons + type-ahead filter), as an OWL dropdown replacement — no core hack needed (`registry` swap of the apps-menu item). |
| Breadcrumbs / control panel | ★★★★ | **KEEP** | Clean white panel, ellipsis-safe breadcrumbs, overlap fix already present (`backend.scss:1528-1550`). |
| Search box | ★★★ | **IMPROVE** | Observed live on every list/settings screen: permanent heavy 2px blue border + inner outline makes the box look focused at rest and visually dominates the control panel. Restyle to quiet-at-rest (1px `--vu-border-soft`), brand ring only on focus. Small change, large calm-down of every screen. |
| Pager / view switcher | ★★★★ | **KEEP** | Compact, correct (observed live on Contacts 1-80/460). |

### 3.3 Views

| Area | Rating | Verdict | Evidence & reasoning |
|---|---|---|---|
| List/tree views | ★★★★½ | **KEEP** | Observed live (Bookings, Contacts): uppercase letter-spaced headers, comfortable 40px-ish rows, status pills, pastel tag chips, avatar squares, phone links with icons, filter-tab row + date-chip row above the table. Already better than most SaaS tables. Density becomes a token; nothing else changes. |
| Kanban | ★★★½ | **TOKEN** *(partly inferred)* | 13px sizing applied globally; cards inherit card tokens. Not deeply inspected live (record cards seen only in dialog "Add Contact" tile). Rate-limited claim: no known issues; token pass only. |
| Calendar | ★★★★ | **IMPROVE** (small) | Booking Queue calendar observed live: clean grid, mini-calendar side panel, filter checkboxes. One issue: event pills carry harsh ~2px near-black outlines that read heavier than the SaaS norm — soften to 1px tinted border + stronger left accent (matches the list-view pill language). |
| Pivot / Graph | ★★★ | **TOKEN** *(inferred)* | Only global font-size rules touch them today. biz_bi (ECharts) already themes via `--bi-* → --vu-*` fallback — good. Native pivot/graph get token colors in the engine's generated palette (chart series derive from preset accent ramp). |
| Custom dashboards (Operations Center, AR, biz_bi) | ★★★★½ | **TOKEN** | Observed live: KPI cards with colored top-border accents + icon chips, booking queue card, staff roster — excellent. They consume their own hexes in places; reroute to tokens so presets restyle them. |
| Settings app | ★★★★ | **KEEP** | Correctly excluded from the form engine (`vu_form_compiler.js:123-125`); renders stock with themed chrome — right call, keep exclusion. |

### 3.4 Forms — VU-engine path

| Area | Rating | Verdict | Evidence & reasoning |
|---|---|---|---|
| Hero header | ★★★★½ | **KEEP** | BK1238 live: code + status pill + type chip + created-by + elapsed timer. Compiler moves (not clones) `.oe_title`, so the field stays editable (`vu_form_compiler.js:85-88`). One nit: the priority star widget floats beside the title with no label context — group it into the meta row. |
| Stat strip (5 KPI cards) | ★★★★½ | **KEEP** | Scheduled/Type/Duration/Facility/Catchment cards with icon chips + left accents; wraps to 2-col at 768px cleanly. |
| Progress rail | ★★★★ | **IMPROVE** (small) | Green checks, orange active pulse — excellent desktop. At 768px the rail truncates (Completed/Closed clipped, observed live). Add horizontal scroll-snap or collapse-to-current-step on narrow widths. |
| Section cards / tabs | ★★★★½ | **KEEP** | Card sections with tinted icon chips; segmented-pill tab bar (Overview/Pricing/Clinical/…) — modern and consistent. |
| Sticky action bar | ★★★½ | **IMPROVE** | Live: the pill-button action row is sticky and overlaps card content while scrolling (observed covering "Scheduled Date &" field and colliding with the Next Best Action card at 1440px). Give it an opaque background + bottom border, and reserve scroll padding. Note `backend.scss:621` writes `background: rgba(var(--vu-surface-card), 0.95)` — **invalid CSS** (rgba over a hex var), so the intended translucent backdrop silently never applied. Fixing that line alone likely resolves the see-through overlap. |
| Statusbar action buttons | ★★★ | **IMPROVE** | The pill shape + colored icons read well live, but the implementation is off-system: Bootstrap-stock gradients (`#0d6efd→#0856c9`, `backend.scss:955`) instead of brand `#1565C0`, four more gradient pairs (success/warning/danger tints), a shine-sweep animation, and a 130-line icon-color map keyed on `button[name*="…"]` substrings — brittle and unthemeable. Rebuild flat-mono on tokens; keep the pill silhouette so users see no layout change. |
| Next Best Action / Quick Actions | ★★★★ | **KEEP** | Distinctive, useful, on-palette (observed live). |
| Field labels/indicators | ★★★★ *(with one open item)* | **KEEP** + verify | Required-red and help-`?` markers render well live. Open item: the Contacts form right column renders inputs with **no labels at all** (only 4 `o_form_label` nodes in the whole form, verified via DOM). The compiler does not remove labels (`compileGroup` only adds classes), so this is almost certainly the custom `crm_contact_form_view` arch using placeholder-only fields — **verify and fix in the view, not the theme**; placeholder-as-label fails WCAG and breaks once a value is entered. |

### 3.5 Forms — native path (dialogs, opt-outs, kill-switch-off)

| Area | Rating | Verdict | Evidence & reasoning |
|---|---|---|---|
| Native dialogs | ★★★★ | **IMPROVE** (small) | "Add Contact" dialog live: rounded, correctly stock-structured, labels intact, themed inputs. Two nits: **both** "Save & Close" and "Save & New" render solid-primary (visual priority tie — make the secondary action outline), and the third-party AI Coach widget floats *above the modal backdrop* (z-index — belongs to that module, flagged as an external bug). |
| Native form sheet/cards | ★★★★ | **KEEP** | `backend.scss` scopes legacy card styling to `:not(.vu-form)` (lines 41-136) — the "single owner per context" comment shows the tug-of-war was already resolved. Native forms get card groups, compact labels, underline inputs. |
| Inputs & focus | ★★★½ | **IMPROVE** | Quiet underline-at-rest inputs are good (`backend.scss:1258-1281`). But `box-shadow: none !important; outline: none !important` on focus (lines 814-820) leaves only a border-color change — weak keyboard-focus affordance, WCAG 2.4.7 risk. Restore a 2-3px brand focus ring via `:focus-visible` (mouse users keep the quiet look). |
| Many2one dropdown | ★★★ | **IMPROVE** | Observed live (country picker): near-stock — sharp corners, cramped rows, no shadow depth. Token pass: radius-md, 6px row padding, `--vu-shadow-md`, hover tint. Pure CSS, no JS. |
| Checkboxes/radios/switches | ★★★★ | **KEEP** *(radios observed in dialog; rest inferred)* | Themed via Bootstrap variable bridge; brand-blue radio dots observed. |
| Date picker | — | **TOKEN** *(not reached live)* | Not opened during inspection (time-boxed). Inherits Bootstrap/Odoo datetime picker + token colors; include it in the playground so it's verified visually there. |
| Badges (`bg-info`/`bg-secondary`) | ★★★ | **IMPROVE** | Live pills look fine, but implementation is gradient fills + `!important` walls + fixed 100px inner input widths (`backend.scss:671-767`) — violates flat-mono and fights field rendering. Flatten to tinted-bg/solid-border pills on tokens. |
| Chatter | ★★★★½ | **KEEP** | Bottom, full-width (project rule), white card, compact 13px, clean topbar (observed live on contact form). Only the `!important` font-size ladder gets absorbed into tokens over time. |
| Notifications / toasts | ★★★ | **TOKEN** *(inferred)* | No custom styling today beyond Bootstrap state-color bridge — token pass + playground sample. |
| Empty states | ★★★ | **TOKEN** *(partially observed)* | "Add Contact" ghost tile observed (fine). Stock empty-state illustrations elsewhere remain Odoo-purple — recolor via token or neutral illustration. |
| Loading | ★★★★ | **KEEP** | Custom dual-ring spinner + blur overlay (`loading_spinner.scss`); skeleton loaders added to the playground as a new shared component (currently none exist). |

### 3.6 Cross-cutting findings (bugs found during audit — fix regardless of theme work)

| # | Bug | Where |
|---|---|---|
| B1 | Browser theme-color meta is legacy teal `#0F6D66`, should be `#1565C0` | `health_theme/views/webclient_templates.xml:7` |
| B2 | `background: rgba(var(--vu-surface-card), 0.95)` is invalid CSS — sticky action bar has no backdrop, causing the observed scroll-overlap | `backend.scss:621` |
| B3 | AI Coach floating widget overlaps content at 1440px (Staff Roster, list rows, Next Best Action) and renders **above modal backdrops** | AI coaching module (not health_theme) — z-index + right-edge offset |
| B4 | Contact form right column: fields render with placeholders only, no labels (4 labels in entire form DOM) | custom contact form arch (verify `crm_contact_form_view`) |
| B5 | CMS sidebar fixed-width at tablet width crushes content (calendar unusable at 768px) | health_cms_sidebar responsive |
| B6 | Statusbar buttons use stock-Bootstrap `#0d6efd` gradient, not brand `#1565C0` | `backend.scss:955` |

---

## 4. What must NOT change

1. **VU Form Engine internals** — `vu_form_compiler.js`, `vu_form_renderer.js`, `vu_form_state.js`. Fail-closed, kill-switched, battle-tested. The engine consumes retargeted tokens; its logic is untouched.
2. **Structural contracts** — `.o_form_sheet_bg` / `.o_form_sheet` / chatter anchors never renamed (the compiler's own documented contract).
3. **The VU form layout language** — hero, stat strip, progress rail, card sections, segmented tabs. It is the product's identity and already excellent.
4. **List-view design, chatter placement, control panel, loading spinner, state system, side sheet, progress rail widgets.**
5. **The compact 13px density** as the default — it was a deliberate, correct call for this data-dense domain.
6. **Settings-app exclusion** and all existing opt-out mechanisms (`vu-form-native`, `js_class` sets, kill-switch).
7. **`health_pwa`** — out of scope entirely.
8. **The existing `[data-theme='dark']` block** — stays as-is, dormant (dark mode descoped).

---

## 5. What transfers from world-class design systems (and what doesn't)

| Concept | Source | Adopt? | How |
|---|---|---|---|
| Three-layer token architecture (palette → semantic → component) | Material 3, Carbon, ShadCN | **Yes — core of the engine** | §6.1. The repo is already 70% there. |
| Runtime theming via CSS custom properties, zero rebuild | ShadCN, Radix, Stripe | **Yes** | Generated `:root` override block served per company (§6.3). |
| Semantic-only styling rule (components never read raw hex) | Carbon, Atlassian | **Yes** | Lint rule + refactor list (§8). |
| Quiet-at-rest inputs, focus-visible rings | Linear, GitHub | **Yes** | Search box + input focus fixes (§3.2, §3.5). |
| Segmented controls, pill tabs, command-palette-grade launcher | Linear, Notion, Slack | **Yes** | Already present (tabs); apps-menu redesign (§3.2). |
| Density switching (comfortable/compact/large) | Gmail, Atlassian, Airtable | **Yes** | Space-scale multiplier token (§6.1). |
| Elevation restraint (1-2 shadow levels per surface) | Apple HIG, Material | **Yes** | Already respected; keep. |
| Glassmorphism / heavy blur surfaces | (trend) | **No** | Conflicts with flat-mono rule, GPU cost on clinic hardware; offered only as a card-style preset value, default off. |
| Per-user theme personalization | Slack, Monday | **No** | Explicitly descoped (admin-published single theme). |
| Animated micro-delights (confetti, springy lists) | Linear at times | **No** | Healthcare context; reduced-motion discipline already in place. |
| Full component library replacement (Radix-style primitives) | Radix/ShadCN | **No** | Would fork Odoo's OWL components and destroy upgrade safety. We theme Odoo's primitives, never replace them. |

---

## 6. Theme Engine architecture

### 6.1 Token model — three layers, one source of truth

```
Layer 1  PALETTE      --vu-p-*    raw values a preset defines (blue-600: #1565C0, radius-md: 8px, …)
Layer 2  SEMANTIC     --vu-*      meaning-level (existing! brand-primary, surface-card, border-soft, …)
Layer 3  COMPONENT    --vuf-*, --bi-*, sidebar/navbar vars — derive from Layer 2, never from raw hex
```

- **Layer 2 already exists** (`primary_variables.scss:203-293`) and is the engine's contract. Presets and the builder only ever write Layer 1 + a small set of Layer 2 aliases.
- **Unification step:** `--vuf-*` values in `vu_tokens.scss` are re-pointed at Layer 2 (`--vuf-primary: var(--vu-brand-primary, #1565C0)` — fallback keeps today's value byte-identical if a token is missing). Same for the CMS sidebar palette and dashboard hexes. This is the single most important refactor: after it, *one* published theme restyles VU forms, native forms, dialogs, sidebar, dashboards, and BI.
- **New tokens added** (all with defaults equal to today's rendering, so installing the engine changes nothing):
  `--vu-density` (space multiplier 0.85/1/1.15), `--vu-radius-scale`, `--vu-shadow-depth` (0-3), `--vu-navbar-height`, `--vu-navbar-bg`, `--vu-sidebar-width`, `--vu-sidebar-bg/-text/-hover`, `--vu-table-row-py`, `--vu-motion-scale` (0 = reduced), `--vu-font-body`, `--vu-font-headings`, `--vu-font-size-base`, `--vu-card-style` (flat/raised/outlined via composed tokens).
- **SCSS compile-time variables stay** for what Bootstrap needs at build time (`$primary`, `$border-radius`, …). The runtime engine covers everything users may configure; the SCSS layer keeps stock-Bootstrap components in the brand ballpark as a safety net. (Consequence: Bootstrap-compiled colors are the one place a radically different preset can drift — the playground makes this visible, and the generated CSS also overrides the handful of Bootstrap CSS vars Odoo 19 exposes: `--primary`, `--o-action`, etc.)

### 6.2 Data model (new files in `health_theme/models/`)

```python
class VuTheme(models.Model):
    _name = "vu.theme"
    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company")          # single-company today; future-proof
    state = fields.Selection([("draft", "Draft"), ("published", "Published"), ("archived", "Archived")])
    token_values = fields.Json()                          # {"vu-brand-primary": "#1565C0", ...} — Layer 1/2 only
    preset_key = fields.Char()                            # provenance (which preset it started from)
    version = fields.Integer(default=1)                   # bumped on publish → cache busting
    # publish(): archive current published, set state, bump ir.config_parameter version
    # duplicate(), export_json(), import_json() — plain JSON round-trip

class VuThemePreset(models.Model):                        # seed data, noupdate=0 (deliberately updatable)
    _name = "vu.theme.preset"
    key, name, description, token_values (Json), preview_colors (Json)  # swatch strip for the picker
```

`res.config.settings` gets one button ("Open Theme Studio") — no token fields in Settings; the Studio is the single editing surface (avoids muk_web_colors' save-and-reload UX).

### 6.3 Serving tokens — generated CSS, no asset rebuild

- Controller route `GET /vu_theme/tokens.css?v=<version>` returns
  `:root { --vu-brand-primary: #...; ... }` for the **published** theme, `Cache-Control: public, max-age=31536000, immutable` (version param busts it — same pattern as health_pwa's `?v=` asset URLs).
- Injected via a `<link>` in a `web.webclient_bootstrap` inheritance **after** the compiled bundles, so its `:root` block wins the cascade over the SCSS-emitted defaults without any `!important`.
- Published version number rides on `ir.config_parameter` `health_theme.theme_version`, exposed through the existing `session_info()` patch (`ir_http.py` already does exactly this for the kill-switch).
- **No `ir.asset`/SCSS recompilation at publish time.** Publishing = write JSON, bump version, `reload()`. Rollback = re-publish any archived theme row (history is free).
- Failure mode: if the route 500s or the JSON is malformed, the app renders with the SCSS-compiled Việt Úc defaults — the theme engine can only *tint*, never break layout. (The generator validates values server-side: colors must parse as hex/rgb, dimensions clamped to sane ranges, unknown keys dropped.)

### 6.4 Draft / Preview / Publish / Discard lifecycle

```
pick preset or edit tokens (Studio, draft row)
        │ live-applied ONLY to the Studio tab: inline style on <html> (document.documentElement.style.setProperty)
        ▼
"Preview full app" → same inline vars kept while navigating (Studio sets them via a tiny
        │ token-loader service reading sessionStorage["vu_theme_draft"]; other users see nothing)
        ▼
Publish (confirm dialog, admin-only, group_system) → server: draft→published, version++ → reload
Discard → delete draft row + clear sessionStorage → instant revert, zero server state
```

Preview is **client-side only** (inline CSS vars override the `<link>` stylesheet by specificity) — it cannot affect other users, satisfies the "test first, publish or discard" requirement exactly, and costs one tiny JS service (~40 lines) loaded in `web.assets_backend`.

### 6.5 OWL components (new, under `health_theme/static/src/studio/`)

Following the `biz_bi` pattern (client action in `registry.category("actions")`, `useState`, services — see `biz_bi/static/src/components/home/home_action.js`):

```
theme_studio_action.js/.xml      client action "health_theme.theme_studio"; menu under Settings
  ├─ PresetGallery               cards w/ swatch strips (from vu.theme.preset)
  ├─ TokenEditor                 grouped accordions: Colors / Typography / Shape / Density / Motion / Layout
  │    ├─ ColorField             swatch + hex input + native <input type=color> + live WCAG AA badge
  │    ├─ SelectField / SliderField (radius, density, shadow depth, sidebar width…)
  │    └─ undo/redo (in-memory stack), reset-to-preset, import/export JSON
  └─ Playground                  the showcase (below) — reads the same draft tokens live
```

### 6.6 Playground (Theme Preview page)

Static OWL markup that *mimics* Odoo components with the real CSS classes (no records, no ORM — fast, safe, permission-free). Sections, in order: buttons (all variants + statusbar pills), stat buttons, inputs (rest/hover/focus/error/disabled), many2one + tags + selection + date picker (real widgets mounted on dummy models where cheap, static markup where not), status bar + progress rail, notebook tabs, list-table sample (header + rows + pills), kanban cards, KPI/dashboard cards, badges/tags/avatars, alerts + toasts, dialog (opens a real `Dialog`), chatter mock, activity row, search panel snippet, breadcrumb + pager, spinner + skeleton, tooltips/popovers, empty state — **and two full form specimens: a VU-engine form section and a native-form section**, so both paths are visually verified before any publish.
Each section carries a contrast self-check ribbon (computed from draft tokens) flagging any text/surface pair below WCAG AA 4.5:1.

---

## 7. Preset definitions (shipped seed data)

All presets keep: Lucide mask icons, 4px spacing scale, flat mono (no gradients), the VU form layout. They vary only token values. Deep Blue remains the default; logo colors stay reserved in every preset.

| # | Preset | Primary | Surfaces / feel | Type | Radius | Shadow | Density |
|---|---|---|---|---|---|---|---|
| 1 | **Việt Úc (default)** | `#1565C0` | White cards on `#FAFAFA`, exactly today's rendering | Montserrat/Segoe 13px | 8 | 1 | Comfortable |
| 2 | **Minimal White** | `#18181B` (zinc-900) | Near-borderless, hairline `#E4E4E7`, shadow 0 | Inter 13px | 6 | 0 | Comfortable |
| 3 | **Linear-inspired** | `#5E6AD2` | Cool grays `#FBFBFC`/`#F4F5F8`, crisp 1px borders | Inter 13px | 8 | 1 | Compact |
| 4 | **Notion-inspired** | `#2F3437` accents, links `#0B6E99` | Warm whites `#FFFEFC`, generous whitespace | Segoe/system 14px | 4 | 0 | Large |
| 5 | **Slack-inspired** | `#611F69` (aubergine sidebar `#3F0E40`) | White content, colorful state accents | Lato/system 13px | 8 | 1 | Comfortable |
| 6 | **Corporate Blue** | `#0B5CAB` | Cool `#F3F6F9` panels, denser tables | Segoe 13px | 4 | 1 | Compact |
| 7 | **Elegant Green** | `#1B7A53` (medical) | Sage-tinted panels `#F4F8F6` | Montserrat/Segoe 13px | 8 | 1 | Comfortable |
| 8 | **High Contrast (WCAG AAA)** | `#003E92` | Pure white, `#1A1A1A` text (≥7:1 everywhere), 2px borders, visible 3px focus rings, motion 0 | Segoe 14px | 4 | 0 | Large |

Each preset JSON also defines: state-color set, sidebar bg/text, navbar bg, link color, hover/active tints, table row padding, chart series ramp (6 colors derived from primary + state hues). Presets are data — adding a ninth later is a JSON record, not code.

---

## 8. CSS/SCSS architecture & cleanup

1. **Split `backend.scss`** (1,549 L monolith) into partials: `_chrome.scss` (navbar/control-panel/search), `_forms_native.scss`, `_lists.scss`, `_chatter.scss`, `_buttons.scss`, `_badges.scss`, `_icons.scss`, `_compat.scss` (the `:not(.vu-form)` legacy block). Pure move — bundle output byte-comparable except intended fixes.
2. **Flat-mono enforcement pass** (also a visual improvement): statusbar buttons (gradients→flat tokens, keep pill shape), badges (gradients→tint+border), remove shine-sweep animation. This closes the gap with the project's own stated rule.
3. **Token-only rule:** new/edited rules may reference only `var(--vu-*/--vuf-*)`; raw hex allowed solely in `primary_variables.scss` Layer 1. Enforce by convention + a grep check in CI/deploy script (`grep -nE '#[0-9a-fA-F]{3,8}' src/scss --exclude primary_variables.scss`).
4. **`!important` reduction target:** 343 → <150. Keep the justified classes (state-visibility system, legacy-override compat block); remove the ones that die naturally with the gradient/badge/icon-map cleanup (~120 by count of the affected blocks). Not a goal in itself — done only where the owning refactor already touches the lines.
5. **Icon consolidation:** single lucide set in `health_theme/static/src/img/lucide/` (superset of both current folders), `backend.scss` icon tints derived from a 6-color token ramp instead of 22 hardcoded pairs. `health_base` paths kept working via file copies until callers migrate (no breakage).

---

## 9. Accessibility & responsive improvements

- **Focus:** restore `:focus-visible` rings (2px, `--vu-brand-primary`, 2px offset) on inputs, buttons, list rows, tabs; remove the blanket `outline: none !important` (`backend.scss:814-820`). Mouse users see no change.
- **Contrast:** builder blocks publishing when any semantic text/surface pair < 4.5:1 (override checkbox with warning for deliberate brand choices); High Contrast preset ships at AAA.
- **Placeholder-as-label** (bug B4): fix in the owning view arch — labels visible, placeholders as hints only.
- **Reduced motion:** already honored in the engine scope; extend the media query to theme-added transitions; `--vu-motion-scale: 0` token gives an explicit off switch per theme.
- **Responsive:** sidebar collapse-to-icons ≤1024px with flyout labels (fixes B5); progress-rail scroll-snap on narrow widths; keep existing font step-downs at 1400/1200px. The VU form's own 768px behavior (stacking cards, wrapping buttons) already works — observed live.
- **Keyboard:** the Studio itself fully keyboard-navigable; apps-menu replacement gets type-ahead + arrow navigation.

---

## 10. Performance strategy

- Publish = one cached immutable CSS file (<4 KB) + version bump. **No SCSS/asset recompilation, no bundle invalidation**, no FOUC (link loads in `<head>` after bundles, before first paint).
- Preview = inline style properties on `<html>` — zero network, instant, per-tab.
- Non-Studio pages gain only the token-loader service (~40 lines) and the `<link>`; the Studio bundle is lazy-loaded (`web.assets_backend_lazy` or dynamic import in the client action) so daily users never pay for it.
- CSS custom-property updates restyle without reflow-storms (browsers invalidate paint, not layout, for color tokens; dimension tokens like density are Studio-preview-only until publish+reload).
- Existing budget unchanged: no new fonts by default (presets that use Inter/Lato declare system-font fallbacks; webfont loading is opt-in per preset with `font-display: swap`).

---

## 11. Risk & compatibility

| Risk | Mitigation |
|---|---|
| Regression on existing screens | Token retargeting keeps identical default values (fallbacks in every `var()`); playground diff-check before publish; deploy is SCSS/JS-only (stop/start, no `-u` upgrade needed per deploy workflow). |
| Form compiler breakage | Not touched. All engine work is CSS/tokens/new files. |
| A radical preset breaking readability | WCAG gate in builder + preview-first flow + one-click rollback to any archived theme. |
| Odoo 20 upgrade | Engine is additive (new models, one controller, one template inherit, token CSS). The fragile piece remains the pre-existing compiler patch — unchanged risk, kill-switch intact. |
| MUK modules | Not installed in vietuat (verified via DB). Repo-only. Exclude from deploys; delete folders in a later hygiene commit. |
| Multi-company | `vu.theme.company_id` nullable = global theme today; per-company resolution is a one-line lookup later. |

---

## 12. Implementation roadmap (for later approval — nothing is being built yet)

| Phase | Content | Size | Risk |
|---|---|---|---|
| **1. Token unification + bug fixes** | Re-derive `--vuf-*`/sidebar/dashboard tokens from Layer 2; add new knob tokens with today's defaults; fix B1 (meta color), B2 (action-bar rgba), B6 (statusbar brand color); flat-mono cleanup of badges/statusbar buttons; focus-visible restoration; search-box quiet-at-rest | M (2-3 days) | Low — visual output intended ≈ identical except the 6 listed fixes |
| **2. Engine core** | `vu.theme` + preset models, tokens.css controller, webclient link, token-loader service, publish/rollback, seed 8 presets | M (3-4 days) | Low — additive only |
| **3. Theme Studio** | Client action: preset gallery, token editor (undo/redo/import/export), playground with both form specimens, WCAG gate, Preview/Publish/Discard | L (5-7 days) | Low-medium — new UI, no existing surface touched |
| **4. Chrome upgrades** | Apps-menu grid launcher, sidebar collapse ≤1024px + width token, calendar pill softening, progress-rail narrow behavior, backend.scss split | M (3-4 days) | Medium — touches shared chrome; each item independently revertible |
| **5. Polish & hygiene** | Icon consolidation, `!important` reduction alongside, B4 label fix in owning view, B3 handoff to AI-coach module, MUK folder removal | S-M | Low |

Module layout after Phase 3:

```
health_theme/
├── models/            ir_http.py, vu_theme.py, vu_theme_preset.py, res_config_settings.py
├── controllers/       theme_tokens.py                (GET /vu_theme/tokens.css)
├── data/              theme_presets.xml              (8 presets, JSON payloads)
├── views/             webclient_templates.xml, theme_menus.xml, res_config_settings.xml
├── security/          ir.model.access.csv            (theme models: group_system write, all read)
├── static/src/
│   ├── scss/          primary_variables.scss, vu_tokens.scss, partials per §8, studio/studio.scss
│   ├── services/      theme_loader_service.js        (draft-preview vars, ~40 lines)
│   ├── studio/        theme_studio_action.js/.xml, token_editor/, playground/, presets/
│   ├── js/            (existing form engine — untouched)
│   └── img/lucide/    (consolidated icon set)
```

**Code-generation strategy for Claude Code (Phase execution):** each phase is one deploy unit; Phase 1 ships behind visual-diff discipline (before/after screenshots of the five audited screens at 1440px, per the pixel-validation rule); Phases 2-3 are pure additions verified in the playground; every deploy follows the standard VietUcUAT workflow (scp → /tmp → sudo cp → chown → `-u health_theme` upgrade only when Python/XML changed, stop/start only for asset-only changes).

---

## Appendix A — requested-deliverable checklist

| # | Requested | Where |
|---|---|---|
| 1 | UI/UX review of health_theme | §3 (per-component, dual form paths), §2 method |
| 2 | Areas NOT to change | §4 |
| 3 | Areas to improve | §3 verdicts IMPROVE/REDESIGN, §3.6 bugs |
| 4 | Theme Engine architecture | §6.1-6.4 |
| 5 | Theme Builder architecture | §6.5 |
| 6 | Theme Preview page design | §6.6 |
| 7 | Theme configuration models | §6.2 |
| 8 | OWL component architecture | §6.5 (+ biz_bi pattern reference) |
| 9 | CSS architecture | §6.1, §8 |
| 10 | SCSS structure | §8.1, §12 module layout |
| 11 | Asset loading strategy | §6.3, §10 |
| 12 | Performance | §10 |
| 13 | Accessibility | §9 (+ High Contrast preset) |
| 14 | Responsive | §9, §3.2 sidebar, §3.4 progress rail |
| 15 | Recommended animations | §3.1 Animations, §5 (what not to adopt) |
| 16 | Modern icon strategy | §3.1 Icons, §8.5 |
| 17 | Theme preset definitions | §7 |
| 18 | Dark mode strategy | Descoped by decision; §4 item 8 (tokens stay dark-ready) |
| 19 | Implementation roadmap | §12 |
| 20 | Folder/module structure | §12 |
| 21 | Code generation strategy | §12 final paragraph |
