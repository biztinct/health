import json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .identity import clean_image, clean_identity

COMPANY_FIELDS = ('name', 'street', 'street2', 'city', 'zip', 'phone', 'email', 'website', 'vat', 'company_registry')
STEPS = ('company', 'facilities', 'people', 'services', 'connections', 'review')


class Workspace(models.AbstractModel):
    _name = 'health.tenant.workspace'
    _description = 'Your company and clinic setup'

    def _guard(self):
        if not (self.env.user.has_group('base.group_system') or self.env.user.has_group('health_access.group_clinic_admin')):
            raise AccessError(_('Only a clinic administrator can open these settings.'))
        # Ignore caller-supplied allowed_company_ids.
        return self.env.user.company_id.sudo()

    @api.model
    def profile(self):
        company = self._guard()
        return {'company': {k: company[k] or '' for k in COMPANY_FIELDS},
                'brand': self.env['ir.http']._tenant_identity(),
                'country': company.country_id.name or '', 'currency': company.currency_id.name,
                'logo': '/web/image/res.company/%s/logo' % company.id,
                'countries': self.env['res.country'].search_read([], ['name'], order='name'),
                'country_id': company.country_id.id or False,
                'revision': company.write_date.isoformat()}

    @api.model
    def save_profile(self, values, revision):
        company = self._guard()
        if set(values) - set(COMPANY_FIELDS) - {'country_id', 'logo'}:
            raise AccessError(_('Only company contact and legal details can be changed here.'))
        self.env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', [company.id])
        company.invalidate_recordset()
        if company.write_date.isoformat() != revision:
            raise ValidationError(_('These details changed since you opened them. Refresh before saving.'))
        clean = {}
        for k, v in values.items():
            if k == 'logo':
                clean[k] = clean_image(v)
            elif k == 'website':
                clean[k] = clean_identity({'website': v})['website']
            elif k == 'country_id':
                country = self.env['res.country'].browse(int(v or 0)).exists()
                if not country:
                    raise ValidationError(_('Choose a country.'))
                clean[k] = country.id
            else:
                clean[k] = str(v or '').strip()[:500]
        if not clean.get('name', company.name):
            raise ValidationError(_('Enter your company name.'))
        changes = {k: {'before': str(company[k] or ''), 'after': v} for k, v in clean.items() if k not in ('logo', 'country_id') and (company[k] or '') != v}
        if 'logo' in clean:
            self.env['ir.config_parameter'].sudo().set_param('tenant.identity.company_logo_custom', '1' if clean['logo'] else '')
            changes['logo'] = {'before': _('Previous image'), 'after': _('Image updated')}
        if 'country_id' in clean and clean['country_id'] != company.country_id.id:
            changes['country'] = {'before': company.country_id.name, 'after': self.env['res.country'].browse(clean['country_id']).name}
        company.write(clean)
        if changes:
            self.env['health.workspace.audit']._record(_('Company details'), changes, company)
        return self.profile()

    @api.model
    def setup_state(self):
        company = self._guard()
        p = self.env['ir.config_parameter'].sudo()
        key = 'tenant.setup.%s' % company.id
        try:
            draft = json.loads(p.get_param(key) or '{}')
        except (ValueError, TypeError):
            draft = {}
        checks = [
            {'key': 'company', 'label': _('Company details'), 'ready': bool(company.name and company.street and company.country_id), 'action': False},
            {'key': 'facilities', 'label': _('Facilities'), 'ready': self._has('health.facility'), 'action': self._action_for('health.facility')},
            {'key': 'people', 'label': _('Staff and access'), 'ready': self.env['res.users'].sudo().search_count([('company_id','=',company.id),('share','=',False),('active','=',True)]) > 1, 'action': 'biz_access.action_biz_access_home'},
            {'key': 'services', 'label': _('Services and prices'), 'ready': self._has('product.template', [('type','=','service'), ('list_price','>',0)]), 'action': self._action_for('product.template')},
            {'key': 'connections', 'label': _('Connections'), 'ready': self._has('care.channel.connection', [('state','=','ready')]), 'action': self._action_for('care.channel.connection'), 'optional': True},
        ]
        return {'step': draft.get('step', 'company'), 'notes': draft.get('notes',''), 'completed': draft.get('completed', False), 'checks': checks}

    def _has(self, model, domain=None):
        if model not in self.env:
            return False
        obj = self.env[model]
        dom = list(domain or [])
        if 'company_id' in obj._fields:
            dom += [('company_id','in',[False,self.env.user.company_id.id])]
        try:
            return bool(obj.search_count(dom, limit=1))
        except AccessError:
            return False

    def _action_for(self, model):
        action = self.env['ir.actions.act_window'].sudo().search([('res_model','=',model)], limit=1)
        return action.id if action else False

    @api.model
    def save_setup(self, step, notes='', complete=False):
        company = self._guard()
        if step not in STEPS:
            raise ValidationError(_('Choose a setup step.'))
        if complete and any(not x['ready'] for x in self.setup_state()['checks'] if not x.get('optional')):
            raise ValidationError(_('Complete the required checks before finishing setup.'))
        data = {'step': step, 'notes': str(notes or '')[:4000], 'completed': bool(complete)}
        self.env['ir.config_parameter'].sudo().set_param('tenant.setup.%s' % company.id, json.dumps(data))
        if complete:
            self.env['health.workspace.audit']._record(_('Clinic setup completed'), {'checks': _('Required checks passed')}, company)
        return self.setup_state()

    @api.model
    def history(self, source='all', query='', offset=0):
        """Bounded merged timeline. Each source is read with its own ACLs."""
        company = self._guard()
        offset = max(0, min(int(offset or 0), 5000))
        limit = offset + 51
        sources = {
            'workspace': ('health.workspace.audit', 'happened_at', 'subject'),
            'clinical': ('health.audit.log.view', 'date', 'field_name'),
            'access': ('biz.access.delegation', 'create_date', 'display_name'),
            'api': ('api.audit.log', 'create_date', 'display_name'),
            'support': ('biz.support.session', 'issued_at', 'reason'),
            'channels': ('care.channel.audit', 'create_date', 'display_name'),
        }
        if source not in ('all', *sources):
            raise ValidationError(_('Choose a history source.'))
        rows, availability = [], []
        for key, (model, datefield, titlefield) in sources.items():
            if source != 'all' and source != key:
                continue
            if model not in self.env:
                availability.append({'source': key, 'status': _('Not installed')});continue
            obj = self.env[model]
            dom = [('company_id','=',company.id)] if 'company_id' in obj._fields else []
            if query and titlefield != 'display_name':
                dom.append((titlefield, 'ilike', str(query)[:100]))
            try:
                records = obj.search(dom, order=datefield+' desc, id desc', limit=limit)
                for r in records:
                    title = str(r[titlefield] or '')
                    if query and titlefield == 'display_name' and query.lower() not in title.lower():
                        continue
                    actor = r.actor_id.name if model == 'health.workspace.audit' else r.create_uid.name if 'create_uid' in r._fields else ''
                    # Summary only: no clinical text, API payloads, bank details or tokens.
                    detail = r.detail if model == 'health.workspace.audit' else ''
                    rows.append({'key': key+':'+str(r.id), 'source': key, 'date': fields.Datetime.to_string(r[datefield]), 'title': title, 'actor': actor or '', 'detail': detail})
                availability.append({'source': key, 'status': _('Available')})
            except AccessError:
                availability.append({'source': key, 'status': _('Restricted by your access')})
        rows.sort(key=lambda r: (r['date'] or '', r['key']), reverse=True)
        return {'rows': rows[offset:offset+50], 'more': len(rows)>offset+50, 'sources': availability}

    @api.model
    def _seed_navigation(self):
        customers = self.env.ref('health_tenancy.item_admin_customers', raise_if_not_found=False)
        if customers:
            tags = [v.strip() for v in (customers.match_action_tags or '').split(',') if v.strip()]
            if 'biz_tenant_identity' not in tags:
                customers.sudo().write({'match_action_tags': ','.join(tags + ['biz_tenant_identity'])})
        section = self.env.ref('health_cms_sidebar.section_admin')
        roles = self.env['biz.access.role'].sudo().search([('name','in',['Owner','Admin'])])
        for suffix, title, tag, sequence in [('company','Your company','health_tenant_company',81),('setup','Clinic setup','health_tenant_setup',82),('history','Activity history','health_tenant_history',83)]:
            action = self.env.ref('health_tenant_workspace.action_'+suffix)
            xmlid = 'health_tenant_workspace.item_'+suffix
            item = self.env.ref(xmlid, raise_if_not_found=False)
            vals = {'name': title, 'section_id': section.id, 'sequence': sequence, 'icon': 'fa fa-building-o', 'action_xmlid': 'health_tenant_workspace.action_'+suffix, 'match_action_tags': tag, 'biz_role_ids': [(6,0,roles.ids)]}
            if not item:
                item = self.env['cms.sidebar.item'].sudo().create(vals)
                self.env['ir.model.data'].sudo().create({'module':'health_tenant_workspace','name':'item_'+suffix,'model':'cms.sidebar.item','res_id':item.id,'noupdate':True})
        return True
