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
"""
import logging

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

from .fs_common import ANCHOR_NAME_RE, FS_PREFIX, SECTION_ID_RE

_logger = logging.getLogger(__name__)


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
    def _clean_sections(self, sections, model):
        """Validate the client's description and return a normalised copy.

        Raises UserError naming the first problem. Empty sections are kept in
        the description (an administrator may be about to fill one) but are
        not drawn.
        """
        Model = self.env[model]
        if not isinstance(sections, list):
            raise UserError(_("The layout could not be read. Reload Studio."))
        seen_ids, seen_fields, out = set(), set(), []
        for sec in sections:
            if not isinstance(sec, dict):
                raise UserError(_("The layout could not be read. Reload Studio."))
            sid = str(sec.get('id') or '')
            if not SECTION_ID_RE.match(sid) or sid in seen_ids:
                raise UserError(_("The layout could not be read. Reload Studio."))
            seen_ids.add(sid)
            anchor = sec.get('anchor') or {'kind': 'before_notebook'}
            kind = anchor.get('kind')
            if kind not in ('card', 'sheet_end', 'before_notebook'):
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
    def _field_node(self, Model, name, required=False):
        field = Model._fields[name]
        node = etree.Element('field', name=name)
        if required:
            node.set('required', '1')
        if field.type == 'binary':
            node.set('widget', 'binary')
        elif field.type == 'many2one':
            node.set('options', "{'no_create': True}")
        return node

    @api.model
    def _render_arch(self, sections, host, base_view):
        """The inherited view's arch for `sections` on `host`'s form."""
        Model = self.env[host.model]
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
        for sec in sections:
            names = [f['name'] for f in sorted(
                sec.get('fields') or [], key=lambda f: f.get('order', 0))]
            for name in names:
                if name not in Model._fields:
                    raise UserError(_(
                        "The field %s no longer exists. Reload Studio.", name))
            if not names:
                continue
            anchor = sec.get('anchor') or {'kind': 'before_notebook'}
            if anchor['kind'] == 'card':
                card = anchor.get('name')
                if card not in open_cards:
                    raise UserError(_(
                        "The card \"%s\" no longer accepts fields.", card))
                if host.kit == 'ws':
                    expr = "//div[@name='%s']/group" % card
                else:
                    expr = "//group[@name='%s']" % card
                xp = etree.SubElement(root, 'xpath', expr=expr,
                                      position='inside')
                for name in names:
                    xp.append(self._field_node(Model, name, name in required))
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
        clean = self._clean_sections(sections, self.model)
        arch = self._render_arch(clean, host, base_view)
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
        self.env['fs.layout.history'].sudo().create({
            'layout_id': self.id,
            'version': version,
            'sections': clean,
            'arch': arch,
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
        return {'version': version, 'view_id': self.view_id.id}

    # ------------------------------------------------------------------
    #  The validator
    # ------------------------------------------------------------------
    def _validate_one(self, host):
        """Re-draw against today's form. Returns None, or why it failed."""
        self.ensure_one()
        if not self.view_id or not self.sections:
            return None
        try:
            with self.env.cr.savepoint():
                arch = self._render_arch(
                    self._clean_sections(self.sections, self.model), host,
                    self.base_view_id.sudo())
                self.view_id.sudo().with_context(lang='en_US').write(
                    {'arch': arch, 'active': True})
                self.base_view_id.sudo()._get_combined_arch()
        except Exception as exc:  # noqa: BLE001 — any failure switches it off
            self.env.invalidate_all()
            return str(exc) or exc.__class__.__name__
        return None

    def _switch_off(self, reason):
        self.ensure_one()
        if self.view_id:
            self.view_id.sudo().write({'active': False})
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
    published_by = fields.Many2one('res.users', ondelete='set null')
    published_at = fields.Datetime()

    def write(self, vals):
        raise UserError(_("A published version cannot be changed."))

    def unlink(self):
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(_("A published version cannot be deleted."))
