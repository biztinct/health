# CareJiyo parallel domain, phase 1

Target: `VietUcUAT`, `54.206.18.111`. New HTTPS addresses:
`carejiyo.com`, `www.carejiyo.com`, `hhh.carejiyo.com`.

This release adds aliases to existing databases, not a canonical-domain switch.
Care Command continues to be operated on `carejiox.com` and existing tenant
addresses. Keep all provider registrations, `web.base.url`, URL freezing,
`biz_tenants.apex_domain`, `/etc/biz-tenants.conf`, OAuth/call relay settings,
database names, mail records, and old virtual hosts/certificates unchanged.
Public canonical/SEO URLs and branding are also unchanged in this phase.

## Deployment scope

Only nginx virtual hosts, their shared proxy snippet, the existing root-owned
hostname map, and the new certificate are changed. No Odoo addon, database
schema, or application setting is changed. The template remains inaccessible.
The existing `biz_domain_router` is already loaded server-wide and reloads its
root-owned map atomically by file timestamp; no Odoo restart is necessary.

Before each deployment, recheck branch `19.0` and working-tree changes, package
this entire directory from the latest combined branch state, and record the
commit. Preserve other sessions' files and existing hostname map entries.
Serialize server changes with `/tmp/carejiox-deploy.lock`; map writes also use
`/run/lock/carejiox-domains.lock` like `biz-domain-map`.

1. Back up nginx, `/etc/carejiox-domains.json`, and certificate configuration
   to a root-readable directory under `/var/backups/`.
2. Install `bootstrap.conf` as `/etc/nginx/sites-available/carejiyo.com` and
   enable its symlink. Create `/var/www/carejiyo-acme/.well-known/acme-challenge/`.
   Run `nginx -t` before reloading. Only ACME challenges are served over HTTP.
3. In GoDaddy change the new domain's parked `A @` to `54.206.18.111`, keep
   `CNAME www = carejiyo.com`, and add `A hhh = 54.206.18.111` (TTL 600).
   No wildcard or forwarding is needed for these three explicit names.
   Preserve all NS, SOA, MX, TXT, domainconnect, and old-domain records.
4. Confirm authoritative DNS and external HTTP challenge delivery for all
   three names, then reuse the existing Let's Encrypt account:

   ```sh
   sudo /snap/bin/certbot certonly --webroot -w /var/www/carejiyo-acme \
     --cert-name carejiyo.com \
     -d carejiyo.com -d www.carejiyo.com -d hhh.carejiyo.com \
     --non-interactive --keep-until-expiring \
     --deploy-hook 'systemctl reload nginx'
   ```

5. Under the map lock, merge `domain-map-additions.json` into the latest map;
   refuse an existing mapping to a different database. Write by atomic rename,
   owner root, mode 0644. Do not replace unrelated mappings. Verify the existing
   router accepts the result before activating the site.
6. Install `proxy.conf` as `/etc/nginx/snippets/carejiyo-proxy.conf`, and replace
   the bootstrap site with `carejiyo.conf`. Test nginx, reload it, then verify
   HTTPS with certificate validation enabled. Restore affected configuration
   from the backup if validation fails.

## Checks

- Verify each new host and corresponding old host reaches the correct login
  and public homepage; no database selector or cross-tenant routing.
- Verify HTTPS certificate SANs/expiry, HTTP redirects preserving paths and
  query strings, stylesheet delivery, websocket upstream, and 404 on database
  manager routes. Unknown, template and staging hosts must remain rejected.
- In Chrome navigate from public home to Sign in for master and HHH; do not
  bypass certificate warnings. Check existing Care Command in its old origin
  when an authenticated session is available; do not send real messages/calls.
- Confirm channel URL parameters and old-domain nginx configurations match
  the pre-deployment values. No provider webhook registration is changed.
- Run `certbot renew --cert-name carejiyo.com --dry-run
  --no-random-sleep-on-renew`; keep `snap.certbot.renew.timer` active.
- Remove test-generated PNG files; do not remove existing assets/screenshots.

## Rollback and next phase

Keep the old domains serving throughout. To withdraw new aliases, restore the
new domain's exported DNS records, remove only this release's enabled nginx
site/snippet, and remove only this release's three map entries under the same
locks. Validate nginx before reload; preserve concurrent map additions.
Do not delete or change any old-domain certificate or virtual host.

A later canonical-domain switch needs channel-specific URL separation: relay
reconciliation currently derives Meta/VoIP settings from the platform apex;
Zalo and other OAuth flows derive return URLs from `web.base.url`, and popup
completion checks the browser origin. Changing these settings now would break
the promise to retain current channel registrations. New aliases are suitable
for public-page/login verification, not channel onboarding or reconnection.
