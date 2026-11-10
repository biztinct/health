"""CareJiyo "Book a demo" intake (platform database only).

A visitor's request becomes a `crm.lead` (type lead, Sales team, tag
"CareJiyo demo request", source carejiyo.com) and a queued email to the
CareJiyo inbox. The email is queued, not sent inline: outgoing mail may be
switched off, and a visitor must never wait on, or see, a mail failure.

Spam rails, cheapest first: a hidden honeypot field, a minimum fill time,
same-email replays within 10 minutes answered "ok" without a second lead, and
a global hourly cap. Nothing here echoes visitor input back as HTML.
"""
import logging
import re
import time
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

from .home import homepage_brand

_logger = logging.getLogger(__name__)

INBOX = 'hello@carejiyo.com'
TAG_NAME = 'CareJiyo demo request'
SOURCE_NAME = 'carejiyo.com'
CARE_TYPES = {
    'home': 'Home care',
    'clinic': 'Clinic',
    'both': 'Home care and clinic',
    'other': 'Something else',
}
EMAIL_RE = re.compile(r'^[^@\s<>]+@[^@\s<>]+\.[A-Za-z]{2,}$')
PHONE_RE = re.compile(r'^[0-9+()\-.\s]{6,30}$')
MIN_FILL_SECONDS = 3
HOURLY_CAP = 40


def _clean(value, limit):
    return ' '.join((value or '').split())[:limit]


def validate_demo_request(post):
    """Return (data, errors). Errors map field -> plain-English message."""
    data = {
        'name': _clean(post.get('name'), 80),
        'email': _clean(post.get('email'), 120).lower(),
        'phone': _clean(post.get('phone'), 30),
        'organisation': _clean(post.get('organisation'), 120),
        'care_type': post.get('care_type') if post.get('care_type') in CARE_TYPES else '',
        'message': (post.get('message') or '').strip()[:1000],
    }
    errors = {}
    if len(data['name']) < 2:
        errors['name'] = 'Please add your name.'
    if not EMAIL_RE.match(data['email']):
        errors['email'] = 'Please add a valid email address.'
    if data['phone'] and not PHONE_RE.match(data['phone']):
        errors['phone'] = 'Please check the phone number.'
    if len(data['organisation']) < 2:
        errors['organisation'] = 'Please add your organisation’s name.'
    return data, errors


class CareJiyoDemoRequest(http.Controller):

    @http.route('/carejiyo/demo-request', type='http', auth='public', methods=['POST'],
                csrf=True, website=True, sitemap=False, readonly=False)
    def demo_request(self, **post):
        if homepage_brand(request.env.cr.dbname) != 'platform':
            return request.not_found()

        def reply(payload, status=200):
            response = request.make_json_response(payload, status=status)
            response.headers['Cache-Control'] = 'no-store'
            return response

        # Bots fill every field and submit instantly; people do neither.
        if (post.get('company_website') or '').strip():
            return reply({'ok': True})
        try:
            started = float(post.get('started') or 0) / 1000.0
        except ValueError:
            started = 0
        if started and time.time() - started < MIN_FILL_SECONDS:
            return reply({'ok': True})

        data, errors = validate_demo_request(post)
        if errors:
            return reply({'ok': False, 'errors': errors}, status=400)

        env = request.env(su=True)
        Lead = env['crm.lead'].with_context(mail_create_nolog=True, tracking_disable=True)
        tag = env['crm.tag'].search([('name', '=', TAG_NAME)], limit=1) \
            or env['crm.tag'].create({'name': TAG_NAME})

        now = fields.Datetime.now()
        recent = Lead.search_count([
            ('tag_ids', 'in', tag.ids), ('email_from', '=ilike', data['email']),
            ('create_date', '>=', now - timedelta(minutes=10)),
        ])
        if recent:
            return reply({'ok': True})
        if Lead.search_count([('tag_ids', 'in', tag.ids),
                              ('create_date', '>=', now - timedelta(hours=1))]) >= HOURLY_CAP:
            _logger.warning('CareJiyo demo intake: hourly cap reached, request refused')
            return reply({'ok': False, 'errors': {
                'form': 'We are receiving a lot of requests right now. Please email %s instead.' % INBOX,
            }}, status=429)

        lead = self._create_lead(env, Lead, tag, data)
        self._queue_email(env, lead, data)
        return reply({'ok': True})

    @staticmethod
    def _summary(data):
        rows = [
            ('Name', data['name']),
            ('Email', data['email']),
            ('Phone', data['phone'] or '—'),
            ('Organisation', data['organisation']),
            ('Type of care', CARE_TYPES.get(data['care_type'], '—')),
            ('Message', data['message'] or '—'),
        ]
        body = Markup('').join(
            Markup('<tr><td style="padding:4px 12px 4px 0;color:#4C5A72;vertical-align:top">%s</td>'
                   '<td style="padding:4px 0;white-space:pre-wrap">%s</td></tr>') % (label, value)
            for label, value in rows)
        return Markup('<table>%s</table>') % body

    def _create_lead(self, env, Lead, tag, data):
        source = env['utm.source'].search([('name', '=', SOURCE_NAME)], limit=1) \
            or env['utm.source'].create({'name': SOURCE_NAME})
        medium = env.ref('utm.utm_medium_website', raise_if_not_found=False)
        team = env.ref('sales_team.team_sales_department', raise_if_not_found=False)
        vals = {
            'name': 'Demo request: %s' % data['organisation'],
            'type': 'lead',
            'contact_name': data['name'],
            'partner_name': data['organisation'],
            'email_from': data['email'],
            'description': Markup('<p>Demo request from the carejiyo.com website.</p>') + self._summary(data),
            'tag_ids': [(6, 0, tag.ids)],
            'source_id': source.id,
            'medium_id': medium.id if medium else False,
            'team_id': team.id if team else False,
        }
        # The CRM accepts only local phone formats; an overseas number stays in
        # the description rather than costing the visitor their request.
        if data['phone']:
            try:
                with env.cr.savepoint():
                    return Lead.create(dict(vals, phone=data['phone']))
            except ValidationError:
                pass
        return Lead.create(vals)

    def _queue_email(self, env, lead, data):
        try:
            with env.cr.savepoint():
                env['mail.mail'].create({
                    'subject': 'New demo request: %s' % data['organisation'],
                    'email_to': INBOX,
                    'email_from': 'CareJiyo website <%s>' % INBOX,
                    'reply_to': data['email'],
                    'body_html': Markup(
                        '<p>A new demo request came in from carejiyo.com. It is saved as a lead '
                        'in the system.</p>') + self._summary(data),
                    'model': 'crm.lead',
                    'res_id': lead.id,
                    'auto_delete': False,
                })
        except Exception:  # the lead is what matters; never fail the visitor on mail
            _logger.exception('CareJiyo demo intake: could not queue the notification email')
