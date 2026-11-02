# -*- coding: utf-8 -*-
{
    'name': 'Form Studio',
    'summary': 'Let an administrator add fields to a screen and place them, '
               'without a release',
    'description': """
Form Studio, belonging to no particular product.

WHAT IT DOES

  * **Real fields.** A new field is a real column on the record, created as a
    custom field (`x_fs_` + a name made from its label). Its type can never
    change afterwards; a dropdown's options can be added or renamed, never
    removed while records still use them.
  * **One layout per screen, owned by this module.** Where the new fields sit
    is written as ONE inherited view per screen, generated from a small JSON
    description (`fs.layout.sections`). Publishing rewrites that view in one
    transaction, keeps the previous version in a history table, and writes a
    line in the layout's chatter. "Go back to version N" republishes an old
    description.
  * **Who sees a field is enforced by the server.** "Everyone / Staff /
    Admins" becomes the field's `groups`, applied when the registry builds the
    field (`ir.model.fields._instanciate_attrs`), so a person outside the group
    cannot read the value through any door, not just through the form.
  * **A screen opts in.** Nothing works on a screen until a product declares it
    as a host (`fs.host`): its form, the cards a field may be dropped into, the
    fields and areas that are locked and why.
  * **Two kinds of screen.** A standard form takes a new section above its
    tabs or at the end of the sheet. A Workspace form (a pack of cards in one
    tab, `kit='ws'`) takes it as one more card at the end of the pack, drawn
    like the pack's own cards and marked so the "Not filled yet" tray folds it
    while it is empty. A product whose form draws its own top bar calls the
    `biz_form_studio.StudioButton` template from it.

WHAT A PRODUCT SUPPLIES

  * `fs.host` records — the screens that support Studio;
  * `fs.link.target` records — the records a "Link to a record" field may
    point at (none are shipped here);
  * three settings read at call time: `biz_form_studio.gate_group` (who may
    open Studio, default the system administrator), `biz_form_studio.group_staff`
    and `biz_form_studio.group_admin` (the groups behind "Staff" and "Admins").

IT SEEDS NOTHING AND NAMES NOBODY. No host, no target, no menu entry: a
product decides which screens support Studio and where the field library sits
in its own navigation.
""",
    'version': '19.0.1.1.0',
    'category': 'Technical',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': ['base', 'web', 'mail', 'bus', 'biz_kit'],
    'data': [
        'security/fs_security.xml',
        'security/ir.model.access.csv',
        'views/fs_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_form_studio/static/src/scss/studio.scss',
            'biz_form_studio/static/src/js/studio_service.js',
            'biz_form_studio/static/src/js/studio_button.js',
            'biz_form_studio/static/src/xml/studio_button.xml',
            'biz_form_studio/static/src/js/studio/studio_editor.js',
            'biz_form_studio/static/src/xml/studio/studio_editor.xml',
            'biz_form_studio/static/src/js/library.js',
            'biz_form_studio/static/src/xml/library.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
