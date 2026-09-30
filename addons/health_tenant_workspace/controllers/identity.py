import base64
import json
from io import BytesIO
from PIL import Image, ImageDraw
from odoo import http
from odoo.http import request
from odoo.addons.health_pwa.controllers.pwa import HealthPWAController
from odoo.addons.mail.controllers.webmanifest import WebManifest

class TenantIdentity(http.Controller):
    @http.route('/tenant/identity/<kind>', type='http', auth='public', methods=['GET'])
    def identity_image(self, kind, **kw):
        if kind not in ('logo', 'favicon', 'icon512'):
            return request.not_found()
        p = request.env['ir.config_parameter'].sudo()
        size = 512 if kind == 'icon512' else 192
        raw = p.get_param('tenant.identity.'+('favicon' if kind == 'icon512' else kind))
        if not raw and kind in ('favicon', 'icon512'):
            raw = p.get_param('tenant.identity.logo')
        if not raw and p.get_param('tenant.identity.company_logo_custom'):
            company = request.env['res.company'].sudo().browse(1)
            raw = company.logo if company.exists() and company.logo else None
        if raw:
            data = base64.b64decode(raw)
            if kind in ('favicon', 'icon512'):
                original = Image.open(BytesIO(data)).convert('RGBA')
                original.thumbnail((size, size))
                icon = Image.new('RGBA', (size, size))
                icon.alpha_composite(original, ((size-original.width)//2, (size-original.height)//2))
                output = BytesIO(); icon.save(output, 'PNG'); data = output.getvalue()
        else:
            b = request.env['ir.http']._tenant_identity()
            im = Image.new('RGB',(size,size),b['color'])
            # ASCII fallback is safe with Pillow's built-in bitmap font.
            initial = b['name'][:1].upper()
            ImageDraw.Draw(im).text((size//2-4,size//2-6), initial if initial.isascii() else '+', fill='white')
            buf=BytesIO();im.save(buf,'PNG');data=buf.getvalue()
        return request.make_response(data, [('Content-Type','image/png'),('Cache-Control','no-cache'),('X-Content-Type-Options','nosniff')])

class TenantPWA(HealthPWAController):
    @http.route()
    def pwa_manifest(self, **kwargs):
        response = super().pwa_manifest(**kwargs)
        b = request.env['ir.http']._tenant_identity()
        manifest = json.loads(response.get_data())
        manifest.update(name=b['name'], short_name=b['name'], theme_color=b['color'])
        if b['own']:
            manifest['icons'] = identity_icons()
        response.set_data(json.dumps(manifest))
        response.headers['Cache-Control'] = 'no-cache'
        return response


    @http.route()
    def service_worker(self, **kwargs):
        response = super().service_worker(**kwargs)
        brand = request.env['ir.http']._tenant_identity()
        if brand['own']:
            # Replace the three authored fallback notification titles. Keep
            # user-supplied notification titles and payloads unchanged.
            response.set_data(response.get_data(as_text=True).replace("'Viet Uc Care'", json.dumps(brand['name'])))
        return response

def identity_icons():
    return [{'src':'/tenant/identity/'+kind,'sizes':f'{size}x{size}','type':'image/png','purpose':'any'} for kind,size in [('favicon',192),('icon512',512)]]


class TenantWebManifest(WebManifest):
    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        brand = request.env['ir.http']._tenant_identity()
        manifest.update(name=brand['name'], short_name=brand['name'], theme_color=brand['color'])
        if brand['own']:
            manifest.update(icons=identity_icons(), background_color='#ffffff')
        return manifest
