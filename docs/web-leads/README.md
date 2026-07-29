# Web Leads — website & digital lead capture

Browser-openable overview of how every enquiry channel (web form, Google, phone, Zalo, Facebook) reaches the CRM, what is live vs dormant vs not started, and the exact build steps for the website developer.

**Open** [`index.html`](index.html) in a browser. It is self-contained — no build step, no external assets.
Also published as a private Artifact: <https://claude.ai/code/artifact/0253b0df-3bfb-427b-9d58-ecb54a44d9ca> (republish from this path to update that link).

Audience: business owner, website developer (Proima), CRM team. Plain language by design — the technical detail lives in the companion documents.

## Companion documents

| Document | What it holds |
|---|---|
| [`../strategy/website-crm-integration.md`](../strategy/website-crm-integration.md) | Full design: architecture decision, data model, API spec, city rules, dedup, security/privacy, phases. §15 carries the 2026-07-29 addendum (productised plugin, two connector modes, Lead Ads phase). |
| [`../strategy/handovers/web-leads-phaseW1.md`](../strategy/handovers/web-leads-phaseW1.md) | W1 build spec handed to the implementer. |
| [`../strategy/reports/web-leads-phaseW1-report.md`](../strategy/reports/web-leads-phaseW1-report.md) | What W1 actually shipped, with evidence. |

## Keeping it honest

Every status pill on the page was verified against the live CRM database and the published website, not assumed. When a phase ships or a channel switches on, update the page and republish it to the same Artifact URL so the shared link never goes stale.
