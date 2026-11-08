"""Authenticated media and printable manuals. No public training attachments."""
import html
from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class LearningController(http.Controller):
    @http.route('/carejiyo/learn/media/<string:key>/<string:kind>', type='http', auth='user', readonly=True)
    def media(self, key, kind, **kw):
        path = request.env['learn.task']._media_path(key, kind)
        if not path:
            raise NotFound()
        stream = http.Stream.from_path(path)
        stream.mimetype = 'video/mp4' if kind == 'mp4' else 'text/vtt'
        response = stream.get_response()
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @http.route('/carejiyo/learn/manual', type='http', auth='user', readonly=True)
    def manual(self, key=None, section=None, **kw):
        tasks = request.env['learn.task']._allowed()
        if key:
            tasks = [request.env['learn.task']._task(key)]
        elif section:
            tasks = [t for t in tasks if str(t['section']) == section]
        if not tasks:
            raise NotFound()
        e = html.escape
        parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
                 '<title>CareJiyo User Manual</title><style>body{font:16px/1.7 sans-serif;color:#19394a;max-width:900px;margin:40px auto;padding:0 24px}h1,h2{line-height:1.2}h2{margin-top:40px}li{margin:12px 0}article{border-top:1px solid #ddd;padding:24px 0}a{color:#08786e}button{padding:10px 16px}aside{padding:12px;border-left:3px solid #bc852e}nav{columns:2} @media(max-width:600px){body{margin:16px auto;padding:0 14px}nav{columns:1}h1{font-size:25px}} @media print{button,.video{display:none}article{break-before:page}li{break-inside:avoid}h2,h3{break-after:avoid}}video::cue{font-size:16px;background:rgba(15,40,48,.88);color:white}@page{size:A4;margin:18mm}</style>',
                 '<button onclick="window.print()">Print or save as PDF</button><h1>CareJiyo user manual</h1>',
                 '<p>Find your task below. Read what you need first, follow the steps and check the result. Use your own staff account and work within your assigned role and catchment.</p>']
        sections = ['Getting started and enquiries', 'Bookings and operations', 'Mobile visits',
                    'Invoices and payments', 'Users and administration', 'Worked examples']
        if not key and not section:
            parts.append('<p>Open a shorter volume: ' + ' · '.join(
                '<a href="?section=%s">%s</a>' % (i, e(name))
                for i, name in enumerate(sections, 1) if any(t['section'] == i for t in tasks)) + '</p>')
        parts.append('<nav><ul>')
        for t in tasks:
            parts.append('<li><a href="#%s">%s</a></li>' % (e(t['key']), e(t['title'])))
        parts.append('</ul></nav>')
        for t in tasks:
            parts.append('<article id="%s"><h2>%s</h2><p>%s</p><p><b>Who uses this:</b> %s</p><h3>Before you begin</h3><p>%s</p>' % (e(t['key']), e(t['title']), e(t['goal']), e(t['role']), e(t['before'])))
            if t['warning']:
                parts.append('<aside>%s</aside>' % e(t['warning']))
            parts.append('<h3>Steps</h3><ol>'+''.join('<li>%s</li>' % e(s) for s in t['steps'])+'</ol>')
            parts.append('<h3>Check the result</h3><p>%s</p><h3>If something is wrong</h3><p>%s</p>' % (e(t['success']), e(t['trouble'])))
            if request.env['learn.task']._media_path(t['key']):
                url = '/carejiyo/learn/media/' + e(t['key']) + '/'
                parts.append('<div class="video"><h3>Watch the walkthrough</h3><video controls playsinline preload="none" style="width:100%%" poster="/health_learn/static/src/library/poster.svg" src="%smp4"><track kind="subtitles" srclang="en" label="English" default src="%sen.vtt"><track kind="subtitles" srclang="vi" label="Tiếng Việt" src="%svi.vtt"></video></div>' % (url, url, url))
            parts.append('</article>')
        parts.append('<footer>CareJiyo user manual</footer></html>')
        return request.make_response(''.join(parts), headers=[('Content-Type', 'text/html; charset=utf-8'), ('Cache-Control','private, no-store'), ('X-Content-Type-Options','nosniff')])
