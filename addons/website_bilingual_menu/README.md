# Website Bilingual Menu for Odoo 19 CE

This add-on displays an English menu label in bold above its Māori label for
regular links, desktop dropdown headings, and mobile accordion headings.

## Installation

1. Copy the `website_bilingual_menu` directory into an Odoo add-ons path.
2. Restart Odoo.
3. Enable developer mode and select **Apps > Update Apps List**.
4. Search for **Website Bilingual Menu** and install it.

## Menu setup

Open **Website > Site > Menu Editor** and use a pipe (`|`) between the labels:

```text
About us|Ā mātou tangata
Latest News & Reports|Ngā karere
Surveys|Whānau Voice
Events|Takahanga
Contact us|Whakapā Mai
```

Names without a pipe continue to render as normal single-line menu items.

After changing or upgrading the module, open the website with `?debug=assets`
and hard-refresh once if an older asset bundle remains cached.

## Unified editable page titles

The one-time `scripts/unify_title_design.py` maintenance script copies the
background image, navy filter and compact Odoo padding from the editable About
Us title to all existing content-page titles. It retains each heading, folds a
meaningful legacy eyebrow into a single English / Māori heading where needed,
and removes empty duplicate eyebrow rows. Because it copies Odoo's normal
background attachment metadata and spacing utility classes, editors can still
replace the background, edit the text and resize the section in Website Builder.

## Board editor compatibility

Run `scripts/board_editor_compat.py` after importing or restructuring board
profiles. It removes legacy inline image padding that conflicts with Odoo's
crop tool and applies the green pill only to genuine role labels using Odoo's
editable `lead` paragraph style. Ordinary biography paragraphs stay unstyled
and editable.

Image/text snippets use non-forced default vertical spacing so Odoo's Website
Builder resize pills can add or remove top and bottom padding normally.

All other custom section defaults—including general content sections, the
homepage hero, board profiles and footer—also avoid forced vertical padding.
Saved Odoo `pt*` and `pb*` classes therefore remain the final authority across
the site.

## September 2026 client design

`scripts/build_client_refresh.py` reads `Taupo Website/THHS mockup website Deb
010926.pptx` and the accompanying assets. It generates the reviewed content in
`data/client_refresh_2026.json` and copies only the assets used by the website
into `static/client_2026`. Those PNG files are original client/product assets,
not test screenshots. Do not remove them during screenshot cleanup.

The import supplies 18 pages using editable Website Builder sections. Board,
patron and associate profiles use the native Odoo carousel, with automatic
rotation disabled so visitors have time to read. News items are separate
sections that can be duplicated, reordered or moved to the archive. The
Taupō Health category in Blocks adds lake titles, news, calendar and document
blocks. Text, images, PDF links, colours and section spacing remain editable.
Duplicate an existing client page when adding a page to preserve its design.

The menu retains its existing bilingual layout and dropdown styling, originally
described in the source as Te Tiratū-inspired. Labels and destinations follow
slide 3. The menu font follows the client's Aptos requirement.

The desktop homepage uses the complete supplied image in the panoramic frame
shown on slide 1. On mobile it shows the photograph at its natural proportion
above the text, retaining the complete photo and readable text. Long pages may
scroll instead of reducing body text to unreadable slide-scale sizes.

### Content decisions and missing inputs

- PowerPoint copy takes priority where the companion history Word file differs.
- `Website changes.docx` supplies Laurie Burdett's QSM and the contact-page
  supporting-information placement. The grants Word file supplies the missing
  2018 year for the Bowling Club grant.
- Only eight completed testimonial PDFs are published. The `Testimonials to
  complete` drafts are not presented as completed client stories.
- 2019–2025 annual report icons open the original PDF files. No 2026 report was
  supplied, so its icon has a non-clickable availability note.
- Facebook is sourced from the client's membership form:
  `https://www.facebook.com/TaupoHospitalHealthSociety`.
- The constitution was not supplied. The deck's Givealittle URL is its account
  homepage, not a confirmed Society donation page. A final import requires both
  links. The user has requested a live review deployment with these outstanding;
  `THHS_CLIENT_REVIEW=1` explicitly permits Contact Us as their temporary
  destination and records the pending links in configuration.
- Aptos is specified using local font sources with Calibri/Arial fallbacks.
  This does not guarantee Aptos on devices without it. Supply licensed webfont
  files or agree the fallback before final sign-off. No Office font files are
  copied to the public server. Microsoft distinguishes CSS font stacks from
  redistributing font files: https://learn.microsoft.com/en-us/typography/fonts/font-faq
- PDF links open inline rather than forcing a download. A public browser
  document can still be saved by the visitor; this is not download protection.

### Import and deployment

Scope: SSH `TaupoHealth`, database `thhs`, website ID 1, module at
`/odoo/odoo-server/addons/website_bilingual_menu`. Website 2 and unrelated
healthcare add-ons are outside this change. Publish the latest combined version
of this entire module, preserving other repository changes.

1. Recheck `git status` and the branch head. Run the build and
   `python3 addons/website_bilingual_menu/scripts/validate_client_refresh.py`.
2. Back up the database, filestore and existing module. Backups taken during
   preparation are `/home/ubuntu/thhs_before_client_20260928.dump` and
   `/home/ubuntu/thhs_filestore_before_client_20260928.tar.gz`; take fresh
   timestamped backups if deployment occurs later.
3. Supply `ir.config_parameter` values `thhs.client_2026.constitution` and
   `thhs.client_2026.givealittle` using the approved URLs. An optional
   `thhs.client_2026.facebook` overrides the supplied membership-form address.
4. Stage the complete module. Validate the importer with
   `THHS_CLIENT_APPLY=1 THHS_CLIENT_DRYRUN=1 THHS_CLIENT_MODULE=/path/to/staged/module`
   running its `scripts/apply_client_refresh.py` inside Odoo shell with database
   `thhs` and `--no-http`. This validates snippet registration, pages,
   attachments and menus and rolls the database transaction back. Placeholder
   contact URLs used for missing links exist only in that rolled-back test.
5. Deploy the complete module, upgrade `website_bilingual_menu` with
   `--stop-after-init --no-http`, and restart `odoo-server`.
6. Run `scripts/apply_client_refresh.py` in Odoo shell with
   `THHS_CLIENT_APPLY=1`, without dry-run variables. For the user-authorized live
   review, also set `THHS_CLIENT_REVIEW=1`; otherwise the importer will refuse
   to commit while either required link is missing. It is an explicit content
   replacement, never an automatic module-upgrade hook; do not rerun it after
   client edits without reconciling those edits first.
7. Check every public URL, PDF response headers, fonts, desktop/mobile menus,
   carousel controls, and the native editor's ability to edit/save a section.
   Never save a browser editor tab that still contains the old page content.

Preparation checks passed on 28 September 2026: native server Sass compiler;
local content/XML/checksum validation; local Chrome desktop/mobile previews;
and a full Odoo importer/snippet dry run, rolled back successfully. The live
review deployment uses the local Aptos stack and temporary Contact Us
destinations. Missing final inputs do not block this requested review.
