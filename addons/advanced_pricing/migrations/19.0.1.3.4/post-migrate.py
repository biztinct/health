# -*- coding: utf-8 -*-
"""UAT round 10, item 6 — the "Post-service price recalculated" notes that were
posted as plain text show "<br/>", "<ul><li>" literally. Rebuild exactly those
notes (quote and booking copies) as HTML; no other message is touched.

A note is rewritten only when its escaped tail parses as the shape the old code
produced (<br/>Applied rules:<ul><li><b>…</b> …</li>…</ul>); the rule words
are escaped again on the way back in.
"""
import html
import logging
import re

from markupsafe import Markup

_logger = logging.getLogger(__name__)

HEADS = ('Post-service price recalculated', 'Đã tính lại giá sau dịch vụ')
TAIL = re.compile(r'^<br/>(?P<title>[^<>]*)<ul>(?P<items>(?:<li><b>[^<>]*</b> [^<>]*</li>)*)</ul>$')
ITEM = re.compile(r'<li><b>(?P<desc>[^<>]*)</b> (?P<label>[^<>]*)</li>')


def rebuild(body):
    """The fixed body, or None when this is not one of the broken notes."""
    text = body or ''
    if text.startswith('<span>') and text.endswith('</span>'):
        text = text[len('<span>'):-len('</span>')]
    if not text.startswith(HEADS) or '&lt;br/&gt;' not in text:
        return None
    head, _sep, tail = text.partition('&lt;br/&gt;')
    tail = html.unescape('<br/>' + tail.replace('&lt;br/&gt;', '<br/>'))
    match = TAIL.match(tail)
    if not match or '<' in head:
        return None
    items = Markup().join(
        Markup('<li><b>%s</b> %s</li>') % (m['desc'], m['label'])
        for m in ITEM.finditer(match['items']))
    return str(Markup(head) + Markup('<br/>%s<ul>%s</ul>') % (match['title'], items))


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT id, body FROM mail_message
         WHERE body LIKE %s
           AND (body LIKE %s OR body LIKE %s)""",
               ('%&lt;br/&gt;%', '%Post-service price recalculated%',
                '%Đã tính lại giá sau dịch vụ%'))
    fixed = []
    for msg_id, body in cr.fetchall():
        new = rebuild(body)
        if new and new != body:
            cr.execute('UPDATE mail_message SET body = %s WHERE id = %s',
                       (new, msg_id))
            fixed.append(msg_id)
    _logger.info('advanced_pricing 19.0.1.3.4: rebuilt %s post-service price '
                 'note(s) as HTML: %s', len(fixed), fixed)
