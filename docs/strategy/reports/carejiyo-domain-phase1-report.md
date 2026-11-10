# CareJiyo domain migration — phase 1

Date: 10 November 2026 (Australia/Sydney).

The new domain now serves the existing platform and HHH clinic through HTTPS.
This is the parallel-domain preparation stage, not the final canonical-domain
or channel migration. Continue operating Care Command through the old domain.

## Deployment

- Runtime configuration commit: `ea5a7a0d81ee54780843c085cc63d5c9943094c7`.
- Target: `VietUcUAT`, `54.206.18.111`, existing nginx/Odoo server.
- `carejiyo.com`, `www.carejiyo.com` map to existing database `carejiox`.
- `hhh.carejiyo.com` maps to existing database `hhh`.
- Template `carejiox_template` stays private; its settings were checked and
  preserved. No application addon, schema, or database name was changed.
- Latest combined `19.0` configuration was packaged before both bootstrap and
  TLS activation. Exact deployed-file comparisons passed. Existing local
  untracked documents, PNG assets, and outputs were excluded from the commits.
- Config backup: `/var/backups/carejiyo-domain-20261110T002838Z-h61suph3`.
  Includes nginx, old domain map, renewal configuration, and the selected
  non-secret application/channel settings used for before/after comparison.

Files: `ops/carejiyo-domain/bootstrap.conf`, `carejiyo.conf`, `proxy.conf`,
`domain-map-additions.json`, and `README.md`.

## GoDaddy and certificate

The owner exported both zones before changes. The new domain had no forwarding.
Changed only `carejiyo.com` web records:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | @ | 54.206.18.111 (replaces Parked) | 600 |
| A | hhh | 54.206.18.111 (new) | 600 |
| CNAME | www | carejiyo.com (preserved) | 3600 |

The explicit HHH record was used instead of a wildcard because only known
hostnames are being enabled in this phase. NS, SOA, MX, TXT, domainconnect,
old-domain DNS and forwarding settings were not changed.

The new Let's Encrypt certificate covers all three new names, expires on
7 February 2027 at 23:33:14 UTC, and renews through HTTP-01 with a reload hook.
No certificate was purchased and no old certificate was removed.

## Validation

- Server verification: **59/59 passed**. Includes all six old/new homepage,
  login and stylesheet URLs, database-manager blocking, HTTP redirect path and
  query preservation, rejected template/staging/unknown hosts, websocket
  upstream connectivity, active services, and deployed-file hashes.
- Existing UAT account authentication over HTTPS: **2/2 passed**, on
  `carejiyo.com` and `www.carejiyo.com`, selecting `carejiox`. Test sessions
  destroyed afterwards; no passwords printed or committed.
- Chrome: public homepage → interactive preview → Sign in on the new main
  domain; HHH homepage → EN → Open workspace → login form on the new tenant
  domain. Both passed without certificate-warning bypasses.
- Chrome: authenticated old domain → CRM → Care Command passed.
- Certificate renewal simulation after final deployment: **passed**.
- Existing nginx files and selected canonical/channel parameters on
  `carejiox`, `hhh`, and `carejiox_template`: **unchanged**.
- No Odoo service restart, module upgrade, or database migration was required.

Evidence is in `carejiyo-domain-phase1-evidence/`. Browser evidence is textual;
screenshots were viewed in memory, with no test PNG or screenshot files saved.
The only temporary HTTP challenge probe is removed after verification.

The first TLS readiness request raced nginx's asynchronous reload and saw the
old default certificate. Activation rolled back to the bootstrap site as
designed; bounded readiness retries then passed. No TLS verification was
disabled and no old host was changed.

## Remaining migration scope

Canonical URL settings, tenant provisioning apex, branding, SEO links, email
identities, existing PWA installations, and channel provider registrations
are deliberately not migrated in this phase. New OAuth or channel reconnect
flows should still be initiated from the old domain. No real message/call
delivery test, provider reconnect, or new-domain authenticated HHH browser
workflow was performed; those are not claimed as verified here.

Before making CareJiyo the primary application domain, separate the channel
addresses from the canonical application URL. In the current code Meta/VoIP
relay reconciliation derives callback settings from the platform apex, Zalo
and other OAuth flows derive URLs from `web.base.url`, and popup completion
depends on the origin. Changing those shared settings now would invalidate
the intended separation. Old links and callbacks remain directly served.

Rollback instructions are in `ops/carejiyo-domain/README.md`; remove only this
release's three mappings and new virtual host, preserve unrelated mappings,
and restore the new domain's exported DNS if rollback becomes necessary.
