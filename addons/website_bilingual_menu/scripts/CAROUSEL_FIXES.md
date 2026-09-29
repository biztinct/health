# September 2026 carousel follow-up

Successes now uses two native Odoo carousel slides containing the existing
editable grants table/thermometer and cheque presentation. Profile carousels
remain native snippets. No menu or client content is replaced.

Bootstrap ignores arrow clicks while a `.slide` transition is running (600 ms
on this site). Two consecutive clicks in Chrome inside the Odoo website preview
advanced Patrons once. Remove the animation class so native transitions complete
synchronously; retain Bootstrap next/previous, indicators, keyboard and touch
handling. Arrow targets are at least 44 × 44 px with visible focus styling.

Local validation:

```sh
python3 addons/website_bilingual_menu/scripts/validate_client_refresh.py
python3 addons/website_bilingual_menu/scripts/test_carousel_fixes.py
```

Deploy the complete current `website_bilingual_menu` module to TaupoHealth,
after backing up the `thhs` database, filestore, and existing module. Upgrade
the module, then run `scripts/apply_carousel_fixes.py` through Odoo shell.
Default is dry-run; set `THHS_CAROUSEL_APPLY=1` to commit. The script is scoped
to website 1 in `thhs`, preserves current live content, validates its expected
structure and is idempotent. Do **not** run the broad client-content importer.

Chrome acceptance: single next/previous and indicator clicks, consecutive
next clicks, wraparound on Associates and Patrons, two Successes slides, board
regression, mobile, and Odoo editor slide editing/save. No test screenshots
need to be saved to disk.
