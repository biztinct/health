# CareJiyo and Việt Úc homepages

Two independent public QWeb documents, served at `/` by the existing Odoo
website controller. Database identity selects the page: `carejiox` is the
English CareJiyo software platform (served on both carejiox.com and carejiyo.com); `hhh` is the bilingual Việt Úc client. Other
customers (including `carejiox_template`) retain the original website route.
Neither a host header nor a visitor query can select another tenant's page.

The client starts in Vietnamese and offers `?site_lang=en` / `?site_lang=vi`.
A validated, host-only, HttpOnly preference cookie remembers that choice.
Responses are private/no-store, with explicit language/canonical/alternate
metadata. Staff application language, login, portal and booking routes are
unchanged. The standalone public templates load only their own local assets;
there are no external fonts, scripts, analytics or patient-data API calls.

CareJiyo demo links open a draft in the visitor's email client addressed to
`ash@biztinct.com`; they do not send a message. The hhh page is an
application entry point, not a healthcare service brochure. Its parent website
remains https://pkgdvietuc.com/. Workspace and mobile links use existing login
redirects to `/bizapp` and `/health_pwa`. Families use their issued care links.

## Visual experience and assets

### Platform (CareJiyo), since 19.0.3.0.0

A warm, people-first page: cream background, brand blue `#1565C0`, the logo's
orange `#FB8C00` and a scrubs teal. Flat single colours only (no gradients).
It has its own `static/src/platform.css` and `platform.js`; it no longer loads
`home.css`/`home.js`, which now serve only the client page.

Scenes are hand-drawn flat SVGs in `static/img/site/` (home visit, nurse on a
scooter, nurse at the front door, doctor with patient). Every person and screen
is illustrative; the page says so. Floating status cards over the hero pause
with the motion switch and under reduced-motion. Role tabs (nurses & doctors,
coordinators, families, clinic managers) support click, arrows, Home/End.

Brand: `carejiyo-lockup.svg` (+ `-dark`) keeps the Care Pulse mark unchanged;
the wordmark is Montserrat Bold outlined to paths ("carejiyo", orange j-dot).
`carejiyo-mark.svg` is the favicon; `carejiyo-social.jpg` is the share card.
The old `carejiox-*` files stay for the client page and other references.
Canonical/og URLs still point at carejiox.com until the domain switch phase
(see `ops/carejiyo-domain/README.md`).

Copy is plain English and avoids unsupported claims: features named are the
shipped ones (booking, scheduling, field app with offline/glove/sun modes,
"On my way" with family notice, care records, medicines, video visits, family
messages, invoicing/claims with government filing where configured).

### Sign-in pages (platform only), since 19.0.3.1.0

`views/login.xml` inherits `web.login_layout` after `website.login_layout`.
For every database except `carejiox` the website frame is kept as is (tenants
keep their own sign-in page and identity). On `carejiox` a two-panel CareJiyo
screen replaces the website header/footer (which carried the stock
+1 555-555-5556 sample phone): care scene on the left, form on the right,
one column with a short picture band on phones. The form markup from
`web.login` and its inherits (User ID label, "Choose a user", reset link,
passkey) is untouched and restyled only by `static/src/login.css`, scoped
under `.cj-auth`. The same shell frames reset-password, signup and
second-factor pages. Bump the `login.css?v=` query when the CSS changes.

Headless Chrome keeps the login form `d-none` (the user-switch component
never boots under virtual time) on every database; check it in a real
browser, e.g. a same-origin 390px iframe.

Website record 1 on `carejiox` (serves carejiyo.com) had its logo set to
`carejiyo-lockup.svg` by a one-off shell script on 2026-11-10 (previously the
Viet Uc flower). Not module data, because hhh/template must keep their logos.

### Client (Việt Úc)

A locally rendered canvas care network, floating interface cards, waveform
animation, orbital feature graphics and scroll reveals create the experience.
The role explorer supports clicks and arrow/Home/End keys. A motion switch
pauses decoration; reduced-motion preferences are respected. Canvas rendering
is capped at 30fps and stops drawing offscreen or while the page is hidden.
All previews are illustrative and contain no patient data.

The client logo comes from its existing public website. Previously downloaded
clinic photos remain as assets but are not used by the application homepage.
DM Sans fonts are local.

## Deployment and verification

Install `health_public_site` through `carejiox-deploy` on `carejiox`, `hhh`
and `carejiox_template`. No new dependency is needed: `website` is already
installed on all three. Template cron jobs must remain inactive.

Run `-t /health_public_site` per database. The five HttpCase tests cover
actual public rendering and assets, anchor targets, tenant isolation,
English/Vietnamese metadata and preference, and malformed-language input.
Then test both deployed domains in Chrome (desktop and phone viewport),
including preview tabs/keyboard, motion controls, mobile menus, language switching and
login navigation. Delete only screenshots generated by this QA run.

Rollback: uninstall this module through the deployment wrapper on the target
database; saved original website pages are preserved and automatically resume.
