# -*- coding: utf-8 -*-
"""The one door into Form Studio.

EVERY PUBLIC METHOD STARTS WITH THE GATE. `_check_gate(model)` asks two
things: does this person hold the group the product named as Studio's gate
(`biz_form_studio.gate_group`), and may they write records of this screen at
all. Only then does anything run `sudo()` — and `sudo()` keeps `env.uid`, so
every chatter line and audit row still names the human.

`probe` is the only method that never raises. It is a capability question
("may I show the Studio button here?"), it has an honest answer for everybody,
and for somebody who may not use Studio that answer is "no" — not an error
dialog on a screen that otherwise works.
"""
import logging

from lxml import etree

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .fs_common import (DEFAULT_GATE, FS_PREFIX, NAME_RE, PARAM_GATE,
                        PARAM_REQUIRED_RULES, PHI_WARN_TYPES, TYPES, slugify,
                        vis_group_xmlid)

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

#: type -> (name, hint, icon). The icon names are keys of the shared `ic()`
#: registry (`biz_kit/static/src/js/kit_icons.js`); the source gate checks it.
TYPE_INFO = {
    'char': (_lt('Text'), _lt('short, one line'), 'type'),
    'text': (_lt('Long text'), _lt('notes'), 'alignLeft'),
    'integer': (_lt('Whole number'), _lt('0, 1, 2…'), 'hash'),
    'float': (_lt('Decimal'), _lt('12.5'), 'sigma'),
    'monetary': (_lt('Money'), _lt('an amount'), 'banknote'),
    'boolean': (_lt('Yes / No'), _lt('a tick box'), 'toggleLeft'),
    'date': (_lt('Date'), _lt('a day'), 'calendar'),
    'datetime': (_lt('Date and time'), _lt('a day and an hour'), 'calendarClock'),
    'selection': (_lt('Dropdown'), _lt('pick one'), 'list'),
    'many2one': (_lt('Link to a record'), _lt('another record'), 'link'),
    'binary': (_lt('File'), _lt('a document or photo'), 'paperclip'),
}

#: Types Studio does not make but a standard screen shows: a name and a
#: picture for the schematic, nothing more.
OTHER_TYPE_INFO = {
    'html': (_lt('Formatted text'), 'fileText'),
    'one2many': (_lt('List of records'), 'table'),
    'many2many': (_lt('Several records'), 'layers'),
    'reference': (_lt('Link to a record'), 'link'),
    'json': (_lt('Structured data'), 'fileText'),
    'properties': (_lt('Structured data'), 'fileText'),
}

VIS = ('all', 'staff', 'admin')


class FsStudio(models.AbstractModel):
    _name = 'fs.studio'
    _description = 'Form Studio'

    # ==================================================================
    #  The gate
    # ==================================================================
    @api.model
    def _gate_group(self):
        return (self.env['ir.config_parameter'].sudo().get_param(PARAM_GATE)
                or DEFAULT_GATE)

    @api.model
    def _is_gate_user(self):
        """The ACTOR is `env.uid`, never `env.su` (ledger §5.210)."""
        if self.env.uid == SUPERUSER_ID:
            return True
        try:
            return self.env.user.has_group(self._gate_group())
        except ValueError:
            return False

    @api.model
    def _deny(self):
        return AccessError(_(
            "You do not have access to Form Studio for this screen."))

    @api.model
    def _check_gate(self, model):
        if not self._is_gate_user():
            raise self._deny()
        if not model or model not in self.env:
            raise self._deny()
        try:
            self.env[model].check_access('write')
        except AccessError:
            raise self._deny() from None

    @api.model
    def _vis_group_xmlid(self, vis):
        return vis_group_xmlid(self.env.cr, vis)

    # ==================================================================
    #  Helpers
    # ==================================================================
    @api.model
    def _host(self, model, view_id=None):
        Host = self.env['fs.host'].sudo()
        if view_id:
            host = Host._for(model, view_id)
        else:
            host = Host.search([('model', '=', model)], limit=1)
        if not host or not host._base_view():
            raise UserError(_("This screen does not support Studio."))
        return host

    @api.model
    def _host_of_layout(self, layout):
        for host in self.env['fs.host'].sudo().search(
                [('model', '=', layout.model)]):
            if host._base_view() == layout.base_view_id:
                return host
        return self.env['fs.host']

    @api.model
    def _layout(self, host, create=True):
        base = host._base_view()
        Layout = self.env['fs.layout'].sudo()
        layout = Layout.search([('model', '=', host.model),
                                ('base_view_id', '=', base.id),
                                ('company_id', '=', False)], limit=1)
        if not layout and create:
            layout = Layout.create({'model': host.model,
                                    'base_view_id': base.id})
        return layout

    @api.model
    def _audit(self, host, body):
        """Field events are written on the screen's layout (created lazily),
        naming the person — `env.user` survives the `sudo()`."""
        layout = self._layout(host)
        layout.message_post(body=body, author_id=self.env.user.partner_id.id)

    @api.model
    def _custom_field(self, model, name):
        field = self.env['ir.model.fields'].sudo().search(
            [('model', '=', model), ('name', '=', name),
             ('state', '=', 'manual')], limit=1)
        if not field or not (name or '').startswith(FS_PREFIX):
            raise UserError(_("This field was not made in Studio."))
        Meta = self.env['fs.field.meta'].sudo()
        meta = Meta.search([('field_id', '=', field.id)], limit=1)
        if not meta:
            meta = Meta.create({'field_id': field.id,
                                'vis': field.fs_vis or 'all'})
        return field, meta

    @api.model
    def _vi_active(self):
        lang = self.env['res.lang']._lang_get('vi_VN')
        return bool(lang and lang.active)

    @api.model
    def _write_vi(self, field, label_vi=None, help_vi=None):
        """The Vietnamese label and help as the field's own translations.

        Written as translations rather than through `write`, so the English
        source is never replaced by a Vietnamese administrator's context;
        the label caches are cleared so the next request reads them."""
        if not self._vi_active():
            return
        changed = False
        if label_vi is not None and label_vi.strip():
            field.sudo().update_field_translations(
                'field_description', {'vi_VN': label_vi.strip()})
            changed = True
        if help_vi is not None and help_vi.strip():
            field.sudo().update_field_translations(
                'help', {'vi_VN': help_vi.strip()})
            changed = True
        if changed:
            # The translated labels and options are cached per language in the
            # 'stable' cache (`ir.model.fields._get_fields_cached`), which a
            # translation alone does not clear.
            self.env.registry.clear_cache('stable')
            self.env.registry.clear_cache()

    @api.model
    def _new_name(self, model, label):
        base = slugify(label) or 'field'
        taken = set(self.env[model]._fields)
        taken |= set(self.env['ir.model.fields'].sudo().search(
            [('model', '=', model)]).mapped('name'))
        name, i = FS_PREFIX + base, 2
        while name in taken:
            name = '%s%s_%s' % (FS_PREFIX, base, i)
            i += 1
        if not NAME_RE.match(name) or len(name) > 63:
            raise UserError(_("Choose a different label for this field."))
        return name

    @staticmethod
    def _option_values(labels, taken=()):
        values, used = [], set(taken)
        for label in labels:
            base = slugify(label, 30) or 'option'
            value, i = base, 2
            while value in used:
                value = '%s_%s' % (base, i)
                i += 1
            used.add(value)
            values.append(value)
        return values

    @api.model
    def _type_list(self, host):
        out = []
        for key in TYPES:
            label, hint, icon = TYPE_INFO[key]
            item = {'key': key, 'label': self.env._(label),
                    'hint': self.env._(hint), 'icon': icon,
                    'disabled': False, 'reason': ''}
            if key == 'monetary' and not host.money_ok:
                item['disabled'] = True
                item['hint'] = _("not on this screen")
                item['reason'] = _("This screen has no currency, so it cannot "
                                   "hold an amount of money.")
            out.append(item)
        return out

    @api.model
    def _type_label(self, ttype):
        info = TYPE_INFO.get(ttype) or OTHER_TYPE_INFO.get(ttype)
        return self.env._(info[0]) if info else ttype

    @staticmethod
    def _type_icon(ttype):
        if ttype in TYPE_INFO:
            return TYPE_INFO[ttype][2]
        if ttype in OTHER_TYPE_INFO:
            return OTHER_TYPE_INFO[ttype][1]
        return 'circle'

    # ==================================================================
    #  The probe — never raises
    # ==================================================================
    @api.model
    def probe(self, model, view_id):
        no = {'host': False, 'can_edit': False}
        try:
            if not self._is_gate_user():
                return no
            host = self.env['fs.host'].sudo()._for(model, view_id)
            if not host:
                return no
            self._check_gate(model)
            return {'host': True, 'can_edit': True}
        except Exception:  # noqa: BLE001 — a capability probe has no error path
            _logger.debug("Form Studio probe said no", exc_info=True)
            return no

    @api.model
    def can_use(self):
        """May this person open Studio at all (the field library, a Settings
        tile)? A capability question like `probe`: it never raises."""
        try:
            return bool(self._is_gate_user())
        except Exception:  # noqa: BLE001 — a capability probe has no error path
            return False

    # ==================================================================
    #  Reading a screen
    # ==================================================================
    @api.model
    def _base_cards(self, arch, host, fg):
        """The screen as cards: what the schematic draws around Studio's own
        sections. Standard fields are listed so an administrator sees where
        the new ones will sit; they are not movable in this release."""
        # Translated once, here: `_()` finds the reader's language from the
        # calling frame, and the nested helpers below have no `self` in it.
        t_details, t_tab = _('Details'), _('Tab')
        t_title, t_status = _('Title'), _('Status bar')
        t_header = _('Header')
        ws = host.kit == 'ws'
        zones = {z.get('name'): z for z in (host.locked_zones or [])
                 if isinstance(z, dict)}
        open_cards = {c.get('name'): c for c in (host.sections or [])
                      if isinstance(c, dict)}
        cards, seen_zones, counter = [], set(), [0]

        def has_class(node, cls):
            return cls in (node.get('class') or '').split()

        def ws_title(card):
            """A Workspace card's title is the text of the LAST `div` of its
            `.vu-card__title` (the first one is the icon)."""
            for head in card:
                if head.tag == 'div' and has_class(head, 'vu-card__title'):
                    divs = [d for d in head if d.tag == 'div']
                    if divs:
                        return ''.join(divs[-1].itertext()).strip()
            return ''

        def ws_pack(page):
            for child in page:
                if child.tag == 'div' and has_class(child, 'ws-pack'):
                    return child
            return None

        def collect(node, out):
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                if child.tag == 'field':
                    name = child.get('name')
                    if (name and name in fg and not name.startswith(FS_PREFIX)
                            and child.get('invisible') not in ('1', 'True')
                            and name not in out):
                        out.append(name)
                    continue
                collect(child, out)
            return out

        def key():
            counter[0] += 1
            return 'c%s' % counter[0]

        def zone_card(name):
            zone = zones[name]
            seen_zones.add(name)
            return {'kind': 'zone', 'key': key(), 'name': name,
                    'title': host._fs_text(zone.get('title') or name),
                    'reason': host._fs_text(zone.get('reason') or ''),
                    'fields': []}

        def walk(node):
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                name = child.get('name')
                if name in zones:
                    cards.append(zone_card(name))
                    continue
                if child.tag == 'group':
                    sub = [c for c in child if c.tag == 'group']
                    direct = [c for c in child if c.tag == 'field']
                    if sub and not direct:
                        walk(child)
                        continue
                    fields_ = collect(child, [])
                    if not fields_ and name not in open_cards:
                        continue
                    cards.append({
                        'kind': 'std', 'key': key(), 'name': name or '',
                        'title': child.get('string') or (
                            open_cards.get(name, {}).get('title') or
                            t_details),
                        'open': name in open_cards,
                        'tab': False, 'fields': fields_})
                elif child.tag == 'notebook':
                    cards.append({'kind': 'notebook', 'key': key()})
                    for page in child:
                        if not isinstance(page.tag, str) or page.tag != 'page':
                            continue
                        pack = None
                        if ws and page.get('name') == host.pack_page:
                            pack = ws_pack(page)
                        if pack is not None:
                            # The pack: a marker, one card per named card of
                            # the pack (Studio's own `fs_` cards are drawn from
                            # the layout, not from here), and an end marker.
                            cards.append({'kind': 'pack', 'key': key(),
                                          'name': page.get('name'),
                                          'title': page.get('string') or t_tab})
                            for card in pack:
                                cname = card.get('name') if isinstance(
                                    card.tag, str) else None
                                if (card.tag != 'div' or not cname
                                        or not has_class(card, 'vu-detail-card')
                                        or cname.startswith('fs_')):
                                    continue
                                cards.append({
                                    'kind': 'std', 'key': key(), 'name': cname,
                                    'title': ws_title(card) or open_cards.get(
                                        cname, {}).get('title') or t_details,
                                    'open': cname in open_cards,
                                    'tab': False, 'pack': True,
                                    'fields': collect(card, [])})
                            cards.append({'kind': 'pack_end', 'key': key()})
                            continue
                        fields_ = collect(page, [])
                        cards.append({
                            'kind': 'std', 'key': key(),
                            'name': page.get('name') or '',
                            'title': page.get('string') or t_tab,
                            'open': False, 'tab': True, 'fields': fields_})
                elif ws and child.tag == 'div' and has_class(child, 'ws-hero'):
                    # the Workspace header: who the record is, read-only here
                    # (its picture is not a field anybody reads as text)
                    fields_ = [n for n in collect(child, [])
                               if fg[n].get('type') != 'binary']
                    if fields_:
                        cards.append({'kind': 'std', 'key': key(), 'name': '',
                                      'title': t_header, 'open': False,
                                      'tab': False, 'fields': fields_})
                elif child.tag == 'div' and 'oe_title' in (
                        child.get('class') or ''):
                    fields_ = collect(child, [])
                    if fields_:
                        cards.append({'kind': 'std', 'key': key(), 'name': '',
                                      'title': t_title, 'open': False,
                                      'tab': False, 'fields': fields_})
                elif child.tag in ('div', 'span'):
                    walk(child)

        header = arch.find('header')
        if header is not None:
            fields_ = collect(header, [])
            if fields_:
                cards.append({'kind': 'std', 'key': key(), 'name': '',
                              'title': t_status, 'open': False,
                              'tab': False, 'fields': fields_})
        sheet = arch.find('.//sheet')
        walk(sheet if sheet is not None else arch)
        missing = [zone_card(n) for n in zones if n not in seen_zones]
        return missing + cards

    @api.model
    def _field_info(self, model, fg, fg_en, host, shown=None):
        """Every field the schematic may show, keyed by name: the standard
        fields its cards list (`shown`; None = all of them), and every field
        made in Studio. A large record type has hundreds of standard fields
        the schematic never draws; they are not sent."""
        locked = host.locked_fields or {}
        vi_on = self._vi_active()
        out = {}
        for name, desc in fg.items():
            if name.startswith(FS_PREFIX):
                continue
            if shown is not None and name not in shown:
                continue
            out[name] = {
                'label': desc.get('string') or name,
                'display': desc.get('string') or name,
                'type': desc.get('type'),
                'type_label': self._type_label(desc.get('type')),
                'icon': self._type_icon(desc.get('type')),
                'std': True,
                'locked': name in locked,
                'reason': host._fs_text(locked[name]) if name in locked
                else _("Part of the standard screen. It cannot be moved "
                       "or hidden in this release."),
                'required': bool(desc.get('required')),
            }
        targets = {t.model: t.label for t in
                   self.env['fs.link.target'].sudo().search([])}
        fields_ = self.env['ir.model.fields'].sudo().search(
            [('model', '=', model), ('state', '=', 'manual'),
             ('name', '=like', FS_PREFIX + '%')])
        metas = {m.field_id.id: m for m in self.env['fs.field.meta'].sudo()
                 .search([('field_id', 'in', fields_.ids)])}
        for field in fields_:
            if not field.name.startswith(FS_PREFIX):
                continue
            meta = metas.get(field.id)
            en = fg_en.get(field.name, {})
            info = {
                'label': en.get('string') or field.name,
                'display': fg.get(field.name, {}).get('string') or
                en.get('string') or field.name,
                'help': en.get('help') or '',
                'type': field.ttype,
                'type_label': self._type_label(field.ttype),
                'icon': self._type_icon(field.ttype),
                'std': False,
                'locked': False,
                'reason': '',
                'required': bool(meta and meta.required),
                'vis': (meta and meta.vis) or field.fs_vis or 'all',
                'phi': bool(meta and meta.phi),
                'pwa': bool(meta and meta.pwa),
                'list_ok': bool(meta.list_ok) if meta else True,
                'label_vi': (meta and meta.label_vi) or '',
                'help_vi': (meta and meta.help_vi) or '',
                'warned_phi': bool(meta and meta.warned_phi),
                'created_by': (meta and meta.created_by.name) or '',
            }
            if field.ttype == 'selection':
                retired = set((meta and meta.retired_values) or [])
                info['options'] = []
                for sel in field.selection_ids.sorted('sequence'):
                    en_label = sel.with_context(lang='en_US').name
                    vi_label = sel.with_context(lang='vi_VN').name \
                        if vi_on else en_label
                    info['options'].append({
                        'value': sel.value,
                        'label': en_label,
                        'label_vi': vi_label if vi_label != en_label else '',
                        'retired': sel.value in retired})
            if field.ttype == 'many2one':
                info['comodel'] = field.relation
                info['comodel_label'] = targets.get(field.relation) or \
                    self.env['ir.model']._get(field.relation).name
            out[field.name] = info
        return out

    @api.model
    def get_studio(self, model, view_id):
        self._check_gate(model)
        host = self._host(model, view_id)
        base = host._base_view()
        layout = self._layout(host, create=False)
        Model = self.env[model].sudo()
        attrs = ['string', 'help', 'type', 'required', 'relation']
        fg = Model.fields_get(attributes=attrs)
        fg_en = Model.with_context(lang='en_US').fields_get(
            attributes=['string', 'help'])
        arch = etree.fromstring(base.get_combined_arch())
        cards = self._base_cards(arch, host, fg)
        shown = {name for card in cards for name in card.get('fields') or []}
        draft = None
        history = []
        if layout:
            rec = self.env['fs.layout.draft'].sudo().search(
                [('layout_id', '=', layout.id),
                 ('user_id', '=', self.env.uid)], limit=1)
            if rec:
                draft = rec.sections or []
            for hist in self.env['fs.layout.history'].sudo().search(
                    [('layout_id', '=', layout.id)], order='version desc',
                    limit=30):
                history.append({
                    'version': hist.version,
                    'published_at': fields.Datetime.to_string(
                        hist.published_at) if hist.published_at else '',
                    'published_by': hist.published_by.name or '',
                })
        rules_action = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_REQUIRED_RULES)
        if rules_action and not self.env.ref(rules_action,
                                             raise_if_not_found=False):
            rules_action = False
        targets = [{'model': t.model, 'label': t.label} for t in
                   self.env['fs.link.target'].sudo().search([])
                   if t.model in self.env]
        return {
            'host': {
                'id': host.id,
                'title': host._title(),
                'kit': host.kit,
                'sections': host.sections or [],
                'money_ok': host.money_ok,
                'has_notebook': bool(arch.xpath('//sheet/notebook')),
                'pwa_label': host.pwa_label or _('Mobile app'),
                'base_view_id': base.id,
                'pack_page': host.pack_page or False,
                'pack_tail': host.pack_tail or False,
            },
            'layout': {
                'id': layout.id or False,
                'version': layout.version if layout else 0,
                'sections': (layout.sections or []) if layout else [],
                'state': layout.state if layout else 'ok',
                'broken_reason': (layout.broken_reason or '') if layout else '',
            },
            'draft': draft,
            'cards': cards,
            'fields': self._field_info(model, fg, fg_en, host, shown),
            'link_targets': targets,
            'types': self._type_list(host),
            'can_publish': True,
            'history': history,
            'required_rules_action': rules_action or False,
            'lang': self.env.lang or 'en_US',
        }

    # ==================================================================
    #  Drafts
    # ==================================================================
    @api.model
    def save_draft(self, model, view_id, sections):
        self._check_gate(model)
        host = self._host(model, view_id)
        layout = self._layout(host)
        clean = layout._clean_sections(sections, model, host)
        Draft = self.env['fs.layout.draft'].sudo()
        draft = Draft.search([('layout_id', '=', layout.id),
                              ('user_id', '=', self.env.uid)], limit=1)
        if draft:
            draft.sections = clean
        else:
            Draft.create({'layout_id': layout.id, 'user_id': self.env.uid,
                          'sections': clean})
        return True

    @api.model
    def discard_draft(self, model, view_id):
        self._check_gate(model)
        host = self._host(model, view_id)
        layout = self._layout(host, create=False)
        if layout:
            self.env['fs.layout.draft'].sudo().search(
                [('layout_id', '=', layout.id),
                 ('user_id', '=', self.env.uid)]).unlink()
        return True

    # ==================================================================
    #  Fields
    # ==================================================================
    @api.model
    def create_field(self, model, spec, view_id=None):
        self._check_gate(model)
        host = self._host(model, view_id)
        spec = spec or {}
        ftype = spec.get('type')
        if ftype not in TYPES:
            raise UserError(_("Pick a type for the new field."))
        label = (spec.get('label') or '').strip()
        if not label:
            raise UserError(_("Give the field a label."))
        if ftype == 'monetary' and not host.money_ok:
            raise UserError(_("This screen has no currency, so it cannot "
                              "hold an amount of money."))
        vis = spec.get('vis') or 'all'
        if vis not in VIS:
            raise UserError(_("Choose who sees this field."))
        # "Required" is a rule of the SCREEN: the form refuses to save without
        # a value. It is deliberately NOT the field's database rule — a new
        # column on a table that already has records can never be made NOT
        # NULL (the framework logs an error on every restart trying), and it
        # would refuse records the mobile app and integrations create, which
        # would change the host's business logic.
        required = bool(spec.get('required'))
        name = self._new_name(model, label)
        vals = {
            'name': name,
            'model_id': self.env['ir.model']._get_id(model),
            'ttype': ftype,
            'field_description': label,
            'help': (spec.get('help') or '').strip() or False,
            'state': 'manual',
            'store': True,
            'copied': False,
            'tracking': 0,
            'required': False,
            'fs_vis': vis,
        }
        if ftype == 'selection':
            labels, labels_vi = [], {}
            for opt in spec.get('options') or []:
                text = opt.get('label') if isinstance(opt, dict) else opt
                text = (text or '').strip()
                if text and text not in labels:
                    labels.append(text)
                    if isinstance(opt, dict):
                        labels_vi[text] = (opt.get('label_vi') or '').strip()
            if not labels:
                raise UserError(_("A dropdown needs at least one option."))
        if ftype == 'many2one':
            comodel = spec.get('comodel')
            target = self.env['fs.link.target'].sudo().search(
                [('model', '=', comodel)], limit=1)
            if not comodel or not target or comodel not in self.env:
                raise UserError(_("Pick what this field links to from the "
                                  "list."))
            vals['relation'] = comodel
            vals['on_delete'] = 'restrict' if required else 'set null'
        if ftype == 'monetary':
            vals['currency_field'] = 'currency_id'
        with self.env.cr.savepoint():
            field = self.env['ir.model.fields'].sudo().with_context(
                lang='en_US').create(vals)
            if ftype == 'selection':
                # Created DIRECTLY, never as `selection_ids` commands on the
                # field: `ir.model.fields.selection` refuses sudo commands
                # (`_allow_sudo_commands = False`), so a command list is
                # re-run as the person who made the request — who is not a
                # system administrator — and refused.
                options = self.env['ir.model.fields.selection'].sudo(
                ).with_context(lang='en_US').create([
                    {'field_id': field.id, 'value': value, 'name': text,
                     'sequence': i}
                    for i, (value, text) in enumerate(
                        zip(self._option_values(labels), labels))])
                self._write_options_vi(
                    {opt: labels_vi.get(opt.name) for opt in options})
        phi = bool(spec.get('phi'))
        meta = self.env['fs.field.meta'].sudo().create({
            'field_id': field.id,
            'vis': vis,
            'phi': phi,
            'pwa': bool(spec.get('pwa')),
            'required': required,
            'list_ok': False if phi else spec.get('list_ok', True) is not False,
            'label_vi': (spec.get('label_vi') or '').strip() or False,
            'help_vi': (spec.get('help_vi') or '').strip() or False,
            'created_by': self.env.uid,
        })
        self._write_vi(field, spec.get('label_vi'), spec.get('help_vi'))
        self._audit(host, _("Field \"%(label)s\" added by %(who)s.",
                            label=label, who=self.env.user.name))
        _logger.info("Form Studio: uid %s created %s.%s (%s)",
                     self.env.uid, model, name, ftype)
        return {'name': name, 'label': label,
                'phi_warning': ftype in PHI_WARN_TYPES and not meta.warned_phi}

    @api.model
    def ack_phi_warning(self, model, name):
        self._check_gate(model)
        _field, meta = self._custom_field(model, name)
        meta.warned_phi = True
        return True

    @api.model
    def _write_options_vi(self, wanted):
        """`{option row: Vietnamese name | '' | None}` as the rows' own
        translations. '' removes a Vietnamese name (the English shows again);
        None leaves the row as it is. Written as translations, never with a
        Vietnamese context: that would replace the English (ledger §5.270)."""
        if not self._vi_active():
            return
        changed = False
        for row, label_vi in wanted.items():
            if label_vi is None:
                continue
            en = row.with_context(lang='en_US').name
            now = row.with_context(lang='vi_VN').name
            target = label_vi or en
            if target == now:
                continue
            row.sudo().update_field_translations(
                'name', {'vi_VN': label_vi if label_vi and label_vi != en
                         else False})
            changed = True
        if changed:
            # option labels are read per language from the 'stable' cache
            self.env.registry.clear_cache('stable')
            self.env.registry.clear_cache()

    @api.model
    def _apply_options(self, field, options, meta):
        """Add and rename only. Removing an option still in use is refused
        with the number of records that use it; "retire" is offered instead."""
        Selection = self.env['ir.model.fields.selection'].sudo().with_context(
            lang='en_US')
        existing = {s.value: s for s in field.selection_ids}
        keep, new_labels, retired = [], [], []
        renames, removals = [], []
        vi_wanted, new_vi = {}, {}
        for opt in options or []:
            if not isinstance(opt, dict):
                opt = {'label': opt}
            label = (opt.get('label') or '').strip()
            value = opt.get('value')
            label_vi = (opt.get('label_vi') or '').strip() \
                if 'label_vi' in opt else None
            if value and value in existing:
                keep.append(value)
                old = existing[value].with_context(lang='en_US').name
                if label and label != old:
                    renames.append((existing[value], label))
                if opt.get('retired'):
                    retired.append(value)
                vi_wanted[existing[value]] = label_vi
            elif label and label not in new_labels:
                new_labels.append(label)
                new_vi[label] = label_vi
        Model = self.env[field.model].sudo().with_context(active_test=False)
        for value, sel in existing.items():
            if value in keep:
                continue
            count = Model.search_count([(field.name, '=', value)])
            if count:
                raise UserError(_(
                    "The option \"%(option)s\" is used on %(count)s records, so "
                    "it cannot be removed. Retire it instead: it is then hidden "
                    "from new picks after the next release.",
                    option=sel.with_context(lang='en_US').name, count=count))
            removals.append(sel)
        if not keep and not new_labels:
            raise UserError(_("A dropdown needs at least one option."))
        # Direct writes on the option rows, never commands on the field (see
        # create_field: the option model refuses sudo commands).
        for sel, label in renames:
            sel.sudo().with_context(lang='en_US').write({'name': label})
        if removals:
            Selection.browse([r.id for r in removals]).unlink()
        start = max([s.sequence for s in existing.values()] or [0]) + 1
        if new_labels:
            created = Selection.create([
                {'field_id': field.id, 'value': value, 'name': label,
                 'sequence': start + i}
                for i, (value, label) in enumerate(zip(
                    self._option_values(new_labels, existing), new_labels))])
            for row in created:
                vi_wanted[row] = new_vi.get(row.name)
        # the Vietnamese names last: a rename above changed the English they
        # are compared with
        self._write_options_vi(vi_wanted)
        meta.retired_values = retired

    @api.model
    def update_field(self, model, name, spec):
        self._check_gate(model)
        host = self._host(model)
        field, meta = self._custom_field(model, name)
        spec = spec or {}
        if 'type' in spec and spec['type'] != field.ttype:
            raise UserError(_("A field's type cannot be changed."))
        if 'comodel' in spec and spec['comodel'] and \
                spec['comodel'] != field.relation:
            raise UserError(_("What a link points at cannot be changed."))
        fvals, mvals = {}, {}
        en = field.with_context(lang='en_US')
        if 'label' in spec:
            label = (spec.get('label') or '').strip()
            if not label:
                raise UserError(_("Give the field a label."))
            if label != en.field_description:
                fvals['field_description'] = label
        if 'help' in spec:
            help_ = (spec.get('help') or '').strip() or False
            if help_ != (en.help or False):
                fvals['help'] = help_
        vis = spec.get('vis', meta.vis)
        if vis not in VIS:
            raise UserError(_("Choose who sees this field."))
        required = bool(spec.get('required', meta.required))
        republish = False
        if required != meta.required:
            mvals['required'] = required
            republish = True
            if field.ttype == 'many2one':
                fvals['on_delete'] = 'restrict' if required else 'set null'
        if vis != meta.vis or vis != (field.fs_vis or 'all'):
            fvals['fs_vis'] = vis
            mvals['vis'] = vis
        for key in ('phi', 'pwa', 'list_ok'):
            if key in spec:
                mvals[key] = bool(spec[key])
        if mvals.get('phi', meta.phi):
            mvals['list_ok'] = False
        for key in ('label_vi', 'help_vi'):
            if key in spec:
                mvals[key] = (spec.get(key) or '').strip() or False
        if field.ttype == 'selection' and 'options' in spec:
            self._apply_options(field, spec['options'], meta)
        if fvals:
            field.sudo().with_context(lang='en_US').write(fvals)
        if mvals:
            meta.write(mvals)
        self._write_vi(field, spec.get('label_vi'), spec.get('help_vi'))
        if republish:
            # the rule lives on the screen: draw the screens that show it again
            if required:
                note = _("Field \"%s\" is now required.", en.field_description)
            else:
                note = _("Field \"%s\" is no longer required.",
                         en.field_description)
            self._republish_with(model, name, note)
        self._audit(host, _("Field \"%(label)s\" changed by %(who)s.",
                            label=en.field_description,
                            who=self.env.user.name))
        return True

    @api.model
    def _placed(self, layout, name):
        return any(f.get('name') == name for sec in layout.sections or []
                   for f in sec.get('fields') or [])

    @api.model
    def _republish_with(self, model, name, note):
        for layout in self.env['fs.layout'].sudo().search(
                [('model', '=', model)]):
            host = self._host_of_layout(layout)
            if host and self._placed(layout, name):
                layout._publish(layout.sections, host, note=note)

    @api.model
    def _fs_extra_references(self, field):
        """Hook: places a product's own modules keep a field name."""
        return []

    @api.model
    def field_references(self, model, name):
        self._check_gate(model)
        field, _meta = self._custom_field(model, name)
        refs = []
        Model = self.env[model].sudo().with_context(active_test=False)
        refs.append({'kind': 'values', 'blocker': False,
                     'label': _("Records with a value"),
                     'count': Model.search_count([(name, '!=', False)])})
        for layout in self.env['fs.layout'].sudo().search(
                [('model', '=', model)]):
            placed = any(f.get('name') == name
                         for sec in layout.sections or []
                         for f in sec.get('fields') or [])
            if placed:
                host = self._host_of_layout(layout)
                refs.append({'kind': 'layout', 'blocker': False, 'count': 1,
                             'label': _("Placed on %s",
                                        host._title() if host else model)})
        lines = self.env['ir.exports.line'].sudo().search(
            [('export_id.resource', '=', model), ('name', 'ilike', name)])
        if lines:
            refs.append({'kind': 'export', 'blocker': True,
                         'count': len(lines.export_id),
                         'label': _("Saved export lists: %s",
                                    ', '.join(lines.export_id.mapped('name')))})
        filters = self.env['ir.filters'].sudo().with_context(
            active_test=False).search(
            [('model_id', '=', model), '|', ('domain', 'ilike', name),
             ('context', 'ilike', name)])
        if filters:
            refs.append({'kind': 'filter', 'blocker': True,
                         'count': len(filters),
                         'label': _("Saved filters: %s",
                                    ', '.join(filters.mapped('name')))})
        actions = self.env['ir.actions.server'].sudo().with_context(
            active_test=False).search(
            [('model_name', '=', model), ('code', 'ilike', name)])
        if actions:
            refs.append({'kind': 'action', 'blocker': True,
                         'count': len(actions),
                         'label': _("Automatic actions: %s",
                                    ', '.join(actions.mapped('name')))})
        refs += self._fs_extra_references(field)
        return refs

    @staticmethod
    def _strip(sections, names):
        out = []
        for sec in sections or []:
            sec = dict(sec)
            sec['fields'] = [f for f in sec.get('fields') or []
                             if f.get('name') not in names]
            out.append(sec)
        return out

    @api.model
    def delete_field(self, model, name, confirm=None):
        self._check_gate(model)
        if confirm != 'DELETE':
            raise UserError(_("Type DELETE to confirm."))
        field, meta = self._custom_field(model, name)
        refs = self.field_references(model, name)
        blockers = [r for r in refs if r.get('blocker')]
        if blockers:
            raise UserError(_(
                "This field is still used by: %s. Remove it there first.",
                '; '.join(r['label'] for r in blockers)))
        count = next(r['count'] for r in refs if r['kind'] == 'values')
        label = field.with_context(lang='en_US').field_description
        host = self._host(model)
        # Every layout drawing the field is republished WITHOUT it first: a
        # view that names a missing field takes the whole form down.
        for layout in self.env['fs.layout'].sudo().search([('model', '=', model)]):
            placed = any(f.get('name') == name
                         for sec in layout.sections or []
                         for f in sec.get('fields') or [])
            layout_host = self._host_of_layout(layout)
            if placed and layout_host:
                layout._publish(self._strip(layout.sections, {name}),
                                layout_host,
                                note=_("Field \"%s\" deleted.", label))
            for draft in self.env['fs.layout.draft'].sudo().search(
                    [('layout_id', '=', layout.id)]):
                draft.sections = self._strip(draft.sections, {name})
        meta.unlink()
        with self.env.cr.savepoint():
            field.sudo().unlink()
        if count == 1:
            body = _("Field \"%(label)s\" deleted by %(who)s. 1 record had a "
                     "value.", label=label, who=self.env.user.name)
        else:
            body = _("Field \"%(label)s\" deleted by %(who)s. %(count)s records "
                     "had a value.", label=label, who=self.env.user.name,
                     count=count)
        self._audit(host, body)
        _logger.info("Form Studio: uid %s deleted %s.%s (%s values)",
                     self.env.uid, model, name, count)
        return {'count': count}

    # ==================================================================
    #  Layouts
    # ==================================================================
    @api.model
    def publish(self, model, view_id, sections, base_version=None):
        self._check_gate(model)
        host = self._host(model, view_id)
        layout = self._layout(host)
        if base_version is not None and int(base_version) != layout.version:
            raise UserError(_("Someone else published a newer version. "
                              "Reload Studio to see it."))
        res = layout._publish(sections, host)
        self.env['fs.layout.draft'].sudo().search(
            [('layout_id', '=', layout.id),
             ('user_id', '=', self.env.uid)]).unlink()
        return res

    @api.model
    def rollback(self, layout_id, version):
        layout = self.env['fs.layout'].sudo().browse(int(layout_id)).exists()
        if not layout:
            raise UserError(_("This layout no longer exists."))
        self._check_gate(layout.model)
        host = self._host_of_layout(layout)
        if not host:
            raise UserError(_("This screen does not support Studio."))
        hist = self.env['fs.layout.history'].sudo().search(
            [('layout_id', '=', layout.id), ('version', '=', int(version))],
            limit=1)
        if not hist:
            raise UserError(_("That version no longer exists."))
        Model = self.env[layout.model]
        gone = {f.get('name') for sec in hist.sections or []
                for f in sec.get('fields') or []
                if f.get('name') not in Model._fields}
        note = _("Back to version %s.", hist.version)
        if gone:
            note = '%s %s' % (note, _(
                "%s deleted fields were left out.", len(gone)))
        res = layout._publish(self._strip(hist.sections, gone), host,
                              note=note)
        self.env['fs.layout.draft'].sudo().search(
            [('layout_id', '=', layout.id),
             ('user_id', '=', self.env.uid)]).unlink()
        return dict(res, dropped=len(gone))

    @api.model
    def validate_all(self):
        """Re-draw every layout against today's screen; switch off the ones
        that no longer fit. For the deploy step and a nightly job (later)."""
        if not (self.env.uid == SUPERUSER_ID or self._is_gate_user()
                or self.env.user.has_group('base.group_system')):
            raise self._deny()
        layouts = self.env['fs.layout'].sudo().with_context(
            active_test=False).search([('view_id', '!=', False)])
        broken = []
        for layout in layouts:
            host = self._host_of_layout(layout)
            reason = (layout._validate_one(host) if host else
                      _("The screen no longer supports Studio."))
            if reason:
                layout._switch_off(reason)
                broken.append({'layout_id': layout.id, 'model': layout.model,
                               'reason': reason})
            elif layout.state == 'broken':
                layout.sudo().write({'state': 'ok', 'broken_reason': False})
        return {'checked': len(layouts), 'broken': broken}

    # ==================================================================
    #  Visibility after the settings change
    # ==================================================================
    @api.model
    def _reapply_visibility(self):
        """Touch every Studio field that has a group, so the registry builds
        it again with today's settings. One write per visibility value."""
        Fields = self.env['ir.model.fields'].sudo()
        for vis in ('staff', 'admin'):
            rows = Fields.search([('state', '=', 'manual'),
                                  ('name', '=like', FS_PREFIX + '%'),
                                  ('fs_vis', '=', vis)])
            if rows:
                rows.write({'fs_vis': vis})
        return True

    @api.model
    def reapply_visibility(self):
        if not self._is_gate_user():
            raise self._deny()
        return self._reapply_visibility()

    # ==================================================================
    #  The field library
    # ==================================================================
    @api.model
    def library(self):
        if not self._is_gate_user():
            raise self._deny()
        hosts, by_model = [], {}
        for host in self.env['fs.host'].sudo().search([]):
            base = host._base_view()
            if not base or host.model not in self.env:
                continue
            try:
                self.env[host.model].check_access('write')
            except AccessError:
                continue
            item = {'model': host.model, 'title': host._title(),
                    'view_id': base.id}
            hosts.append(item)
            by_model.setdefault(host.model, item)
        rows = []
        metas = self.env['fs.field.meta'].sudo().search([])
        for meta in metas:
            field = meta.field_id
            if not field or field.model not in by_model:
                continue
            Model = self.env[field.model]
            try:
                filled = Model.search_count([(field.name, '!=', False)])
                total = Model.search_count([])
            except AccessError:
                filled = total = None
            rows.append({
                'model': field.model,
                'screen': by_model[field.model]['title'],
                'view_id': by_model[field.model]['view_id'],
                'name': field.name,
                'label': Model.sudo().fields_get(
                    [field.name], ['string']).get(field.name, {}).get(
                        'string') or field.name,
                'type': field.ttype,
                'type_label': self._type_label(field.ttype),
                'vis': meta.vis,
                'phi': meta.phi,
                'list_ok': meta.list_ok,
                'pwa': meta.pwa,
                'filled': filled,
                'total': total,
                'created_by': meta.created_by.name or '',
                'created_on': meta.create_date and
                meta.create_date.date().isoformat(),
            })
        pwa_label = next((h.pwa_label for h in self.env['fs.host'].sudo()
                          .search([]) if h.pwa_label), False)
        return {'hosts': hosts, 'rows': rows,
                'pwa_label': pwa_label or _('Mobile app')}

    @api.model
    def first_record(self, model):
        """A record to open Studio beside, or False — the editor works
        without one."""
        self._check_gate(model)
        try:
            rec = self.env[model].search([], limit=1)
        except AccessError:
            return False
        return rec.id or False
