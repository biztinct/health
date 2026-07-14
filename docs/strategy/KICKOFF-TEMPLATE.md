# Opus kickoff prompt — canonical template

This is the ONE canonical kickoff prompt for implementation sessions.
Copy it verbatim, replace `<PHASE-DOC>` with the phase's handover
filename, and prepend the one-line kickoff from the handover cycle
("Implement the phase specified in docs/strategy/handovers/<PHASE-DOC>.md.").
If a phase needs an extra guard line, the handover's final report says so —
otherwise do not improvise additions. Keep this file in sync with
HANDOVER-CONVENTIONS.md (it is referenced from §8).

---

Implement the phase specified in docs/strategy/handovers/<PHASE-DOC>.md.

Before writing ANY code, read these two documents fully, in this order:
1. docs/strategy/HANDOVER-CONVENTIONS.md  (ground truth, deploy workflow,
   Odoo 19 gotcha ledger, security/PWA conventions, test fixtures)
2. docs/strategy/handovers/<PHASE-DOC>.md  (the design you are implementing)

Rules:
- Follow the handover design exactly. If something is impossible as
  specified, choose the smallest deviation that preserves the interface
  contracts, and record every deviation with reasoning in your final report.
  Do NOT redesign architecture, rename models/fields, or change interfaces.
- Where the handover doc contains verbatim code blocks marked "kernel —
  use as-is", copy them exactly; do not refactor them.
- Edit ONLY the modules/files the handover explicitly sanctions. For
  shared modules (health_pwa, health_fieldservice, web_timeline,
  health_messaging, …) the handover's sanction list is exhaustive — no
  drive-by edits. The PWA version-bump discipline (conventions §3)
  applies whenever PWA assets change.
- Do not pip install anything on the server.
- Work autonomously; do not stop to ask questions. If genuinely blocked,
  finish everything else and list the blocker in your report.

DEFINITION OF DONE — do not report success until ALL of these are true:
1. Deployed to vietuat per conventions §2 and the server log shows
   "0 failed, 0 error(s)" for your module test tags. Quote the result
   line verbatim in your report. If tests fail, fix and re-run — a
   failing state is not done.
2. After the final restart, curl localhost:8069/web/login returns 200.
3. If anything PWA-facing changed: health_pwa version bumped in ALL 5
   places in pwa_templates.xml + __manifest__.py (conventions §3), the
   co-resident version PIN TESTS updated in the same change, and
   health_pwa included in the upgrade.
4. i18n/vi.po exists and covers user-visible strings.
5. All work committed on branch 19.0 and pushed.
6. Final report includes: file list, deviations + reasons, verbatim test
   results, anything deferred, and any NEW Odoo 19 gotcha you discovered
   (flag it explicitly so it can be added to the conventions ledger).
   WRITE the full report to docs/strategy/reports/<PHASE>-report.md and
   commit it with your change (the reviewer reads it from the repo); also
   paste it in your reply.
