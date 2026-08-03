# Open platform remediation tickets

Standing defects that pre-date and out-scope the feature phases that keep
rediscovering them. Each is deliberately NOT fixed inside a feature phase —
both touch platform-wide security surfaces and deserve their own tested,
reviewed change. Close a ticket by striking it through with the fixing
commit; a feature-phase report that hits one of these should cite the ticket
instead of re-describing it.

---

## T-001 — inverted group implication: every internal user carries healthcare-base ACLs

**Found:** Phase W2 (2026-07-29). **Ledger:** §5.88.

`health_base/security/health_security.xml:23` declares
`group_healthcare_base → base.group_user`, but the live
`res_groups_implied_rel` on vietuat ALSO holds the reverse edge
(`gid=1 → hid=346`), which no module's XML asks for. Every internal user
therefore inherits the healthcare-base ACL set — including `health.ews.score`
read — and no narrowing of any service group's own implications can undo it.

**Fix shape:** delete the reverse edge in the live table, then re-run the
recursive closure query (§5.88 rules a–c) to prove the closure matches the
XML; check how the edge got there (a historical module or a manual grant)
so an upgrade does not resurrect it. Test: a `base.group_user`-only user
must NOT reach `health.ews.score`.

**Interim mitigations already shipped:** W2.5/W3 tests pre-check the live
closure before asserting denials (`_live_closure`), so the suites fail
loudly rather than vacuously if the edge spreads.

**ASSIGNED 2026-08-03 → phase SH-2**, specified at §5 of
`docs/strategy/handovers/platform-security-hardening.md`. The design
investigation found the fix is **not** a lone row deletion: `access.role`
id 6 "Doctor" grants no healthcare group at all, so ten clinicians reach
clinical data only through this edge and deleting it alone locks out 21
users. The role repair is part of the fix, and §5.5 carries a user decision
that must be answered before the phase runs.

---

## T-002 — core mail reads `base.partner_root` unsudo'd: every chatter throws AccessError for ops personas

**Found:** Phase W2.5 (2026-07-29); reproduced again in W3 — third phase in
a row.

Core Odoo `addons/mail/models/models.py:557`
(`_message_get_suggested_recipients_batch`) builds
`ban_emails = [self.env.ref('base.partner_root').email_normalized]` without
`sudo()`. This database's `res.partner` record rules deny uid 40 (`crm`,
the live ops persona) partner id 1, so every `mail.thread` chatter and the
CMS Contacts list raise an `AccessError` dialog for ops users. Reproduced
live on vietuat (W2.5 review; W3 evidence README "Pre-existing, not ours").

**Fix shape (pick one):**
1. A narrow `res.partner` read rule granting all internal users partner
   id 1 (smallest change, lives in `health_base` security XML — but see
   T-001 before reasoning about who "internal users" are); or
2. a targeted core patch module sudo'ing that one `env.ref` (survives core
   upgrades badly — prefer 1).

Test: drive a chatter render as a real ops persona (§5.4 — uid-1 tests hid
this for months).

**ASSIGNED 2026-08-03 → phase SH-1**, specified at §6 of
`docs/strategy/handovers/platform-security-hardening.md`, which takes fix 1.
Two corrections to this ticket, both verified live: **the partner is id 2**
(`base.partner_root` = "Viet Uc Care"), not id 1 — a fix hard-coding 1 does
nothing; and **the repo's `addons/mail` is a stale Odoo 18 snapshot that
does not contain the offending code and must never be deployed** (the live
server runs mail 1.19; the cited line 557 is correct for the SERVER file
only). There are two unsudo'd reads, `models.py:406` and `:557`. 16 active
internal users are affected. The "CMS Contacts list" half is **unverified**
and is being split into its own ticket.

---

*Registered 2026-07-29 during the W3 review close-out.*
