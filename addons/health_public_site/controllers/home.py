from datetime import date

from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website


def homepage_brand(database):
    """Database identity, never a visitor-supplied host or query parameter."""
    return {'carejiox': 'platform', 'hhh': 'client'}.get(database)


class CareJioxHomepage(Website):
    @http.route('/', auth='public', website=True, sitemap=True, multilang=False)
    def index(self, **kw):
        brand = homepage_brand(request.env.cr.dbname)
        if not brand:
            return super().index(**kw)
        # Public-page preference only: never change a staff member's app language.
        lang = 'en'
        if brand == 'client':
            chosen = kw.get('site_lang') or request.httprequest.cookies.get('cjx_site_lang')
            lang = chosen if chosen in ('en', 'vi') else 'vi'
        response = request.render('health_public_site.' + brand, {
            'lang': lang,
            'year': date.today().year,
            'origin': 'https://hhh.carejiox.com' if brand == 'client' else 'https://carejiox.com',
        })
        response.headers['Cache-Control'] = 'private, no-store'
        if brand == 'client' and kw.get('site_lang') in ('en', 'vi'):
            response.set_cookie('cjx_site_lang', lang, max_age=31536000,
                                secure=request.httprequest.is_secure, httponly=True,
                                samesite='Lax')
        return response
