# Health API Gateway

API keys / OAuth2 client-credentials, versioned `/api/v1` REST surface,
OpenAPI 3.1 (`/api/v1/openapi.json`, human docs at `/api/docs`), transactional
outbox + signed webhooks, and an append-only PHI access audit log.

## Rate limiting stance (spec B.8)

**Primary rate limiting belongs at the edge.** Traefik/Nginx in front of Odoo
owns real rate limiting (per-IP and per-`Authorization`-header buckets). Odoo
Python workers must not be the throttle of record.

The app-level limiter in this module (`gateway.rate.counter`, fixed 1-minute
window, atomic `INSERT ... ON CONFLICT` upsert) is a **correctness fallback
only** — it is not DDoS protection. Limits are configured via
`ir.config_parameter`:

- `gateway.rate_limit_per_min` (default 120)
- `gateway.rate_limit_burst` (default 240)

Over-limit requests receive a `429` envelope with a `Retry-After` header.

## Service users

API keys and OAuth clients authenticate as their owning **service user** —
create one `res.users` per integration so existing record rules (facility /
catchment scoping) apply naturally. Recommended: a facility-limited read-only
service user per external partner.

## Deployment

`pip install authlib pydantic` on the server before upgrade (both are used
opportunistically; the module degrades gracefully without them).
