# CareJiyo bilingual PDF manuals

Published 8 November 2026. Documentation baseline: repository commit `05f7a4c7` and read-only inspection of the installed clinic menus and selected screens.

## Deliverables

- `output/pdf/CareJiyo_Manuals/Users/CareJiyo_User_Manual_EN.pdf`: 55 pages, 9 chapters, 42 topics, 23 figures.
- `output/pdf/CareJiyo_Manuals/Users/CareJiyo_User_Manual_VI.pdf`: corresponding Vietnamese edition.
- `output/pdf/CareJiyo_Manuals/Administrators/CareJiyo_Administrator_Manual_EN.pdf`: 31 pages, 7 chapters, 21 topics, 8 figures.
- `output/pdf/CareJiyo_Manuals/Administrators/CareJiyo_Administrator_Manual_VI.pdf`: corresponding Vietnamese edition.

Distribute the Users folder to regular users. Distribute the Administrators folder separately to administrators. The current login URL is carejiox.com; the product name is CareJiyo.

## Content maintenance

`content.json` contains the paired English and Vietnamese chapter titles, topic text, process steps, control tables and illustration identifiers. Update both languages together. User-facing material explains workflows without development or acceptance-test provenance. Administrator setup is excluded from the regular-user editions.

Coverage includes CRM, clients, bookings, operations, mobile visits, clinical records, remote and family services, finance, reporting and learning. Administrator coverage includes access, master data, pricing, form configuration, channels, AI settings, audit, compliance tools and maintenance. Descriptions were checked against the implemented models, view buttons, access scope, menu consolidation and learning catalogue. Conditional integrations are described as conditional; preparation and configuration are distinguished from actual external delivery or submission.

Illustrations combine existing documentation assets, frames from existing learning recordings and newly captured blank or overview screens. Captions are translated; screenshots retain the interface labels visible in the source. Crops are applied to image pixels before embedding, so excluded browser chrome and navigation are not hidden in the PDF image payload.

## Verification

All 172 pages were rendered and visually inspected. Final checks covered page count, text bounds, Vietnamese character rendering, bilingual content presence, contents/bookmarks and internal link destinations. The two user editions each contain 146 links; each administrator edition contains 77. `validation.json` records final checksums and counts.

No application code, runtime configuration or business records were changed. This is a documentation release; no server or database deployment is needed. This work does not represent a new full functional test of the application or live communication channels. Temporary screenshots, video frames and PDF page renders created for this task were removed after verification. Pre-existing images and recordings were preserved.
