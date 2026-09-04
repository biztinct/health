# -*- coding: utf-8 -*-
"""The matrix: every customer a column, every part of the product a row.

THE HERO OF THIS PHASE, AND WHY IT IS A GRID. "Which customers have
Telehealth?" and "what does this customer get?" are the same question asked
along two axes, and a list of customers with a list of switches inside each one
answers only the second. A grid answers both, takes bulk actions in either
direction, and — this is the part that matters — has room beside it for a
MINIATURE OF THAT CUSTOMER'S OWN LEFT MENU, redrawing as the switches move. The
owner sees what the customer will see before pressing anything.

⚠ EVERY HELPER HERE IS NAMED FOR THIS FILE (ledger F52). `biz.tenants` is one
model assembled from five files; a helper called `_values` added to a shared
facade is added to every file that shares it, and a name collision there once
broke a button two phases old.

THE WRITE PATH IS THE ONE THAT ALREADY EXISTS. Nothing in here opens a customer's
database: a switch is stored on the platform, and `push_settings` — the single
door, which refuses the platform's own system, leaves a line in the customer's
log and signals every worker (F56) — carries it across.
"""
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common

_logger = logging.getLogger(__name__)


class BizTenantsFeatures(models.AbstractModel):
    _inherit = 'biz.tenants'

    # =====================================================================
    #  READING
    # =====================================================================
    def _feature_rows(self):
        return self.env['biz.feature'].sudo().catalogue()

    def _feature_answers(self, tenants):
        """`{tenant_id: {key: {'on', 'reason', 'changed_at'}}}`.

        A CUSTOMER WITH NO ROW HAS IT ON. The absence of a decision is not a
        decision, and a switch nobody has touched must never take half a
        product away.
        """
        rows = self._feature_rows()
        out = {t.id: {f.key: {'on': bool(f.default_on), 'reason': '',
                              'changed_at': None, 'decided': False}
                      for f in rows}
               for t in tenants}
        answers = self.env['biz.tenant.feature'].sudo().search(
            [('tenant_id', 'in', tenants.ids)])
        for a in answers:
            if a.tenant_id.id in out and a.feature_id.key in out[a.tenant_id.id]:
                out[a.tenant_id.id][a.feature_id.key] = {
                    'on': bool(a.enabled),
                    'reason': a.reason or '',
                    'changed_at': self._stamp(a.changed_at),
                    'decided': True,
                }
        return out

    def _feature_off_keys(self, tenant):
        answers = self._feature_answers(tenant)
        return sorted(k for k, v in answers.get(tenant.id, {}).items()
                      if not v['on'])

    def _feature_settings_value(self, tenant):
        """The ONE setting a customer's system reads. JSON, and it carries the
        NAME as well as the answer — because the customer's own switched-off
        page has to say "Telehealth is not switched on" in the product's words,
        and that system has never heard of a catalogue."""
        answers = self._feature_answers(tenant).get(tenant.id, {})
        rows = {f.key: f for f in self._feature_rows()}
        payload = {}
        for key, ans in answers.items():
            feature = rows.get(key)
            payload[key] = {
                'on': bool(ans['on']),
                'name': (feature.name if feature else key),
                'blurb': (feature.blurb or '') if feature else '',
            }
        return json.dumps(payload, sort_keys=True)

    # =====================================================================
    #  THE SCREEN
    # =====================================================================
    @api.model
    def features_data(self, tenant_id=None):
        """Everything the matrix draws, in one call."""
        self._require_platform_admin()
        rows = self._feature_rows()
        tenants = self._tenants().search(
            [('state', 'in', ('live', 'provisioning', 'error'))],
            order='name')
        answers = self._feature_answers(tenants)
        focus = None
        if tenant_id:
            focus = tenants.filtered(lambda t, i=int(tenant_id): t.id == i)
        if not focus:
            focus = tenants[:1]
        return {
            'features': [{
                'id': f.id, 'key': f.key, 'name': f.name,
                'blurb': f.blurb or '', 'sequence': f.sequence,
                'default_on': f.default_on,
            } for f in rows],
            'tenants': [{
                'id': t.id, 'name': t.name, 'slug': t.slug,
                'state': t.state, 'url': self._tenant_url(t.slug),
                'off': sorted(k for k, v in answers.get(t.id, {}).items()
                              if not v['on']),
            } for t in tenants],
            'answers': {str(tid): vals for tid, vals in answers.items()},
            'focus_id': focus.id if focus else 0,
            'preview': self._feature_preview_for(focus) if focus else None,
            # Said on the screen in these words, because it is the question
            # everybody asks first and the answer is reassuring.
            'note': ("Switching a part off closes the doors to it. Nothing is "
                     "removed and nothing is deleted — switch it back on and "
                     "everything that was ever recorded is still there."),
        }

    def _feature_preview_for(self, tenant):
        """The miniature of THIS customer's own left menu.

        Drawn as somebody who can open everything would see it, so that the
        only difference between the two pictures is the switch that was just
        moved. Answering it for one particular person would put a role
        question inside a sales screen.
        """
        if not tenant:
            return None
        off = self._feature_off_keys(tenant)
        sections = common.menu_preview(self.env, off)
        if sections is None:
            return {'sections': [], 'known': False, 'off': off,
                    'note': ("Nobody has told this screen what this product's "
                             "menu looks like, so there is nothing to draw "
                             "here yet.")}
        hidden = sum(1 for s in sections for i in s.get('items') or ()
                     if i.get('state') != 'on')
        hidden += sum(1 for s in sections for i in s.get('items') or ()
                      for c in i.get('children') or ()
                      if c.get('state') != 'on')
        return {'sections': sections, 'known': True, 'off': off,
                'hidden': hidden,
                'note': ("This is %s's own left menu, as somebody who can "
                         "open everything would see it." % tenant.name)}

    @api.model
    def feature_preview(self, tenant_id):
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on this screen "
                                       "any more."))
        return self._feature_preview_for(tenant)

    # =====================================================================
    #  WRITING
    # =====================================================================
    def _feature_write(self, tenant, feature, on, reason):
        Row = self.env['biz.tenant.feature'].sudo()
        row = Row.search([('tenant_id', '=', tenant.id),
                          ('feature_id', '=', feature.id)], limit=1)
        vals = {'enabled': bool(on), 'reason': (reason or '').strip(),
                'changed_at': fields.Datetime.now(),
                'changed_by': self.env.uid}
        if row:
            if row.enabled == bool(on) and (row.reason or '') == vals['reason']:
                return row, False
            row.write(vals)
        else:
            row = Row.create({'tenant_id': tenant.id,
                              'feature_id': feature.id, **vals})
        return row, True

    def _feature_push(self, tenant):
        """Send this customer their answer. One setting, one door."""
        res = self.push_settings(
            tenant.id, {common.T_FEATURES: self._feature_settings_value(tenant)})
        return res

    @api.model
    def feature_set(self, tenant_id, key, on, reason=''):
        """One switch, for one customer. The whole write path.

        REFUSES BY NAME rather than doing nothing: a screen that says a switch
        moved when it did not is worse than one that says why it could not.
        """
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not here any more."))
        if tenant.state == 'decommissioned':
            raise UserError(self.env._(
                '"%s" has been closed down. There is nothing to switch on or '
                'off on a system that is on its way out.', tenant.name))
        feature = self.env['biz.feature'].sudo().search(
            [('key', '=', key)], limit=1)
        if not feature:
            raise UserError(self.env._(
                'This product has no part called "%s".', key))
        _row, changed = self._feature_write(tenant, feature, on, reason)
        pushed = self._feature_push(tenant)
        if changed:
            tenant.log('%s was switched %s for them%s.'
                       % (feature.name, 'on' if on else 'off',
                          (' — %s' % reason.strip()) if reason else ''))
        if not pushed.get('ok'):
            _logger.warning("biz_tenants: %s could not be told about its "
                            "features: %s", tenant.slug, pushed.get('reason'))
        return {
            'ok': True, 'changed': changed, 'pushed': pushed,
            'answers': self._feature_answers(tenant).get(tenant.id, {}),
            'preview': self._feature_preview_for(tenant),
            'message': ('%s is now %s for %s.'
                        % (feature.name, 'on' if on else 'off', tenant.name)),
        }

    @api.model
    def feature_set_column(self, tenant_id, on, reason=''):
        """Every part, for one customer. The column action."""
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not here any more."))
        moved = 0
        for feature in self._feature_rows():
            _row, changed = self._feature_write(tenant, feature, on, reason)
            moved += 1 if changed else 0
        pushed = self._feature_push(tenant)
        if moved:
            tenant.log('Every part of the product was switched %s for them '
                       '(%d changed).' % ('on' if on else 'off', moved))
        return {
            'ok': True, 'changed': moved, 'pushed': pushed,
            'answers': self._feature_answers(tenant).get(tenant.id, {}),
            'preview': self._feature_preview_for(tenant),
            'message': ('%d switch%s moved for %s.'
                        % (moved, '' if moved == 1 else 'es', tenant.name)
                        if moved else 'Nothing to change for %s.' % tenant.name),
        }

    @api.model
    def feature_set_row(self, key, on, reason=''):
        """One part, for every customer. The row action."""
        self._require_platform_admin()
        feature = self.env['biz.feature'].sudo().search(
            [('key', '=', key)], limit=1)
        if not feature:
            raise UserError(self.env._(
                'This product has no part called "%s".', key))
        tenants = self._tenants().search([('state', '=', 'live')])
        moved, told, skipped = 0, 0, []
        for tenant in tenants:
            _row, changed = self._feature_write(tenant, feature, on, reason)
            if changed:
                moved += 1
                tenant.log('%s was switched %s for them%s.'
                           % (feature.name, 'on' if on else 'off',
                              (' — %s' % reason.strip()) if reason else ''))
            res = self._feature_push(tenant)
            if res.get('ok'):
                told += 1
            else:
                skipped.append({'name': tenant.name,
                                'reason': res.get('reason') or ''})
        return {
            'ok': True, 'changed': moved, 'told': told, 'skipped': skipped,
            'message': ('%s is now %s for %d customer%s.'
                        % (feature.name, 'on' if on else 'off', len(tenants),
                           '' if len(tenants) == 1 else 's')),
        }

    @api.model
    def features_push_all(self):
        """Send every customer their answer again.

        THE REPAIR BUTTON. A customer who was unreachable when a switch moved,
        or who has only just been given the platform link, is one press away
        from being in step — instead of being a discrepancy nobody can see.
        """
        self._require_platform_admin()
        out = []
        for tenant in self._tenants().search([('state', '=', 'live')]):
            res = self._feature_push(tenant)
            out.append({**res, 'tenant_id': tenant.id, 'name': tenant.name})
        return {'results': out,
                'sent': len([r for r in out if r.get('ok')]),
                'skipped': len([r for r in out if not r.get('ok')])}
