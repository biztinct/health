# SH-1 evidence pack

Conventions §8.5. SH-1 is mostly a backend security change, so the pack is
dominated by **before/after live state** rather than screenshots; the one
user-visible defect (§6, the chatter AccessError) is driven in a real browser
as a real persona below.

## Files

| File | What it is |
|---|---|
| `acl-before.txt` | `ir_model_access` on `health.clinical.note` / `health.fieldservice.order` / `health.appointment`, captured on vietuat BEFORE the deploy |
| `rules-before.txt` | every `ir.rule` on those three models + every `res.partner` rule + row counts + `ir_model_data.noupdate` for the four rows to delete + `res.partner` 1/2 |
| `acl-after.txt` | the same ACL query AFTER, plus A2–A9: the four rows gone, the six remaining non-PHI public/portal rows, the new `ir.rule`, all `res.partner` rules (exactly one global, unchanged), the nine FSO rules, `healthcare_skill_ids` on both `hr.employee` and `hr.employee.public`, unchanged row counts, and zero leftover test fixtures |
| `exploit-probe-before.txt` | **unauthenticated** `POST /mail/data` for a real clinical note and a real FSO — `"hasReadAccess": true` |
| `exploit-probe-after.txt` | the same two probes — `"hasReadAccess": false`; plus the handover's `/mail/thread/data` returning 404 (it exists only in the repo's stale Odoo-18 `addons/mail`) |
| `live-probes-after.txt` | post-fix ORM probes: public user denied on all three models; ops persona reads `base.partner_root` and drives `_message_get_suggested_recipients_batch` without raising; the §3.4 doctor-worklist answer; the new rule's shape |
| `01-ops-persona-logged-in.png` | the ops persona logged in at `care.biztinct.com` (Operations Command Center) |
| `02-ops-contacts-list-no-accesserror.png` | the CMS Contacts list rendering for that persona, no AccessError dialog |
| `03-ops-client-profile-t004-rule618.png` | the T-004 finding: opening a client profile still raises on `allowed_main_contact_ids` via rules 340/618 — **not** the defect SH-1 fixed, and the new rule appears in the "blame" list, which is how you can see it is live and correctly scoped to one record |

## The §6 browser drive — exact click path

Persona: a throwaway user carrying **uid 40 (`crm`)'s exact group set**
(`1, 51, 346, 351, 352, 388, 389` — `base.group_user`,
`sales_team.group_sale_manager`, healthcare base/sales/operations-manager,
CRM User, CRM Manager) and `access.role` 9 "CRM", which is what gives it the
same `/bizapp` sidebar a real CRM user sees. Created and deleted the same
session; deletion verified in a fresh psql cursor (§5.34).

1. `https://care.biztinct.com/web/login` → **Use another user** → user
   `sh1_qa_ops`, password, **Log in**
2. lands on `/bizapp/action-1417` — *Operations Command Center*
   → `01-ops-persona-logged-in.png`
3. sidebar → **Contacts** → `/bizapp/action-1438`, the list renders (1 row)
   with **no AccessError dialog** → `02-ops-contacts-list-no-accesserror.png`
4. sidebar → **Clients** → open the first client → the dialog in
   `03-…png` appears. Read it: it is `allowed_main_contact_ids` on partner
   1272, blamed on *User: Own Partner Record* + *Healthcare CRM Partner* —
   **T-004, not T-002.** The new rule is listed as applicable, which proves
   it is installed and that it deliberately matches only partner 2.
5. From the authenticated page, the two RPCs that ARE the defect:
   - `POST /mail/thread/recipients/get_suggested_recipients`
     (`thread_model='res.partner'`, `thread_id=<own partner>`) →
     `[{"email": false, "name": "SH1 QA Ops (delete me)", "partner_id": 16803}]`
     — **no AccessError.** The identical call raised
     `AccessError: … top-secret records` for this persona shape before the
     fix (see `live-probes-*`).
   - `res.partner.read([2], ['id','name','email'])` →
     `{"id": 2, "name": "Viet Uc Care", "email": "bot@example.com"}` — the
     read core mail performs unsudo'd at `mail/models/models.py:557`.

Console for every screen: **no errors, no warnings.** The only console entry
across the whole drive is one accessibility issue,
`A form field element should have an id or name attribute`, which is
pre-existing and unrelated.

## What this pack does NOT claim

Driving the same endpoint on `crm.lead` 1952 **still raises** — at
`mail/models/models.py:548`, nine lines earlier, where
`_compute_message_partner_ids` needs read on every follower partner and
partner 3 (Mitchell Admin) is denied. That is a **second, independent cause**
of the T-002 symptom that SH-1 did not fix and could not have: it is not a
`base.partner_root` read. See T-002 in `docs/strategy/open-tickets.md`, which
is therefore left OPEN.
