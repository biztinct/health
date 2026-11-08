# CareJiyo bilingual PDF manuals

Updated 8 November 2026 with a complete active-menu directory and a current Access & delegation walkthrough. The four PDF files retain their original distribution paths.

## Deliverables

| Audience | Language | Pages | Screen guide begins |
| --- | --- | ---: | ---: |
| User | English | 73 | 56 |
| User | Vietnamese | 71 | 56 |
| Administrator | English | 50 | 32 |
| Administrator | Vietnamese | 48 | 32 |

Files are under `output/pdf/CareJiyo_Manuals/Users` and `output/pdf/CareJiyo_Manuals/Administrators`. Distribute administrator editions separately. The current address is carejiox.com; the product name is CareJiyo. Different page counts reflect text flow, not differences in topic coverage.

## Coverage and editable content

- `content.json`: paired English and Vietnamese process chapters and task guidance. The access topic has been rewritten and its unrelated staff-profile illustration replaced.
- `submenu-guide.json`: every one of the 140 active menu entries, including 21 grouping headings and 119 screen/landing entries. Each entry has its path, purpose, main controls, audience and final page in each language. There are 76 entries in the user editions and 64 in the administrator editions.
- `access-walkthrough.json`: four additional paired pages covering Roles/People, Screens, Hand-overs, and history/investigation. Illustrations are embedded in the PDFs; temporary capture files are not retained.
- `validation.json`: final page counts, link counts, SHA-256 checksums and verification results.

Update both languages together. Check the active menu inventory when adding or moving a feature. User-facing material has no development or acceptance-test provenance. Administrator configuration is excluded from the regular-user directory.

The user editions cover Home, CRM, Operations, Finance, Clinical, report consumption and learning. The administrator editions cover Compliance, reporting data, Training admin and Settings. Entries such as Your company, Clinic setup, Activity history, Form Studio, Channel Go-Live and platform-only Customers are explained individually. Restricted platform controls are distinguished from clinic operational work.

The access walkthrough uses the live CareJiyo screen: Roles, People, Screens and Hand-overs. It explains See it as, Who holds what, History, role maintenance, menu gates and temporary/permanent cover. The user confirmed that the separate seven-tab Access Studio screenshot was from another system and should not be used.

## Review method and limits

The active sidebar inventory and actions were read from carejiox.com. All 118 action-based screens/dialogs were opened in Chrome; Home's role-based routing and its destination were also reviewed. Group headings were checked against their children. Window-view definitions and the implemented models/client controls supplied the detailed button and field context. One platform configuration model was restricted to the RPC owner account; its screen was reviewed in the already-authorised administrator browser session instead.

This revision follows repository work through `82fe011e`, including the readable Activity history screen. Concurrent application changes were preserved. No application code, runtime configuration, access permissions, clinical records or financial transactions were changed for the documentation. Forms opened for inspection were closed without confirmation. The review is a documentation/navigation review, not a new end-to-end acceptance test or verification of live external-channel delivery.

The original process chapters were retained, except the administrator access page. Both covers link to the new directory. All 70 added pages, both replaced access pages and all four changed covers were rendered and visually reviewed; unchanged pages had been reviewed for the preceding edition. Checks also covered all 242 pages for text bounds, all 140 menu entries in both languages, Vietnamese glyphs, and all 522 internal links. A mismatched setup capture was replaced during visual review, and final link destinations were verified after PDF assembly.

Only the four PDFs and documentation content are released. No server or database deployment is required for this documentation-only update. Temporary screenshots, browser-state captures, intermediate PDFs and rendered pages from this task were removed after validation. Pre-existing images, recordings and unrelated work were preserved.
