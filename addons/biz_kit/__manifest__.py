# -*- coding: utf-8 -*-
{
    'name': 'UI Kit (shared)',
    'summary': 'Design tokens, screen primitives, one Lucide icon set and the '
               'one door back — shared by every surface built on them',
    'description': """
The shared look, in one place, belonging to no particular product.

WHAT IS IN HERE

  * **Tokens** (`--bzk-*`). One brand colour, a neutral scale, five semantic
    colours and the shape values. Every BRAND colour is emitted as a custom
    property that reads a `--bzk-brand-*` override first, so a product tints
    the whole kit by declaring nine properties in its own theme — no fork of
    this module, no build-order dependency, and no invented hex anywhere.
  * **Primitives** (`.bzk-*`). Page shell, headings, cards and panels, the
    hero, stat tiles, tables, badges, filter chips, the segmented control,
    buttons, notes, empty states, the busy spinner, and the dialog — a scrim,
    a card that scrolls INSIDE itself, and a head and foot rail.
  * **One icon set.** A hundred-odd Lucide glyphs and the `ic(name, size)`
    helper that inlines one as SVG. A glyph a new screen needs is ADDED here;
    the moment two modules keep their own map the same idea gets two pictures.
    No emoji, and no font glyphs.
  * **One door back.** `openHub()` opens a screen with a return door written
    into its context; `hubBack()` reads it; `<HubBackChip/>` draws it and
    navigates itself. There is always a door: the one the caller wrote, else
    the product's registered home, else the browser's own back.
  * **Three soft registries.** A settings-card category, a command-palette
    category, and the product's home. Keys rather than imports, because this
    module is the bottom of the stack and can never import a screen back.

IT SEEDS NOTHING AND NAMES NOBODY. There is no data file, no model and no
menu here. A product supplies its own words, its own palette and its own
home; this module supplies the shape they all take.
""",
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            # tokens FIRST — every file below reads them, and a primitive
            # compiled before its variables exist is a primitive with the
            # default baked in.
            'biz_kit/static/src/scss/kit_tokens.scss',
            'biz_kit/static/src/scss/kit.scss',
            'biz_kit/static/src/scss/kit_modal.scss',
            'biz_kit/static/src/js/kit_icons.js',
            'biz_kit/static/src/js/kit_registries.js',
            'biz_kit/static/src/js/kit_nav.js',
            'biz_kit/static/src/xml/kit_nav.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
