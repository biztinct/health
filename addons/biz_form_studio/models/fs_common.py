# -*- coding: utf-8 -*-
"""Names, settings and the two small pure helpers every Studio file shares.

THE SETTINGS ARE READ WITH PLAIN SQL, ON PURPOSE. `_param_sql` is called from
`ir.model.fields._instanciate_attrs`, which runs while the registry is being
BUILT — the ORM of `ir.config_parameter` may not be usable yet at that moment,
and a crash there skips the field silently ("Failed to load field … skipped").
A one-row SELECT on a core table is safe at any point of the boot.
"""
import re
import unicodedata

# Pure helpers below also serve the schematic reader and the list writer:
# `card_title` and `has_class` take lxml elements and need no environment.

#: Every field this module creates starts with this. Core only demands `x_`;
#: the extra `fs_` is how Studio recognises its own fields and nobody else's.
FS_PREFIX = 'x_fs_'

PARAM_GATE = 'biz_form_studio.gate_group'
PARAM_STAFF = 'biz_form_studio.group_staff'
PARAM_ADMIN = 'biz_form_studio.group_admin'
PARAM_REQUIRED_RULES = 'biz_form_studio.required_rules_action'

DEFAULT_GATE = 'base.group_system'
DEFAULT_STAFF = 'base.group_user'

#: The most restrictive answer, used when a configured group does not exist.
#: A typo in a setting must hide a field from more people, never from fewer.
FALLBACK_GROUP = 'base.group_system'

NAME_RE = re.compile(r'^x_fs_[a-z0-9_]+$')
SECTION_ID_RE = re.compile(r'^[a-z0-9]{1,24}$')
ANCHOR_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,64}$')

#: The types an administrator may pick, in palette order.
TYPES = ('char', 'text', 'integer', 'float', 'monetary', 'boolean', 'date',
         'datetime', 'selection', 'many2one', 'binary')

#: Types whose free text or file is the likeliest place for sensitive
#: information to land unmarked: they get the one-time warning.
PHI_WARN_TYPES = ('text', 'binary')

#: Types that are never a list column: a file has nothing to show in a cell,
#: and long text overflows one.
NO_LIST_TYPES = ('binary', 'text')

#: Health information of these types is STORED ENCRYPTED on a screen whose
#: host allows it (`fs.host.encrypt_ok`): the value is text (a dropdown keeps
#: its option code). Every other type marked health information is hidden
#: only — kept out of lists, exports, reports and the mobile app.
ENC_TYPES = ('char', 'text', 'selection')

#: The column that holds an encrypted field's value is the field's name plus
#: this. The field itself then has no column at all.
ENC_SUFFIX = '_enc'


def has_class(node, cls):
    return cls in (node.get('class') or '').split()


def card_title(card):
    """The title of a Workspace card, whatever tags it is written in.

    A card's title is the text of its `.vu-card__title` child: a `<div>` on
    some screens, `<span>`s on others, sometimes both. The icon inside it
    (`.vu-section__icon`) has no text of its own and is skipped, and so is the
    card's pencil (`.vu-detail-card__edit-trigger`), which sits beside the
    title. Whitespace is collapsed. '' when the card has no title.
    """
    skip = ('vu-section__icon', 'vu-detail-card__edit-trigger')
    for head in card:
        if not isinstance(head.tag, str) or not has_class(head, 'vu-card__title'):
            continue
        parts = [head.text or '']
        for child in head:
            if isinstance(child.tag, str) and not any(
                    has_class(child, cls) for cls in skip):
                parts.append(''.join(child.itertext()))
            parts.append(child.tail or '')
        return ' '.join(''.join(parts).split())
    return ''


def slugify(text, limit=40):
    """ASCII, lowercase, `[a-z0-9_]` only, at most `limit` characters.

    Vietnamese needs one rule NFKD does not cover: `đ` is its own letter, not
    `d` plus a mark, so it is mapped by hand before the decomposition.
    """
    text = (text or '').replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
    return text[:limit].strip('_')


def param_sql(cr, key, default=None):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", [key])
    row = cr.fetchone()
    return (row and row[0]) or default


def group_exists_sql(cr, xmlid):
    if not xmlid or '.' not in xmlid:
        return False
    module, name = xmlid.split('.', 1)
    cr.execute("SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s "
               "AND model = 'res.groups'", [module, name])
    return bool(cr.fetchone())


def vis_group_xmlid(cr, vis):
    """The group behind "Staff" or "Admins"; None for "Everyone"."""
    if vis == 'staff':
        xmlid = param_sql(cr, PARAM_STAFF, DEFAULT_STAFF)
    elif vis == 'admin':
        xmlid = param_sql(cr, PARAM_ADMIN) or param_sql(cr, PARAM_GATE,
                                                         DEFAULT_GATE)
    else:
        return None
    return xmlid if group_exists_sql(cr, xmlid) else FALLBACK_GROUP
