# Tenant identity and workspace

The Payobook source in `../gitlocal` supplied the three branding levels,
source-text debranding seams, error-page references, company profile pattern,
and resumable setup pattern. Carejiox keeps its existing guided staff creation,
support consent switch/time limits/trail, and immediate platform actions.
No session-approval, sensitive-action approval, or email-invitation policy was added.

## Implementation

- `health_tenant_workspace`: database identity, company profile, setup guide,
  activity summaries, and branding across server templates, translated labels,
  the sidebar, loading screen, mobile/desktop manifests, and notification fallbacks.
  Names default to the tenant company when a custom display name is blank.
  Runtime records, identifiers, code, and customer-entered text are not renamed.
- `biz_tenants`: creation-time country/currency and branding choices; existing
  customer branding editor; applied-state comparison/retry; domain DNS and HTTPS
  controls. Applying branding never calls the old image seeder.
- `biz_errors`: Payobook's frontend error screens, adapted to Carejiox's brand
  parameters. Short random references link the page to the server log. JSON-RPC
  errors retain the framework's existing behaviour.
- `biz_domain_router`: server-wide exact-host mapping, root-owned atomic JSON,
  no trust in a client-provided database header. Root scripts guard unrelated
  nginx blocks and customer ownership when removing custom domains.

## Scope and limitations

The company editor is for a tenant's company, not arbitrary company IDs. Its
writes are serialised and revision-checked; the change history records the actor
and changed fields and cannot be edited or deleted through the application.
Other history sources keep their own ACLs; the merged timeline contains summaries,
not clinical field values or request bodies. Times are UTC.

Country/currency applies to a newly provisioned company. It does not change the
chart of accounts, taxes, or country localisation. Currency changes are refused
when accounting entries exist. Existing customer currency has no new edit path.

New brand settings take effect on the next page load. Customer-controlled mail
sending domains and third-party OAuth redirect allowlists are separate provider
configurations; attaching a web domain does not alter either.

The deployment scope is `carejiox`, `carejiox_template`, and live tenant `hhh`
on `VietUcUAT` (`54.206.18.111`). The template remains quiet. The temporary
`cjx-identity-qa` database and `white-label-check.carejiox.com` are test fixtures.

## Validation

Automated tests cover permission boundaries, caller-supplied company context,
immutable history, revision checks, branding reversal and image preservation,
setup persistence, master-to-tenant applied-state comparison, hostname ownership,
provisioning locale, accounting guards, manifests/icons, and branded error pages.
Router tests cover exact mapping, missing targets, host normalisation, cache
invalidation and unsafe file permissions. Shell tests cover input guards.

Final verification on 2026-10-01 (Asia/Kolkata):

- 38 Odoo regression tests passed, zero failures/errors, against the deployed
  addons on the disposable QA database. This includes PWA shell regressions.
- Five exact-host router tests and 33 shell guard checks passed.
- Chrome verified creation preview with country/currency and white-label choice;
  saved branding; logo display, accent colour and tenant navigation; company-name
  changes flowing into application branding; readable before/after history;
  saved setup step/notes; master branding editor refresh preserving the customer;
  existing HHH sign-in screen; and HTTPS on the temporary custom hostname.
- The browser extension blocked file selection because file-URL access is off.
  Image validation/persistence was covered by automated tests; the same test
  logo was applied through the platform service and its rendering checked in
  Chrome. The browser file-picker upload itself remains unverified.
- All 365 files in the combined deployed module set matched the workspace
  checksums, including pre-existing theme/sidebar/icon work excluded from these
  commits. Original product images were preserved.
- `carejiox`, `carejiox_template`, and `hhh` upgrades exited zero. Both new modules
  are installed on all three databases; `biz_tenants` remains master-only for
  real customers. Template active scheduled jobs: zero.
- Root domain helpers and server-wide exact-host routing are deployed. A live
  attach/retry/remove test passed. Existing nginx host configuration checksums
  matched before and after. Certbot uses webroot certificate issuance only;
  the helper writes the exact TLS host, avoiding wildcard-host modifications.
- The temporary domain, certificate, mapping, customer/alert records, QA
  database/filestore, test images and credential fixtures were removed. No
  testing screenshots were retained. Production backups remain under
  `/var/backups/cjx-identity-20261001/` on the server.

Implementation commits: `1bf5494a`, `35841023`, `bc927173`, `b66f1a4a`,
`9209ec5f`. The three excluded policy changes remain unchanged.
