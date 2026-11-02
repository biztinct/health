# -*- coding: utf-8 -*-
"""The layout of one screen, the generated view that draws it, and its past.

THE WRITER IS DETERMINISTIC AND ANCHORS ONLY ON NAMES. `_render_arch` turns
the JSON description into ONE inherited view. It anchors on `//sheet`,
`//sheet/notebook` and on cards the host declared open by `@name` — never on
a label (`string` is refused as a selector by the view validator anyway),
never on a position number. Every field it places must exist on the model,
or it refuses before touching the view: a view naming a missing field takes
the whole form down for everybody.

A BROKEN LAYOUT SWITCHES ITSELF OFF, NEVER THE SCREEN. `validate_all` re-draws
every layout against today's form; one that no longer fits deactivates its
OWN view and says why. The form underneath keeps working.

TWO KINDS OF SCREEN. A standard form (`kit='vu'`) takes a new section as a
`<group>` above the tabs or at the end of the sheet. A Workspace form
(`kit='ws'`) is a pack of cards: a new section is drawn as one more card at
the END of the pack the host names (`pack_end`), carrying the markup the
pack's own cards carry, plus two attributes the "Not filled yet" tray reads:
`data-fs-fold="1"` (this card may fold) and `data-fs-fields` (the fields that
decide whether it is empty). A field dropped into an open card of a Workspace
form also marks that card with `data-fs-fields`, so the tray never folds a
card while a Studio field in it holds a value.

A LAYOUT ALSO KEEPS A LIST VIEW. When the host names the list its records
appear in (`fs.host.list_view_xmlid` + `list_anchor`), every placed field whose
"show in lists" switch is on becomes a column of that list, right after the
anchor column, in the order the fields sit on the screen. That second view is
written in the same transaction as the form's, kept in the history next to
it, and switched off together with it: one switch, one reason, never half a
layout. With no columns the view stays (empty and inactive), so its id is
stable for the history.
"""
import logging

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

from .fs_common import (ANCHOR_NAME_RE, FS_PREFIX, NO_LIST_TYPES,
                        SECTION_ID_RE)

_logger = logging.getLogger(__name__)

#: Where a section may go, per kind of screen. A Workspace screen has no
#: "above the tabs" or "end of the sheet": its tabs and rail are drawn by the
#: product, so a section is either inside an open card or a card of its own.
ANCHORS = {
    'vu': ('card', 'sheet_end', 'before_notebook'),
    'ws': ('card', 'pack_end'),
}
DEFAULT_ANCHOR = {'vu': 'before_notebook', 'ws': 'pack_end'}

#: The card-title glyph of a Studio card on a Workspace form. It must be one
#: the Workspace's own section-icon set draws (`vu-section__icon[data-icon]`).
WS_CARD_ICON = 'clipboard-list'

#: Types that take the pack's "—" placeholder, like the cards around them.
WS_NO_PLACEHOLDER = ('boolean', 'binary')

#: An empty extension: what a layout's list view holds while it has no column.
EMPTY_ARCH = '<data/>'


class FsLayout(models.Model):
    _name = 'fs.layout'
    _inherit = ['mail.thread']
    _description = 'Form Studio layout'
    _order = 'model, id'

    model = fields.Char(required=True, index=True)
    base_view_id = fields.Many2one(
        'ir.ui.view', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', ondelete='cascade')
    sections = fields.Json(default=list)
    version = fields.Integer(default=0, tracking=True)
    view_id = fields.Many2one('ir.ui.view', ondelete='set null', copy=False)
    list_view_id = fields.Many2one('ir.ui.view', ondelete='set null',
                                   copy=False)
    published_by = fields.Many2one('res.users', ondelete='set null')
    published_at = fields.Datetime()
    state = fields.Selection(
        [('ok', 'Working'), ('broken', 'Switched off')],
        default='ok', required=True, tracking=True)
    broken_reason = fields.Text()

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS fs_layout_screen_uniq ON "
            "fs_layout (model, base_view_id, COALESCE(company_id, 0))")

    def _compute_display_name(self):
        for layout in self:
            layout.display_name = _('Layout of %s', layout.model)

    # ------------------------------------------------------------------
    #  The writer
    # ------------------------------------------------------------------
    @api.model
    def _clean_sections(self, sections, model, host=None):
        """Validate the client's description and return a normalised copy.

        Raises UserError naming the first problem. Empty sections are kept in
        the description (an administrator may be about to fill one) but are
        not drawn. `host` decides which places exist (see ANCHORS); without
        one, the standard form's.
        """
        Model = self.env[model]
        kit = (host.kit if host else None) or 'vu'
        allowed = ANCHORS.get(kit, ANCHORS['vu'])
        if not isinstance(sections, list):
            raise UserError(_("The layout could not be read. Reload Studio."))
        seen_ids, seen_fields, out = set(), set(), []
        for sec in sections:
            if not isinstance(sec, dict):
                raise UserError(_("The layout could not be read. Reload Studio."))
            sid = str(sec.get('id') or '')
            if not SECTION_ID_RE.match(sid) or sid in seen_ids:
                raise UserError(_("The layout could not be read. Reload Studio."))
            # A Studio card is found on the page by its `name`, and the first
            # element carrying that name wins: a field of the same name would
            # be found instead of the card.
            if ('fs_%s' % sid) in Model._fields:
                raise UserError(_(
                    "A section's name is already taken on this screen. "
                    "Reload Studio."))
            seen_ids.add(sid)
            anchor = sec.get('anchor') or {'kind': DEFAULT_ANCHOR[kit]}
            kind = anchor.get('kind')
            if kind not in allowed:
                raise UserError(_("The layout could not be read. Reload Studio."))
            clean_anchor = {'kind': kind}
            if kind == 'card':
                name = str(anchor.get('name') or '')
                if not ANCHOR_NAME_RE.match(name):
                    raise UserError(_("The layout could not be read. Reload Studio."))
                clean_anchor['name'] = name
            names = []
            for fld in sec.get('fields') or []:
                name = fld.get('name') if isinstance(fld, dict) else fld
                if not isinstance(name, str) or not name.startswith(FS_PREFIX):
                    raise UserError(_("Only fields made in Studio can be placed."))
                if name not in Model._fields:
                    raise UserError(_(
                        "The field %s no longer exists. Reload Studio.", name))
                if name in seen_fields:
                    raise UserError(_(
                        "The field \"%s\" is placed twice.",
                        Model._fields[name].string))
                seen_fields.add(name)
                names.append(name)
            title = str(sec.get('title') or '').strip()[:80]
            if kind != 'card' and not title:
                title = 'More details'
            out.append({
                'id': sid,
                'title': title,
                'title_vi': str(sec.get('title_vi') or '').strip()[:80],
                'anchor': clean_anchor,
                'fields': [{'name': n, 'order': i} for i, n in enumerate(names)],
            })
        return out

    @api.model
    def _field_node(self, Model, name, required=False, ws=False):
        field = Model._fields[name]
        node = etree.Element('field', name=name)
        if required:
            node.set('required', '1')
        if field.type == 'binary':
            node.set('widget', 'binary')
        elif field.type == 'many2one':
            node.set('options', "{'no_create': True}")
        if ws and field.type not in WS_NO_PLACEHOLDER:
            # read-first cards show an empty value as a dash, like their
            # neighbours
            node.set('placeholder', '—')
        return node

    @api.model
    def _ws_pack(self, combined, host):
        """(xpath, position) that puts a new card at the end of the host's
        pack, checked against today's form. Raises before anything is
        written when the pack or its tail is gone."""
        pack = "//page[@name='%s']/div[hasclass('ws-pack')]" % host.pack_page
        if len(combined.xpath(pack)) != 1:
            raise UserError(_(
                "The cards of this screen moved, so Studio cannot place new "
                "sections. Open Studio to repair the layout."))
        if host.pack_tail:
            tail = "%s/widget[@name='%s']" % (pack, host.pack_tail)
            if len(combined.xpath(tail)) != 1:
                raise UserError(_(
                    "The cards of this screen moved, so Studio cannot place "
                    "new sections. Open Studio to repair the layout."))
            return tail, 'before'
        return pack, 'inside'

    @api.model
    def _ws_card(self, parent, sec, names, Model, required):
        """One Workspace card, drawn like the pack's own cards."""
        card = etree.SubElement(parent, 'div', {
            'class': 'vu-detail-card ws-card fs-card',
            'name': 'fs_%s' % sec['id'],
            'data-fs-fold': '1',
            'data-fs-fields': ','.join(names),
        })
        head = etree.SubElement(card, 'div', {'class': 'vu-card__title'})
        etree.SubElement(head, 'div', {'class': 'vu-section__icon',
                                       'data-icon': WS_CARD_ICON})
        # The English source; the Vietnamese title is this text node's
        # translation (`_write_title_translations`).
        etree.SubElement(head, 'div').text = sec.get('title') or 'More details'
        group = etree.SubElement(card, 'group')
        for name in names:
            group.append(self._field_node(Model, name, name in required,
                                          ws=True))
        return card

    @api.model
    def _render_arch(self, sections, host, base_view):
        """The inherited view's arch for `sections` on `host`'s form."""
        Model = self.env[host.model]
        ws = host.kit == 'ws'
        combined = etree.fromstring(base_view.get_combined_arch())
        has_sheet = bool(combined.xpath('//sheet'))
        if not has_sheet:
            raise UserError(_("This screen has no place for new sections."))
        has_notebook = bool(combined.xpath('//sheet/notebook'))
        open_cards = {c.get('name') for c in (host.sections or [])
                      if isinstance(c, dict)}
        # "Required" is a rule of the SCREEN (see fs_studio.create_field).
        required = set(self.env['fs.field.meta'].sudo().search(
            [('model', '=', host.model), ('required', '=', True)]).mapped('name'))
        root = etree.Element('data')
        pack_at = None
        card_fields = {}  # open Workspace card -> Studio fields, in order
        for sec in sections:
            names = [f['name'] for f in sorted(
                sec.get('fields') or [], key=lambda f: f.get('order', 0))]
            for name in names:
                if name not in Model._fields:
                    raise UserError(_(
                        "The field %s no longer exists. Reload Studio.", name))
            if not names:
                continue
            anchor = sec.get('anchor') or {
                'kind': DEFAULT_ANCHOR['ws' if ws else 'vu']}
            if anchor['kind'] not in ANCHORS['ws' if ws else 'vu']:
                raise UserError(_("The layout could not be read. Reload Studio."))
            if anchor['kind'] == 'card':
                card = anchor.get('name')
                if card not in open_cards:
                    raise UserError(_(
                        "The card \"%s\" no longer accepts fields.", card))
                if ws:
                    expr = "//div[@name='%s']/group" % card
                    if len(combined.xpath(expr)) != 1:
                        raise UserError(_(
                            "The card \"%s\" cannot take fields: it has no "
                            "field group.", card))
                    card_fields.setdefault(card, []).extend(names)
                else:
                    expr = "//group[@name='%s']" % card
                xp = etree.SubElement(root, 'xpath', expr=expr,
                                      position='inside')
                for name in names:
                    xp.append(self._field_node(Model, name, name in required,
                                               ws=ws))
                continue
            if anchor['kind'] == 'pack_end':
                # One xpath per section, in section order: each lands at the
                # end of the pack (or just before its tail), so the order on
                # the screen is the order in Studio.
                if pack_at is None:
                    pack_at = self._ws_pack(combined, host)
                xp = etree.SubElement(root, 'xpath', expr=pack_at[0],
                                      position=pack_at[1])
                self._ws_card(xp, sec, names, Model, required)
                continue
            if anchor['kind'] == 'before_notebook' and has_notebook:
                xp = etree.SubElement(root, 'xpath', expr='//sheet/notebook',
                                      position='before')
            else:
                xp = etree.SubElement(root, 'xpath', expr='//sheet',
                                      position='inside')
            # The arch is the English source; a section's Vietnamese title is
            # written as the arch's translation (`_write_title_translations`).
            group = etree.SubElement(xp, 'group', {
                'name': 'fs_%s' % sec['id'],
                'string': sec.get('title') or 'More details',
                'class': 'fs-card',
            })
            for name in names:
                group.append(self._field_node(Model, name, name in required))
        # An open Workspace card that received Studio fields says so, so the
        # "Not filled yet" tray counts them when it decides the card is empty.
        for card, names in card_fields.items():
            xp = etree.SubElement(root, 'xpath', expr="//div[@name='%s']" % card,
                                  position='attributes')
            etree.SubElement(xp, 'attribute', name='data-fs-fields').text = \
                ','.join(names)
        return etree.tostring(root, pretty_print=True, encoding='unicode')

    def _write_view(self, arch, host):
        """Create or rewrite this layout's view. `_check_xml` runs on write:
        a layout that does not fit raises here and nothing is saved."""
        self.ensure_one()
        # The arch is a TRANSLATED field: written under a Vietnamese reader's
        # context it would replace the Vietnamese copy and leave the source
        # untouched. The source is always written in English.
        View = self.env['ir.ui.view'].sudo().with_context(lang='en_US')
        company = self.company_id
        vals = {
            'name': 'Form Studio: %s' % self.model,
            'key': 'biz_form_studio.%s.%s' % (
                self.model, company.id if company else 'all'),
            'model': self.model,
            'type': 'form',
            'mode': 'extension',
            'priority': 200,
            'inherit_id': self.base_view_id.id,
            'active': True,
            'arch': arch,
        }
        if self.view_id:
            self.view_id.sudo().with_context(lang='en_US').write(vals)
        else:
            self.sudo().view_id = View.create(vals)
        self._write_title_translations()

    def _write_title_translations(self):
        """Section titles in Vietnamese, as translations of the arch.

        The arch is written in English; a title's Vietnamese wording is stored
        as the view's own translation of that term, so a Vietnamese reader
        sees it on the form with no second view.
        """
        self.ensure_one()
        lang = self.env['res.lang']._lang_get('vi_VN')
        if not lang or not lang.active or not self.view_id:
            return
        terms = {}
        for sec in self.sections or []:
            if sec.get('title') and sec.get('title_vi') and \
                    sec['anchor']['kind'] != 'card':
                terms[sec['title']] = sec['title_vi']
        if terms:
            self.view_id.sudo().update_field_translations(
                'arch_db', {'vi_VN': terms})

    # ------------------------------------------------------------------
    #  The list columns
    # ------------------------------------------------------------------
    @api.model
    def _column_names(self, sections, model):
        """The fields placed in `sections` whose switch makes them a column,
        in the order they sit on the screen (section order, then field
        order). Health information, files and long text never are, whatever
        a stored switch says."""
        placed = []
        for sec in sections or []:
            for f in sorted(sec.get('fields') or [],
                            key=lambda f: f.get('order', 0)):
                if f.get('name') and f['name'] not in placed:
                    placed.append(f['name'])
        if not placed:
            return []
        Model = self.env[model]
        metas = self.env['fs.field.meta'].sudo().search(
            [('model', '=', model), ('name', 'in', placed)])
        ok = {m.name for m in metas if m.list_ok and not m.phi}
        return [n for n in placed if n in ok and n in Model._fields
                and Model._fields[n].type not in NO_LIST_TYPES]

    @api.model
    def _render_list_arch(self, names, host, list_view):
        """The list view's arch: one xpath after the host's anchor column,
        holding one column per name. No names: an empty extension."""
        if not names:
            return EMPTY_ARCH
        Model = self.env[host.model]
        try:
            combined = etree.fromstring(list_view.get_combined_arch())
        except Exception as exc:  # noqa: BLE001 — said in the user's words
            raise UserError(_(
                "The list changed: %s", str(exc) or exc.__class__.__name__)
            ) from exc
        expr = "//field[@name='%s']" % host.list_anchor
        if len(combined.xpath(expr)) != 1:
            raise UserError(_(
                "The list changed: the column \"%s\" that new columns go "
                "after is not there.", host.list_anchor))
        root = etree.Element('data')
        xp = etree.SubElement(root, 'xpath', expr=expr, position='after')
        currency = None
        for name in names:
            if name not in Model._fields:
                raise UserError(_(
                    "The field %s no longer exists. Reload Studio.", name))
            field = Model._fields[name]
            node = etree.SubElement(xp, 'field', name=name, optional='show')
            if field.type == 'selection':
                # like the lists' own status columns
                node.set('widget', 'badge')
            if field.type == 'monetary':
                currency = getattr(field, 'currency_field', None) or 'currency_id'
        # A money column shows its currency only when the list reads the
        # currency field; most lists do not, so it is read, never shown.
        # Always written (a list that already reads it reads it twice, which
        # is harmless): whether "the list" has it cannot be told apart from
        # this layout's own copy in the combined arch, and the arch must not
        # depend on what the previous version wrote.
        if currency and currency in Model._fields:
            etree.SubElement(xp, 'field', name=currency,
                             column_invisible='1')
        return etree.tostring(root, pretty_print=True, encoding='unicode')

    def _write_list_view(self, arch, list_view):
        """Create or rewrite this layout's list view. Active only while it
        holds a column; never deleted while the layout exists."""
        self.ensure_one()
        active = arch != EMPTY_ARCH
        company = self.company_id
        vals = {
            'name': 'Form Studio list: %s' % self.model,
            'key': 'biz_form_studio.list.%s.%s' % (
                self.model, company.id if company else 'all'),
            'model': self.model,
            'type': 'list',
            'mode': 'extension',
            'priority': 200,
            'inherit_id': list_view.id,
            'active': active,
            'arch': arch,
        }
        View = self.env['ir.ui.view'].sudo().with_context(lang='en_US')
        if self.list_view_id:
            self.list_view_id.sudo().with_context(lang='en_US').write(vals)
        else:
            self.sudo().list_view_id = View.create(vals)

    def _empty_list_view(self):
        """The host stopped declaring a list: keep the view, empty and off."""
        self.ensure_one()
        if self.list_view_id:
            self.list_view_id.sudo().with_context(lang='en_US').write(
                {'arch': EMPTY_ARCH, 'active': False})

    def _diff(self, old, new):
        """(+added, -removed, moved) between two descriptions."""
        def where(sections):
            out = {}
            for sec in sections or []:
                for f in sec.get('fields') or []:
                    out[f['name']] = (sec['id'], f.get('order', 0))
            return out
        a, b = where(old), where(new)
        added = [n for n in b if n not in a]
        removed = [n for n in a if n not in b]
        moved = [n for n in b if n in a and a[n] != b[n]]
        return added, removed, moved

    def _publish(self, sections, host, note=None):
        """Draw `sections`, bump the version, keep the history, say so."""
        self.ensure_one()
        base_view = self.base_view_id.sudo()
        clean = self._clean_sections(sections, self.model, host)
        arch = self._render_arch(clean, host, base_view)
        # the list is drawn before anything is written: a list that cannot
        # take the columns refuses the whole publish, never half of it
        list_view = host._list_view()
        list_arch = self._render_list_arch(
            self._column_names(clean, self.model), host, list_view
        ) if list_view else False
        old = self.sections or []
        added, removed, moved = self._diff(old, clean)
        version = self.version + 1
        user = self.env.user
        self.sudo().write({
            'sections': clean,
            'version': version,
            'published_by': user.id,
            'published_at': fields.Datetime.now(),
            'state': 'ok',
            'broken_reason': False,
        })
        self._write_view(arch, host)
        if list_view:
            self._write_list_view(list_arch, list_view)
        else:
            self._empty_list_view()
        self.env['fs.layout.history'].sudo().create({
            'layout_id': self.id,
            'version': version,
            'sections': clean,
            'arch': arch,
            'list_arch': list_arch or False,
            'published_by': user.id,
            'published_at': fields.Datetime.now(),
        })
        Meta = self.env['fs.field.meta'].sudo()
        for name in added:
            meta = Meta.search([('model', '=', self.model), ('name', '=', name)],
                               limit=1)
            if meta and not meta.publish_version:
                meta.publish_version = version
        body = _("Published version %(version)s by %(who)s: +%(added)s fields, "
                 "−%(removed)s fields, %(moved)s moved.",
                 version=version, who=user.name, added=len(added),
                 removed=len(removed), moved=len(moved))
        if note:
            body = '%s %s' % (body, note)
        self.sudo().message_post(body=body, author_id=user.partner_id.id)
        # Every open browser keeps the screen's layout in a cache keyed on
        # the server's registry version. Bumping it makes "everyone sees it on
        # their next page load" true for the people who did not publish.
        self.env.registry.registry_invalidated = True
        _logger.info("Form Studio: uid %s published %s version %s",
                     self.env.uid, self.model, version)
        return {'version': version, 'view_id': self.view_id.id,
                'list_view_id': self.list_view_id.id or False}

    # ------------------------------------------------------------------
    #  The validator
    # ------------------------------------------------------------------
    def _validate_one(self, host):
        """Re-draw against today's form and today's list. Returns None, or
        why it failed (a list failure says so)."""
        self.ensure_one()
        if not self.view_id or not self.sections:
            return None
        stage = 'form'
        try:
            with self.env.cr.savepoint():
                clean = self._clean_sections(self.sections, self.model, host)
                arch = self._render_arch(clean, host, self.base_view_id.sudo())
                self.view_id.sudo().with_context(lang='en_US').write(
                    {'arch': arch, 'active': True})
                self.base_view_id.sudo()._get_combined_arch()
                stage = 'list'
                list_view = host._list_view()
                if list_view:
                    list_arch = self._render_list_arch(
                        self._column_names(clean, self.model), host, list_view)
                    self._write_list_view(list_arch, list_view)
                    if list_arch != EMPTY_ARCH:
                        list_view._get_combined_arch()
                else:
                    self._empty_list_view()
        except Exception as exc:  # noqa: BLE001 — any failure switches it off
            self.env.invalidate_all()
            reason = str(exc) or exc.__class__.__name__
            if stage == 'list' and not reason.startswith(
                    _("The list changed: %s", '')):
                reason = _("The list changed: %s", reason)
            return reason
        return None

    def _switch_off(self, reason):
        self.ensure_one()
        # the form's view and the list's together: never half a layout
        (self.view_id | self.list_view_id).sudo().write({'active': False})
        self.sudo().write({'state': 'broken', 'broken_reason': reason})
        self.sudo().message_post(body=_(
            "This layout is switched off because the screen changed. "
            "Open Studio to repair it."))
        self.env.registry.registry_invalidated = True
        _logger.error("Form Studio: layout %s (%s) switched off: %s",
                      self.id, self.model, reason)


class FsLayoutDraft(models.Model):
    _name = 'fs.layout.draft'
    _description = 'Form Studio draft'

    layout_id = fields.Many2one('fs.layout', required=True,
                                ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                              default=lambda self: self.env.uid)
    sections = fields.Json(default=list)

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS fs_layout_draft_user_uniq ON "
            "fs_layout_draft (layout_id, user_id)")


class FsLayoutHistory(models.Model):
    _name = 'fs.layout.history'
    _description = 'Form Studio published version'
    _order = 'layout_id, version desc'

    layout_id = fields.Many2one('fs.layout', required=True,
                                ondelete='cascade', index=True)
    version = fields.Integer(required=True)
    sections = fields.Json(default=list)
    arch = fields.Text()
    list_arch = fields.Text()
    published_by = fields.Many2one('res.users', ondelete='set null')
    published_at = fields.Datetime()

    def write(self, vals):
        raise UserError(_("A published version cannot be changed."))

    def unlink(self):
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(_("A published version cannot be deleted."))
