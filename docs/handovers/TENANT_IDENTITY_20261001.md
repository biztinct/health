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

Deployment and Chrome verification results are recorded with the implementation
handover after the final run.
