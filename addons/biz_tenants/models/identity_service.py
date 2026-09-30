"""Per-customer identity and provisioning locale; no approval or mail hooks."""
import re
import logging
import socket
import subprocess
from urllib.parse import urlsplit
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from . import tenants_common as common

_logger = logging.getLogger(__name__)

LEVELS = [('product','Our product'),('powered','Their brand, powered by us'),('white','Their brand only')]
IDENTITY_FIELDS = ('brand_level','brand_name','brand_website','brand_color','brand_logo','brand_favicon','country_id','currency_id')

class Tenant(models.Model):
    _inherit = 'biz.tenant'
    brand_level = fields.Selection(LEVELS, default='product', required=True)
    brand_name = fields.Char()
    brand_website = fields.Char()
    brand_color = fields.Char(default='#1565C0')
    brand_logo = fields.Binary(attachment=True)
    brand_favicon = fields.Binary(attachment=True)
    brand_pushed_at = fields.Datetime()
    country_id = fields.Many2one('res.country')
    currency_id = fields.Many2one('res.currency')

class Domain(models.Model):
    _inherit = 'biz.tenant.domain'
    state = fields.Selection([('pending','Check DNS'),('verified','Ready to activate'),('active','Active'),('error','Needs attention')],default='pending',required=True)
    last_check = fields.Datetime()

class IdentityService(models.AbstractModel):
    _inherit = 'biz.tenants'

    @api.model
    def get_tenant(self, tenant_id):
        result = super().get_tenant(tenant_id)
        result['custom_domains_note'] = _('Open Brand and addresses to add a customer-owned hostname, check DNS and activate HTTPS.')
        return result

    def _identity_tenant(self, tenant_id):
        self._require_platform_admin()
        t = self.env['biz.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t or t.state == 'decommissioned':
            raise UserError(_('Choose an existing customer.'))
        return t

    @api.model
    def identity_options(self):
        self._require_platform_admin()
        return {'countries': self.env['res.country'].search_read([],['name','code'],order='name'),
                'currencies': self.env['res.currency'].with_context(active_test=False).search_read([],['name'],order='name')}

    def _identity_form(self, form):
        vals = {k: form[k] for k in IDENTITY_FIELDS if k in form}
        if vals.get('brand_level','product') not in dict(LEVELS):
            raise ValidationError(_('Choose one of the branding options.'))
        color = vals.get('brand_color')
        if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValidationError(_('Use a colour such as #1565C0.'))
        for key, model in [('country_id','res.country'),('currency_id','res.currency')]:
            if key in vals:
                vals[key] = int(vals[key] or 0) or False
                if vals[key] and not self.env[model].with_context(active_test=False).browse(vals[key]).exists():
                    raise ValidationError(_('Choose an available country and currency.'))
        return vals

    @api.model
    def provision_preview(self, form):
        vals = self._identity_form(form)
        result = super().provision_preview(form)
        name = vals.get('brand_name') or form.get('name') or ''
        result['plan'][1]['what'] += ' ' + (_('Application name: %s.', name) if vals.get('brand_level','product') != 'product' else _('Keep the platform product name.'))
        return result

    @api.model
    def provision_start(self, form):
        result = super().provision_start(form)
        self._identity_tenant(result['tenant_id']).write(self._identity_form(form))
        return result

    def _identity_values(self, t):
        p=self.env['ir.config_parameter'].sudo()
        return {'level':t.brand_level,'name':t.brand_name or '',
                'website':t.brand_website or self._tenant_url(t.slug),
                'color':t.brand_color or '#1565C0',
                'product':common.brand(self.env) or p.get_param('biz_debranding.brand_name'),
                'logo':t.brand_logo.decode() if isinstance(t.brand_logo,bytes) else t.brand_logo or '',
                'favicon':t.brand_favicon.decode() if isinstance(t.brand_favicon,bytes) else t.brand_favicon or ''}

    def _step_configure(self, tenant, say, preview):
        result = super()._step_configure(tenant,say,preview)
        if preview:
            say(_('Would apply the selected brand, country and currency.'))
            return result
        with self._tenant_env(tenant.slug) as env:
            company=env['res.company'].sudo().browse(1)
            updates={}
            if tenant.country_id:
                country=env['res.country'].search([('code','=',tenant.country_id.code)],limit=1)
                if not country: raise UserError(_('The selected country is unavailable in the template.'))
                updates['country_id']=country.id
            if tenant.currency_id and company.currency_id.name != tenant.currency_id.name:
                if 'account.move' in env and env['account.move'].sudo().search_count([],limit=1):
                    raise UserError(_('The template contains accounting entries. Currency cannot be changed safely.'))
                currency=env['res.currency'].with_context(active_test=False).search([('name','=',tenant.currency_id.name)],limit=1)
                if not currency: raise UserError(_('The selected currency is unavailable in the template.'))
                currency.sudo().write({'active':True});updates['currency_id']=currency.id
            if updates: company.write(updates)
            if not hasattr(env['ir.http'],'_apply_tenant_identity'):
                raise UserError(_('Update the blank system before creating customers with these settings.'))
            env['ir.http']._apply_tenant_identity(self._identity_values(tenant))
        tenant.write({'brand_pushed_at':fields.Datetime.now()})
        say(_('Brand, country and currency applied.'))
        return result

    @api.model
    def tenant_brand(self, tenant_id):
        t=self._identity_tenant(tenant_id)
        desired=self._identity_values(t)
        live={};differences=[];reachable=False
        try:
            with self._tenant_env(t.slug) as env:
                p=env['ir.config_parameter'].sudo()
                live=env['ir.http']._tenant_identity()
                differences=[k for k,v in desired.items() if (p.get_param('tenant.identity.'+k) or '') != (v or '')]
                reachable=True
        except Exception:
            pass
        return {'id':t.id,'name':t.name,'values':{k:getattr(t,k) or '' for k in ('brand_level','brand_name','brand_website','brand_color')},
                'live':live,'reachable':reachable,'differences':differences,'in_step':reachable and not differences,
                'pushed_at':str(t.brand_pushed_at or ''),'domains':[{'id':d.id,'hostname':d.hostname,'state':d.state,'note':d.note or '','kind':d.kind} for d in t.domain_ids]}

    @api.model
    def tenant_set_brand(self, tenant_id, values):
        t=self._identity_tenant(tenant_id)
        allowed=set(IDENTITY_FIELDS)-{'country_id','currency_id'}
        if set(values)-allowed: raise UserError(_('Only branding can be changed on this screen.'))
        vals=self._identity_form(values)
        # Validate and normalise images/URLs before saving intent on the master.
        clean=self.env['ir.http']._validate_tenant_identity({k.removeprefix('brand_'):v for k,v in vals.items()})
        t.write({'brand_'+k:v for k,v in clean.items()})
        t.log(_('Branding choice saved.'))
        return self.tenant_push_brand(t.id)

    @api.model
    def tenant_push_brand(self, tenant_id):
        t=self._identity_tenant(tenant_id)
        with self._tenant_env(t.slug) as env:
            env['ir.http']._apply_tenant_identity(self._identity_values(t))
        t.write({'brand_pushed_at':fields.Datetime.now()})
        t.log(_('Branding applied to the customer database.'))
        return self.tenant_brand(t.id)

    @api.model
    def domain_add(self, tenant_id, hostname):
        t=self._identity_tenant(tenant_id)
        host=str(hostname or '').strip().lower().rstrip('.')
        if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+',host):
            raise UserError(_('Enter a hostname such as care.example.com.'))
        if host == self._apex() or host == 'www.'+self._apex() or host == self._tenant_host(t.slug):
            raise UserError(_('This address already belongs to the platform.'))
        if host.endswith('.'+self._apex()) and self.env['biz.tenant'].sudo().search_count([('slug','=',host[:-len(self._apex())-1])]):
            raise UserError(_('This address already belongs to the platform.'))
        if t.state != 'live':raise UserError(_('The customer must be live before adding an address.'))
        Domain=self.env['biz.tenant.domain'].sudo()
        if Domain.search_count([('hostname','=',host)]):raise UserError(_('That address is already attached to a customer.'))
        Domain.create({'tenant_id':t.id,'hostname':host,'kind':'custom','state':'pending'})
        return self.tenant_brand(t.id)

    def _identity_domain(self, domain_id):
        self._require_platform_admin()
        d=self.env['biz.tenant.domain'].sudo().browse(int(domain_id)).exists()
        if not d or d.kind != 'custom':raise UserError(_('Choose a customer-owned address.'))
        return d

    @api.model
    def domain_check(self, domain_id):
        d=self._identity_domain(domain_id)
        expected=common.param(self.env,'biz_tenants.public_ip') or '54.206.18.111'
        try: ips={x[4][0] for x in socket.getaddrinfo(d.hostname,443,type=socket.SOCK_STREAM)}
        except socket.gaierror:ips=set()
        ok=bool(ips) and ips == {expected}
        d.write({'state':'active' if d.state=='active' else 'verified' if ok else 'pending', 'last_check':fields.Datetime.now(), 'note':_('DNS is ready.') if ok else _('Point the address to %s, then check again.',expected)})
        return self.tenant_brand(d.tenant_id.id)

    @api.model
    def domain_activate(self, domain_id):
        d=self._identity_domain(domain_id)
        if d.tenant_id.state != 'live':
            raise UserError(_('The customer must be live before adding an address.'))
        if d.state == 'active':
            return self.tenant_brand(d.tenant_id.id)
        self.domain_check(d.id)
        if d.state not in ('verified','active'):raise UserError(_('Check DNS before activating the address.'))
        proc=subprocess.run(['sudo','-n','/usr/local/bin/biz-domain-attach',d.hostname,d.tenant_id.slug],capture_output=True,text=True,timeout=180)
        if proc.returncode:
            raise UserError(_('The address could not be activated. Ask the platform administrator to check the certificate and routing logs.'))
        d.write({'state':'active','note':_('Serving securely with HTTPS.')})
        d.tenant_id.log(_('Customer address activated: %s',d.hostname))
        return self.tenant_brand(d.tenant_id.id)

    @api.model
    def domain_remove(self, domain_id):
        d=self._identity_domain(domain_id);tenant=d.tenant_id
        # Even a pending row may have completed externally before a request
        # timed out. The root helper only removes this exact managed address.
        proc=subprocess.run(['sudo','-n','/usr/local/bin/biz-domain-detach',d.hostname,'--custom',tenant.slug],capture_output=True,text=True,timeout=120)
        if proc.returncode:raise UserError(_('The address could not be removed. Please try again.'))
        d.unlink()
        return self.tenant_brand(tenant.id) if tenant.state != 'decommissioned' else {'ok': True}

    def _detach_cert(self, tenant):
        super()._detach_cert(tenant)
        for domain in tenant.domain_ids.filtered(lambda d: d.kind == 'custom'):
            try:
                proc = subprocess.run(['sudo', '-n', '/usr/local/bin/biz-domain-detach', domain.hostname, '--custom', tenant.slug], capture_output=True, text=True, timeout=120)
                if proc.returncode:
                    raise RuntimeError('Domain helper returned an error')
                domain.write({'state': 'pending', 'note': _('Customer closed; address disabled.')})
            except Exception:
                _logger.exception('Could not detach customer domain %s', domain.hostname)
                domain.write({'state': 'error', 'note': _('Address removal needs administrator attention.')})
