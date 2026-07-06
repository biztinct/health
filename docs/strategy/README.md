# health19 Strategy & Design Documents (July 2026)

Product strategy and implementation-ready design for the next generation of the health19 platform.

**Start here:**
- [`DESIGN.md`](DESIGN.md) — master design document: context, stack, hard conventions, build order. An implementing model/engineer starts here.
- [`design-clinical-modules.md`](design-clinical-modules.md) — field-level specs for the six Horizon-1 clinical modules (care plans, vitals, eMAR, forms, incidents, consent).
- [`design-platform-services.md`](design-platform-services.md) — field-level specs for EVV, API gateway, FHIR facade, reminder cascade, H0 automations, PWA additions.
- [`architecture-interop.md`](architecture-interop.md) — FHIR R4 gateway with country adapters, terminology, DICOM stance, platform architecture.
- [`health19-strategy-report.html`](health19-strategy-report.html) — the full interactive strategy report (open in a browser): audit, gap analysis, competitor landscape, 473 scored recommendations, roadmap. Also published at https://claude.ai/code/artifact/6147a22b-fd18-45e1-88b6-022b0a0591db
- [`data/`](data/) — machine-readable sources: `recommendations.json` (473 scored items), `roadmap.json`, `competitors.json`, `review.json`, `modules.json`, `dashboards.json`, `redesigns.json`.

Generated via codebase audit (3 exploration passes over all custom addons), multi-agent competitor/standards research, and scored synthesis. July 2026.
