# -*- coding: utf-8 -*-
from markupsafe import escape

from odoo import http
from odoo.http import request


_CONTACT_EMAIL = 'ash@biztinct.com'
_OPERATOR = 'Carejiox'
_EFFECTIVE_DATE = '14 September 2026'


def _page(title, body):
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="index,follow">
  <title>{escape(title)} | Carejiox</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, Arial, sans-serif; color: #17213d; }}
    body {{ margin: 0; background: #f5f7fb; line-height: 1.65; }}
    main {{ max-width: 820px; margin: 48px auto; padding: 40px; background: white;
            border: 1px solid #e1e6f0; border-radius: 16px; box-shadow: 0 8px 30px #17213d12; }}
    h1 {{ margin-top: 0; font-size: 2rem; line-height: 1.25; }}
    h2 {{ margin-top: 2rem; font-size: 1.2rem; }}
    a {{ color: #2546c7; }}
    .meta {{ color: #667085; }}
    @media (max-width: 700px) {{ main {{ margin: 0; padding: 24px; border-radius: 0; }} }}
  </style>
</head>
<body><main>{body}</main></body>
</html>"""
    return request.make_response(html, headers=[
        ('Content-Type', 'text/html; charset=utf-8'),
        ('X-Content-Type-Options', 'nosniff'),
        ('Cache-Control', 'public, max-age=3600'),
    ])


class CarejioxLegal(http.Controller):

    @http.route('/privacy-policy', type='http', auth='public', website=False,
                sitemap=True, methods=['GET'])
    def privacy_policy(self, **_kwargs):
        body = f"""
<h1>Carejiox Privacy Policy</h1>
<p class="meta">Effective date: {_EFFECTIVE_DATE}</p>
<p>Carejiox operates the Carejiox platform. This policy explains how Carejiox
processes information when an organisation connects a Facebook Page or another
communications channel to Care Command.</p>
<h2>Information we process</h2>
<p>When a Facebook Page administrator authorises the integration, Carejiox may
receive the Page name and identifier, the administrator's authorisation grant,
Page access tokens, and permissions approved through Meta. When people contact
the connected Page, Carejiox may receive their public profile name and
identifier, messages, public comments and replies, attachments, stickers,
timestamps, post or conversation identifiers, and delivery status.</p>
<h2>How we use information</h2>
<p>We use this information to show Page messages and public comments in Care
Command, allow authorised staff to respond, route and assign conversations,
create or update a lead or client record at an authorised user's request,
maintain an audit trail, prevent duplicate delivery, diagnose connection
failures, and protect the service. Carejiox does not sell personal information
or use Facebook data for advertising.</p>
<h2>Sharing and service providers</h2>
<p>Information is available to the organisation that controls the connected
Page and its authorised Carejiox users. We may use contracted hosting, security,
monitoring, and support providers only to operate and protect the service. We
may disclose information when required by law or to protect users and the
service. Meta processes information under its own terms and policies.</p>
<h2>Storage, security, and retention</h2>
<p>Carejiox uses access controls, encrypted transport, protected credentials,
and operational logging. Channel data is kept while the customer account needs
it for communication, care operations, audit, or legal obligations. It is then
deleted or de-identified according to the customer's instructions and
applicable law. Disconnecting a Page stops new collection but does not
automatically erase records the organisation must retain.</p>
<h2>Your choices and rights</h2>
<p>You may ask the organisation operating the Facebook Page to access, correct,
or delete information associated with your conversation. You may also request
deletion directly from Carejiox using our
<a href="/facebook-data-deletion">Facebook Data Deletion instructions</a>.
Page administrators can disconnect the Page in Channel Center or remove the
Carejiox app from Facebook.</p>
<h2>International processing and children</h2>
<p>Information may be processed where Carejiox and its service providers
operate, subject to appropriate safeguards. Carejiox is a business
communications service and is not directed to children.</p>
<h2>Changes and contact</h2>
<p>We may update this policy when the service or legal requirements change and
will publish the revised effective date here. For privacy questions or requests,
contact <a href="mailto:{_CONTACT_EMAIL}">{_CONTACT_EMAIL}</a>.</p>
<p>{_OPERATOR} · <a href="https://carejiox.com/">carejiox.com</a></p>
"""
        return _page('Privacy Policy', body)

    @http.route('/facebook-data-deletion', type='http', auth='public',
                website=False, sitemap=True, methods=['GET'])
    def facebook_data_deletion(self, **_kwargs):
        body = f"""
<h1>Carejiox Facebook Data Deletion</h1>
<p class="meta">{_OPERATOR}</p>
<p>You can request deletion of information Carejiox received through Facebook.</p>
<h2>How to request deletion</h2>
<ol>
  <li>Email <a href="mailto:{_CONTACT_EMAIL}?subject=Carejiox%20Facebook%20data%20deletion">{_CONTACT_EMAIL}</a>
      with the subject <strong>Carejiox Facebook data deletion</strong>.</li>
  <li>Include your Facebook profile name, the name of the Facebook Page you
      contacted, and enough detail to locate the conversation or comment.
      Do not send your Facebook password or access token.</li>
  <li>We may ask for limited information to verify the request and prevent the
      deletion of another person's records.</li>
</ol>
<p>We will acknowledge the request and delete or de-identify the applicable
Facebook data unless retention is required by law, security, fraud prevention,
or the connected organisation's lawful recordkeeping obligations. We will
explain any required retention in our response.</p>
<h2>Remove the app from Facebook</h2>
<p>A Facebook user can also open Facebook Settings, choose <strong>Apps and
websites</strong>, select Carejiox, and remove it. A Page administrator can
disconnect the Page from Carejiox Channel Center. Removing or disconnecting the
app stops future access; use the email process above to request deletion of
previously received records.</p>
<p>For more information, read the <a href="/privacy-policy">Carejiox Privacy
Policy</a>.</p>
<p>{_OPERATOR} · <a href="https://carejiox.com/">carejiox.com</a></p>
"""
        return _page('Facebook Data Deletion', body)
