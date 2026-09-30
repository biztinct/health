"""One database identity; company details remain company-owned data."""
import base64
import re
from io import BytesIO
from urllib.parse import urlsplit
from PIL import Image
from odoo import api, models, _
from odoo.http import request
from odoo.exceptions import ValidationError

LEVELS = ('product', 'powered', 'white')


def clean_image(value):
    if not value:
        return False
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError()
        im = Image.open(BytesIO(raw))
        if im.format not in ('PNG', 'JPEG', 'WEBP') or im.width * im.height > 16000000:
            raise ValueError()
        im.load()
        im.thumbnail((1024, 1024))
        out = BytesIO()
        im.convert('RGBA').save(out, format='PNG')
        return base64.b64encode(out.getvalue()).decode()
    except Exception as exc:
        raise ValidationError(_('Choose a PNG, JPEG or WebP image smaller than 2 MB.')) from exc


def clean_identity(values):
    allowed = {'level', 'name', 'website', 'color', 'logo', 'favicon', 'product'}
    if set(values) - allowed:
        raise ValidationError(_('Some of these settings cannot be changed here.'))
    out = dict(values)
    if out.get('level', 'product') not in LEVELS:
        raise ValidationError(_('Choose one of the three branding options.'))
    for key in ('name', 'product'):
        if key in out:
            out[key] = str(out[key] or '').strip()[:120]
    if 'website' in out:
        url = str(out['website'] or '').strip().rstrip('/')
        if url and ':' in url and not url.startswith(('https://', 'http://')):
            raise ValidationError(_('Enter a valid website address.'))
        if url and not url.startswith(('https://', 'http://')):
            url = 'https://' + url
        u = urlsplit(url)
        if url and (u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password):
            raise ValidationError(_('Enter a valid website address.'))
        out['website'] = url
    if 'color' in out:
        color = str(out['color'] or '').strip() or '#1565C0'
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValidationError(_('Use a colour such as #1565C0.'))
        out['color'] = color
    for key in ('logo', 'favicon'):
        if key in out:
            out[key] = clean_image(out[key])
    return out


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        # ORM parameter caches honour cross-worker registry signalling. Refresh
        # the translation seam's small process cache at the same boundary.
        from .brand import cache_brand
        cache_brand(request.env)
        return super()._pre_dispatch(rule, args)

    @classmethod
    def _biz_paused_door(cls, rule):
        if request.httprequest.path in ('/tenant/identity/logo', '/tenant/identity/favicon', '/tenant/identity/icon512'):
            return
        return super()._biz_paused_door(rule)

    @api.model
    def _validate_tenant_identity(self, values):
        return clean_identity(values)

    @api.model
    def _tenant_identity(self):
        p = self.env['ir.config_parameter'].sudo()
        level = p.get_param('tenant.identity.level', 'product')
        product = p.get_param('tenant.identity.product') or p.get_param('biz_debranding.brand_name') or 'Carejiox'
        own = level in ('white', 'powered')
        company = self.env['res.company'].sudo().browse(1).exists() or self.env.company.sudo()
        name = (p.get_param('tenant.identity.name') or company.name) if own else product
        return {'level': level, 'name': name or 'Workspace', 'product': product,
                'website': p.get_param('tenant.identity.website') or company.website or p.get_param('web.base.url') or '',
                'color': p.get_param('tenant.identity.color') or '#1565C0',
                'logo': '/tenant/identity/logo' if own else '/health_pwa/static/icons/icon-192.png',
                'favicon': '/tenant/identity/favicon' if own else '/health_pwa/static/icons/icon-192.png',
                'powered': product if level == 'powered' else '', 'own': own}

    @api.model
    def _apply_tenant_identity(self, values=None):
        """Private: platform service or guarded company facade only."""
        p = self.env['ir.config_parameter'].sudo()
        for key, value in clean_identity(values or {}).items():
            p.set_param('tenant.identity.' + key, value or '')
        b = self._tenant_identity()
        for key, value in {
            'biz_debranding.brand_name': b['name'], 'biz_debranding.brand_website': b['website'],
            'biz_debranding.theme_color': b['color'], 'biz_debranding.product_name': b['product'] if b['own'] else '',
            'biz_debranding.powered_by': b['powered'], 'web_debranding.new_name': b['name'],
            'web_debranding.new_title': b['name'], 'web_debranding.new_website': b['website'],
            'web_debranding.new_documentation_website': b['website'] + '/documentation/',
            'web.web_app_name': b['name'], 'health_pwa.theme_color': b['color'],
        }.items():
            p.set_param(key, value or '')
        if 'website' in self.env:
            self.env['website'].sudo().search([]).write({'name': b['name']})
        # Invalidate generated templates as well as the parameter cache.
        self.env.registry.clear_cache()
        from .brand import cache_brand
        cache_brand(self.env)
        return b

    def session_info(self):
        info = super().session_info()
        b = self._tenant_identity()
        info['tenant_identity'] = b
        info['biz_brand_name'] = b['name']
        return info


class Company(models.Model):
    _inherit = 'res.company'

    def write(self, values):
        result = super().write(values)
        if {'name', 'website', 'logo'} & set(values) and 1 in self.ids:
            p = self.env['ir.config_parameter'].sudo()
            if p.get_param('tenant.identity.level') in ('white', 'powered'):
                self.env['ir.http']._apply_tenant_identity()
        return result


class Settings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _biz_apply_brand(self):
        # Upgrades must preserve tenant logos and favicons. The old seeder
        # writes its generic image to every company and website.
        if self.env['ir.config_parameter'].sudo().get_param('tenant.identity.level'):
            self.env['ir.http']._apply_tenant_identity()
            return True
        return super()._biz_apply_brand()
