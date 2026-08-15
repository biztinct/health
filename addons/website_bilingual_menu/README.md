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
