#!/usr/bin/env python3
"""Generate addons/health_learn's data files from the prototype's content.

    python3 tools/gen_learn_data.py            # write
    python3 tools/gen_learn_data.py --check    # fail if writing would change anything

WHY A GENERATOR AND NOT HAND-TRANSCRIPTION
------------------------------------------
The prototype is the authoring surface: sub-second preview, both languages side
by side, and `check_contract.py` already guarding every product fact it asserts.
The module is the delivery surface. Two surfaces means a pipeline or a fork, and
a fork is the thing analysis §8 says kills content systems.

So: content is edited in docs/tutorial_crm/, generated into the addon, and
`--check` runs beside the tests. Hand-editing the generated XML is a build
failure rather than a silent divergence.

WHAT GOES WHERE
---------------
English lands in the XML (the msgid). Vietnamese lands in i18n/vi_VN.po (the
msgstr). That is the standard Odoo path and it is what lets a translator work
without touching a data file — while `translate=True` keeps arithmetic out of
their reach, because numbers live in non-translatable `value` columns.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PROTO))
ADDON = os.path.join(REPO, 'addons', 'health_learn')

# No "--" anywhere in this string: it is emitted inside an XML comment, where a
# double hyphen is illegal. (Caught by parsing every generated file.)
BANNER = ("GENERATED FILE. Do not edit.\n"
          "         Source: docs/tutorial_crm/ · Regenerate: "
          "python3 docs/tutorial_crm/tools/gen_learn_data.py\n"
          "         Hand edits are erased on the next run and fail the CI check.")

# station id -> the cms.sidebar.item xml-id it teaches. Verified against the
# sidebar data files; test_station_sidebar_link keeps it honest.
SIDEBAR_KEYS = {
    'dashboard':     'health_cms_sidebar.item_crm_dashboard',
    'carecommand':   'health_care_command.item_care_command',
    'contacts':      'health_cms_sidebar.item_crm_contacts',
    'activities':    'health_cms_sidebar.item_crm_activities',
    'unrouted':      'health_care_command_channels.item_contact_capture',
    'channelcenter': 'health_care_command_channels.item_channel_center',
    'touchpoints':   'health_web_leads.item_web_touchpoints',
    'leadanalysis':  'health_web_leads.item_lead_analysis',
}

# Which morph / chain each visual step pulls its rows from is declared in the
# content as moment.which / moment.chain; these just name the source tables.
MORPH_SRC, CHAIN_SRC = 'morphs', 'chains'


# --------------------------------------------------------------------- helpers
class Trans:
    """Collects msgid -> msgstr with their source references.

    gettext allows one entry per msgid, so identical English in two places must
    merge. A merge where the two Vietnamese strings DIFFER is a real content
    bug — the same sentence cannot mean two things — so it is reported rather
    than silently resolved.
    """

    def __init__(self):
        self.entries = {}   # msgid -> {'msgstr': str, 'refs': [str]}
        self.conflicts = []

    def add(self, model, field, xmlid, en, vi):
        en = (en or '').strip()
        vi = (vi or '').strip()
        if not en:
            return
        ref = 'model:%s,%s:health_learn.%s' % (model, field, xmlid)
        e = self.entries.setdefault(en, {'msgstr': vi, 'refs': []})
        e['refs'].append(ref)
        if vi and e['msgstr'] and vi != e['msgstr']:
            self.conflicts.append((en, e['msgstr'], vi, ref))
        elif vi and not e['msgstr']:
            e['msgstr'] = vi

    def render(self):
        out = [
            '# Translation of Odoo Server.',
            '# This file contains the translation of the following modules:',
            '# \t* health_learn',
            '#',
            '# GENERATED — see docs/tutorial_crm/tools/gen_learn_data.py',
            'msgid ""',
            'msgstr ""',
            '"Project-Id-Version: Odoo Server 19.0\\n"',
            '"Report-Msgid-Bugs-To: \\n"',
            '"Last-Translator: \\n"',
            '"Language-Team: \\n"',
            '"Language: vi\\n"',
            '"MIME-Version: 1.0\\n"',
            '"Content-Type: text/plain; charset=UTF-8\\n"',
            '"Content-Transfer-Encoding: 8bit\\n"',
            '"Plural-Forms: nplurals=1; plural=0;\\n"',
            '',
        ]
        for msgid in sorted(self.entries):
            e = self.entries[msgid]
            out.append('#. module: health_learn')
            for ref in sorted(set(e['refs'])):
                out.append('#: %s' % ref)
            out.append(_po_str('msgid', msgid))
            out.append(_po_str('msgstr', e['msgstr']))
            out.append('')
        return '\n'.join(out)


def _po_str(kw, s):
    """A .po literal. Multi-line strings use the empty-first-line form so the
    file stays readable and diffable at 100+ character lesson bodies."""
    esc = (s.replace('\\', '\\\\').replace('"', '\\"'))
    if '\n' not in esc and len(esc) < 90:
        return '%s "%s"' % (kw, esc)
    parts = esc.split('\n')
    lines = ['%s ""' % kw]
    for i, p in enumerate(parts):
        lines.append('"%s%s"' % (p, '\\n' if i < len(parts) - 1 else ''))
    return '\n'.join(lines)


def x(s):
    """XML-escape a field value."""
    return html.escape(s or '', quote=False)


def is_pair(v):
    return isinstance(v, dict) and set(v.keys()) == {'en', 'vi'}


def en_of(v):
    return v['en'] if is_pair(v) else (v if isinstance(v, str) else '')


def vi_of(v):
    return v['vi'] if is_pair(v) else (v if isinstance(v, str) else '')


class Xml:
    def __init__(self, title):
        self.lines = ['<?xml version="1.0" encoding="utf-8"?>',
                      '<!-- %s -->' % BANNER,
                      '<!-- %s -->' % title,
                      '<odoo>', '']

    def rec(self, model, xmlid, fields):
        self.lines.append('    <record id="%s" model="%s">' % (xmlid, model))
        for name, val in fields:
            if val is None or val == '':
                continue
            if isinstance(val, bool):
                self.lines.append('        <field name="%s" eval="%s"/>' % (name, val))
            elif isinstance(val, int):
                self.lines.append('        <field name="%s">%d</field>' % (name, val))
            elif isinstance(val, tuple) and val[0] == 'ref':
                self.lines.append('        <field name="%s" ref="%s"/>' % (name, val[1]))
            elif isinstance(val, tuple) and val[0] == 'eval':
                self.lines.append('        <field name="%s" eval="%s"/>' % (name, val[1]))
            else:
                self.lines.append('        <field name="%s">%s</field>' % (name, x(val)))
        self.lines.append('    </record>')
        self.lines.append('')

    def render(self):
        return '\n'.join(self.lines + ['</odoo>', ''])


# ---------------------------------------------------------------- flatteners
def flatten_chrome(en_tree, vi_tree, prefix=''):
    """I18N -> {dotted key: (en, vi)}."""
    out = {}
    for k, v in en_tree.items():
        key = '%s%s' % (prefix, k)
        w = (vi_tree or {}).get(k)
        if is_pair(v):
            out[key] = (en_of(v), vi_of(w) if is_pair(w) else en_of(v))
        elif isinstance(v, dict):
            out.update(flatten_chrome(v, w if isinstance(w, dict) else {}, key + '.'))
        elif isinstance(v, str):
            out[key] = (v, w if isinstance(w, str) else v)
    return out


# ------------------------------------------------------------------ generators
def gen_strings(data, tr):
    chrome = flatten_chrome(data['i18n']['en'], data['i18n']['vi'])
    doc = Xml('UI chrome. Both languages reach the browser so the learner can '
              'switch live, mid-lesson, without losing their place.')
    for key in sorted(chrome):
        en, vi = chrome[key]
        if not en:
            continue
        xmlid = 'str_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')
        doc.rec('learn.string', xmlid, [('key', key), ('value', en)])
        tr.add('learn.string', 'value', xmlid, en, vi)
    return doc.render()


def gen_glossary(data, tr):
    doc = Xml('Glossary. One entry per term the CRM desk uses differently from '
              'ordinary Vietnamese or English.')
    for i, (key, val) in enumerate(data['glossary'].items()):
        # The prototype stores "Term — definition" as one string.
        en, vi = en_of(val), vi_of(val)
        term_en, _, def_en = en.partition('—')
        term_vi, _, def_vi = vi.partition('—')
        if not def_en:
            term_en, def_en = key, en
            term_vi, def_vi = key, vi
        xmlid = 'gloss_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')
        doc.rec('learn.glossary.term', xmlid, [
            ('key', key), ('sequence', (i + 1) * 10),
            ('term', term_en.strip()), ('definition', def_en.strip()),
        ])
        tr.add('learn.glossary.term', 'term', xmlid, term_en.strip(), term_vi.strip())
        tr.add('learn.glossary.term', 'definition', xmlid, def_en.strip(), def_vi.strip())
    return doc.render()


def _station_xmlid(sid):
    return 'station_' + re.sub(r'[^a-z0-9]+', '_', sid.lower()).strip('_')


def gen_stations(data, tr):
    doc = Xml('Stations — the nodes on the Guided Journey map.')
    lesson_of = {l['station']: l['id'] for l in data['lessons'].values()}
    seq = 0
    for line_key, line in data['stations'].items():
        for st in line['stations']:
            seq += 10
            sid = st['id']
            xmlid = _station_xmlid(sid)
            outline = st.get('outline') or {}
            kind = 'lesson' if sid in lesson_of else 'outline'
            doc.rec('learn.station', xmlid, [
                ('key', sid),
                ('name', en_of(st['title'])),
                ('line', line_key),
                ('section', 'crm'),
                ('sequence', seq),
                ('summary', en_of(st.get('desc'))),
                ('icon', st.get('icon') or 'circle'),
                ('kind', kind),
                ('sidebar_key', SIDEBAR_KEYS.get(sid, '')),
                ('duration_min', st.get('mins') or 5),
                ('required', bool(st.get('required'))),
                ('star', bool(st.get('star'))),
                ('after_key', st.get('after') or ''),
                ('outline_what', en_of(outline.get('what'))),
                ('outline_why', en_of(outline.get('why'))),
                ('outline_when', en_of(outline.get('when'))),
                ('outline_prereq', en_of(outline.get('prereq'))),
            ])
            tr.add('learn.station', 'name', xmlid, en_of(st['title']), vi_of(st['title']))
            tr.add('learn.station', 'summary', xmlid, en_of(st.get('desc')), vi_of(st.get('desc')))
            for f in ('what', 'why', 'when', 'prereq'):
                tr.add('learn.station', 'outline_' + f, xmlid,
                       en_of(outline.get(f)), vi_of(outline.get(f)))
            for i, m in enumerate(outline.get('mistakes') or []):
                mid = '%s_mistake_%d' % (xmlid, i)
                doc.rec('learn.station.mistake', mid, [
                    ('station_id', ('ref', xmlid)),
                    ('sequence', (i + 1) * 10),
                    ('name', en_of(m)),
                ])
                tr.add('learn.station.mistake', 'name', mid, en_of(m), vi_of(m))
    return doc.render()


def _step_lines(step, data):
    """The rows a visual needs, as (role, label_pair, value) triples.

    ONLY morph. The calc breakdown and the lifecycle stepper are also drawn by
    the practice screens themselves, straight from the fixture — emitting them
    here as well would put one product fact under two owners, and the one that
    drifted would be the one nobody was watching. The fixture is where product
    facts live and where check_contract.py guards them; a lesson step just
    names which chain or which calc to show.

    Morph captions are different: they exist only inside a lesson, and they are
    consequence prose ("3 records changed, not 1") rather than a product fact.
    """
    moment = step.get('moment') or {}
    kind = moment.get('kind')
    rows = []
    if kind == 'morph':
        m = data[MORPH_SRC][moment['which']]
        # `value` carries an explicit kind marker rather than being inferred
        # from position or emptiness. A row shape you have to reconstruct from
        # ordering is one reorder away from rendering the delta as a heading.
        for role, side in (('morph_before', m['before']), ('morph_after', m['after'])):
            rows.append((role, side['h'], 'head|%s' % side['big']))
            rows.append((role, side['d'], 'detail'))
            if side.get('delta'):
                rows.append((role, side['delta'], 'delta'))
    return rows


def gen_lessons(data, tr):
    doc = Xml('Lessons, steps and understanding checks.')
    for lkey in sorted(data['lessons']):
        lesson = data['lessons'][lkey]
        lx = 'lesson_' + lkey.lower()
        station_x = _station_xmlid(lesson['station'])
        # A lesson's own name/goal are not authored separately in the
        # prototype — the station carries them. Reuse rather than invent.
        st = None
        for line in data['stations'].values():
            for s in line['stations']:
                if s['id'] == lesson['station']:
                    st = s
        doc.rec('learn.lesson', lx, [
            ('key', lkey),
            ('station_id', ('ref', station_x)),
            ('sequence', 10),
            ('name', en_of(st['title'])),
            ('goal', en_of(st.get('desc'))),
            ('duration_min', lesson.get('mins') or 5),
        ])
        tr.add('learn.lesson', 'name', lx, en_of(st['title']), vi_of(st['title']))
        tr.add('learn.lesson', 'goal', lx, en_of(st.get('desc')), vi_of(st.get('desc')))

        for i, step in enumerate(lesson['steps']):
            sx = '%s_step_%02d' % (lx, i)
            moment = step.get('moment') or {}
            doc.rec('learn.step', sx, [
                ('lesson_id', ('ref', lx)),
                ('sequence', (i + 1) * 10),
                ('kicker', en_of(step.get('kicker'))),
                ('title', en_of(step['title'])),
                ('body', en_of(step['body'])),
                ('tip', en_of(step.get('tip'))),
                ('consequence', en_of(step.get('consequence'))),
                ('screen', step['screen']),
                ('anchor', step.get('anchor') or ''),
                ('visual', moment.get('kind') or 'none'),
                ('moment_from', moment.get('from') or ''),
                ('moment_to', moment.get('to') or ''),
                ('moment_chain', moment.get('chain') or ''),
                ('moment_which', moment.get('which') or ''),
            ])
            for f in ('kicker', 'title', 'body', 'tip', 'consequence'):
                tr.add('learn.step', f, sx, en_of(step.get(f)), vi_of(step.get(f)))

            for j, (role, label, value) in enumerate(_step_lines(step, data)):
                lnx = '%s_line_%02d' % (sx, j)
                doc.rec('learn.step.line', lnx, [
                    ('step_id', ('ref', sx)),
                    ('sequence', (j + 1) * 10),
                    ('role', role),
                    ('label', en_of(label)),
                    ('value', value),
                ])
                tr.add('learn.step.line', 'label', lnx, en_of(label), vi_of(label))

        quiz = lesson.get('quiz')
        if quiz:
            qx = '%s_quiz' % lx
            doc.rec('learn.quiz', qx, [
                ('lesson_id', ('ref', lx)),
                ('sequence', 10),
                ('kind', 'choice'),
                ('prompt', en_of(quiz['question'])),
            ])
            tr.add('learn.quiz', 'prompt', qx, en_of(quiz['question']), vi_of(quiz['question']))
            for k, opt in enumerate(quiz['options']):
                ox = '%s_opt_%d' % (qx, k)
                doc.rec('learn.quiz.option', ox, [
                    ('quiz_id', ('ref', qx)),
                    ('sequence', (k + 1) * 10),
                    ('label', en_of(opt['text'])),
                    ('is_correct', bool(opt.get('correct'))),
                    ('feedback', en_of(opt['explanation'])),
                ])
                tr.add('learn.quiz.option', 'label', ox, en_of(opt['text']), vi_of(opt['text']))
                tr.add('learn.quiz.option', 'feedback', ox,
                       en_of(opt['explanation']), vi_of(opt['explanation']))
    return doc.render()


def _intent_xmlid(key):
    return 'intent_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')


def _screen_xmlid(key):
    return 'screen_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')


# The prototype's four role names, mapped onto capabilities the product can
# actually CHECK. This is the whole point of the Phase-2 capability model: a
# role name is a copy that drifts, a group membership is the thing itself.
ROLE_TO_CAPABILITY = {
    'nurse': 'no_access',   # the leaf is not in their sidebar
    'crm': 'operator',      # sees the screen, no CRM Manager group
    'om': 'manager',        # holds the CRM Manager permission
    'owner': 'owner',       # plus every catchment area
}

# Only screens WITHOUT a sidebar leaf need a manual tag here. Everything else
# reads its matchers from the leaf itself at bundle time — five of the eight CRM
# leaves are act_windows with no tag at all, so a hard-coded tag map silently
# failed to detect them.
SCREEN_ACTION_TAGS = {}


def gen_screens(data, tr):
    doc = Xml('Screens the Coach knows, with the questions it offers before '
              'anything is typed.')
    for i, (key, blurb) in enumerate(data['screenCtx'].items()):
        xmlid = _screen_xmlid(key)
        station = None
        for line in data['stations'].values():
            for s in line['stations']:
                if s['id'] == key:
                    station = s
        name = en_of(station['title']) if station else key
        suggest = data['qaSuggest'].get(key) or []
        doc.rec('learn.screen', xmlid, [
            ('key', key),
            ('sequence', (i + 1) * 10),
            ('name', name),
            ('blurb', en_of(blurb)),
            ('action_tags', SCREEN_ACTION_TAGS.get(key, '')),
            ('sidebar_key', SIDEBAR_KEYS.get(key, '')),
            ('suggest_ids', ('eval', '[(6, 0, [%s])]' % ', '.join(
                "ref('%s')" % _intent_xmlid(k) for k in suggest))),
        ])
        tr.add('learn.screen', 'name', xmlid, name,
               vi_of(station['title']) if station else name)
        tr.add('learn.screen', 'blurb', xmlid, en_of(blurb), vi_of(blurb))
        # "What should I do next here" is derived from the station's own
        # "when to use it" — the honest answer, already written and checked.
        if station:
            nxt = (station.get('outline') or {}).get('when')
            if nxt:
                tr.add('learn.screen', 'next_step', xmlid, en_of(nxt), vi_of(nxt))
    return doc.render()


def _blocks_of(intent):
    """(capability, blocks) pairs — one for a plain intent, four for a
    capability-aware one."""
    if intent.get('roleVariants'):
        return [(ROLE_TO_CAPABILITY[r], blocks)
                for r, blocks in intent['roleVariants'].items()
                if r in ROLE_TO_CAPABILITY]
    return [('any', intent.get('blocks') or [])]


BLOCK_KIND = {'calcKpi': 'calc_kpi'}


def gen_intents(data, tr):
    doc = Xml('Coach intents. Every answer the Coach can give is a block here; '
              'there is no path from a question to the screen that skips this '
              'file, which is what lets it promise never to invent a fact.')
    for intent in data['qa']:
        key = intent['id']
        xmlid = _intent_xmlid(key)
        screens = intent.get('screens')
        screens_csv = '*' if screens == '*' else ','.join(screens or [])
        doc.rec('learn.intent', xmlid, [
            ('key', key),
            ('label', en_of(intent['label'])),
            ('screens', screens_csv),
            ('dynamic', {'screenCtx': 'screen_blurb',
                         'nextStep': 'next_step'}.get(intent.get('dynamic'), 'none')),
            ('show_me', ','.join(intent.get('showMe') or [])),
            ('simpler', en_of(intent.get('simpler'))),
            ('practice_key', intent.get('practice') or ''),
            # A refusal stays reachable but is never advertised.
            ('offer', False if intent.get('offer') is False else True),
        ])
        tr.add('learn.intent', 'label', xmlid, en_of(intent['label']), vi_of(intent['label']))
        if intent.get('simpler'):
            tr.add('learn.intent', 'simpler', xmlid,
                   en_of(intent['simpler']), vi_of(intent['simpler']))

        # The label is ALWAYS a trigger phrase, in both languages. The
        # suggestion buttons submit the label verbatim, so a label that does
        # not resolve to its own intent is a dead button — and that is exactly
        # what six of them were, because a hand-written match list does not
        # reliably overlap the question it is offered as.
        phrases = list(intent.get('match') or [])
        for lab in (en_of(intent['label']), vi_of(intent['label'])):
            if lab and lab not in phrases:
                phrases.append(lab)

        for j, phrase in enumerate(phrases):
            doc.rec('learn.intent.phrase', '%s_p%02d' % (xmlid, j), [
                ('intent_id', ('ref', xmlid)),
                ('text', phrase),
            ])

        seq = 0
        for capability, blocks in _blocks_of(intent):
            for b in blocks:
                seq += 10
                bx = '%s_b%03d' % (xmlid, seq)
                kind = BLOCK_KIND.get(b['k'], b['k'])
                body = ''
                if kind != 'steps' and b.get('v') is not None:
                    body = en_of(b['v'])
                doc.rec('learn.intent.block', bx, [
                    ('intent_id', ('ref', xmlid)),
                    ('sequence', seq),
                    ('capability', capability),
                    ('kind', kind),
                    ('body', body),
                ])
                if body:
                    tr.add('learn.intent.block', 'body', bx, body, vi_of(b['v']))
                if kind == 'steps':
                    for k, st in enumerate(b['v']):
                        sx = '%s_s%02d' % (bx, k)
                        doc.rec('learn.intent.step', sx, [
                            ('block_id', ('ref', bx)),
                            ('sequence', (k + 1) * 10),
                            ('text', en_of(st['t'])),
                            ('anchor', st.get('a') or ''),
                        ])
                        tr.add('learn.intent.step', 'text', sx,
                               en_of(st['t']), vi_of(st['t']))
    return doc.render()


def _mission_xmlid(key):
    return 'mission_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')


# Which practice screen each mission opens on.
MISSION_SCREEN = {'m1': 'carecommand', 'm2': 'channelcenter',
                  'm3': 'contacts', 'm4': 'touchpoints'}


def gen_missions(data, tr):
    doc = Xml('Practice missions. These run on the REPLICA, never a live screen: '
              'a step that says "press Junk" would otherwise be a real spam flag '
              'on a real number.')
    steps_by_mission = {'m1': data['m1Steps'], 'm2': data['m2Steps']}

    for i, m in enumerate(data['missions']):
        key = m['id']
        xmlid = _mission_xmlid(key)
        full = bool(m.get('full'))
        conf = m.get('conf') or {}
        cons = m.get('consequence') or {}
        anom = m.get('anomaly') or {}
        fields_ = [
            ('key', key),
            ('sequence', (i + 1) * 10),
            ('line', m.get('group') or 'daily'),
            ('icon', m.get('icon') or 'flask'),
            ('name', en_of(m['title'])),
            ('summary', en_of(m.get('desc'))),
            ('duration_min', m.get('mins') or 5),
            ('kind', 'full' if full else 'outline'),
            ('outline_note', en_of(m.get('outlineNote'))),
            ('screen', MISSION_SCREEN.get(key, '')),
            ('confidence_key', conf.get('key') or ''),
            ('confidence_gain', conf.get('gain') or 10),
            ('consequence_title', en_of(cons.get('title'))),
            ('consequence_scope', en_of(cons.get('scope'))),
            ('consequence_reversible', en_of(cons.get('reversible'))),
            ('consequence_verify', en_of(cons.get('verify'))),
            ('anomaly_title', en_of(anom.get('title'))),
            ('anomaly_body', en_of(anom.get('body'))),
        ]
        doc.rec('learn.mission', xmlid, fields_)
        tr.add('learn.mission', 'name', xmlid, en_of(m['title']), vi_of(m['title']))
        tr.add('learn.mission', 'summary', xmlid, en_of(m.get('desc')), vi_of(m.get('desc')))
        tr.add('learn.mission', 'outline_note', xmlid,
               en_of(m.get('outlineNote')), vi_of(m.get('outlineNote')))
        for f, src in (('consequence_title', cons.get('title')),
                       ('consequence_scope', cons.get('scope')),
                       ('consequence_reversible', cons.get('reversible')),
                       ('consequence_verify', cons.get('verify')),
                       ('anomaly_title', anom.get('title')),
                       ('anomaly_body', anom.get('body'))):
            tr.add('learn.mission', f, xmlid, en_of(src), vi_of(src))

        for j, note_kind in (('did', 'did'), ('checklist', 'check')):
            for n, note in enumerate((m.get('debrief') or {}).get(j) or []):
                nx = '%s_%s_%02d' % (xmlid, note_kind, n)
                doc.rec('learn.mission.note', nx, [
                    ('mission_id', ('ref', xmlid)),
                    ('sequence', (n + 1) * 10),
                    ('kind', note_kind),
                    ('body', en_of(note)),
                ])
                tr.add('learn.mission.note', 'body', nx, en_of(note), vi_of(note))

        for k, st in enumerate(steps_by_mission.get(key) or []):
            sx = '%s_step_%02d' % (xmlid, k)
            doc.rec('learn.mission.step', sx, [
                ('mission_id', ('ref', xmlid)),
                ('sequence', (k + 1) * 10),
                ('key', st['id']),
                ('nav', st.get('nav') or ''),
                ('target', st.get('target') or ''),
                ('instruction', en_of(st['instruction'])),
                ('detail', en_of(st.get('detail'))),
                ('hint', en_of(st.get('hint'))),
                ('is_decision', bool(st.get('decision'))),
                ('is_consequence', bool(st.get('consequence'))),
                ('is_undo', bool(st.get('undo'))),
            ])
            for f in ('instruction', 'detail', 'hint'):
                tr.add('learn.mission.step', f, sx, en_of(st.get(f)), vi_of(st.get(f)))

            recovery = st.get('recovery') or {}
            for o, opt in enumerate(st.get('options') or []):
                ox = '%s_opt_%s' % (sx, opt['id'])
                rec = recovery.get(opt['id'])
                doc.rec('learn.mission.option', ox, [
                    ('step_id', ('ref', sx)),
                    ('sequence', (o + 1) * 10),
                    ('key', opt['id']),
                    ('label', en_of(opt['label'])),
                    ('is_correct', bool(opt.get('correct'))),
                    ('recovery', en_of(rec)),
                ])
                tr.add('learn.mission.option', 'label', ox,
                       en_of(opt['label']), vi_of(opt['label']))
                if rec:
                    tr.add('learn.mission.option', 'recovery', ox, en_of(rec), vi_of(rec))
    return doc.render()


def gen_columns(data, tr):
    doc = Xml('Column glossary. Written, not derived from ir.model.fields: '
              'measured on this database, only 126 of 239 crm.lead fields carry '
              'any help and the one a learner actually asked about has none.')
    for screen, cols in (data.get('columns') or {}).items():
        for i, (key, label, body) in enumerate(cols):
            xmlid = 'col_%s_%s' % (
                re.sub(r'[^a-z0-9]+', '_', screen.lower()).strip('_'),
                re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_'))
            doc.rec('learn.column', xmlid, [
                ('screen', screen),
                ('key', key),
                ('sequence', (i + 1) * 10),
                ('label', en_of(label)),
                ('body', en_of(body)),
            ])
            tr.add('learn.column', 'label', xmlid, en_of(label), vi_of(label))
            tr.add('learn.column', 'body', xmlid, en_of(body), vi_of(body))
    return doc.render()


def gen_overrides(data, tr):
    doc = Xml('Tenant slots — the shipped defaults. A key with no row here does '
              'not exist, so this file is also the declaration the override '
              'constraint validates against.')
    for key in sorted(data['tenantDefaults']):
        pair = data['tenantDefaults'][key]
        xmlid = 'slot_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')
        doc.rec('learn.tenant.override', xmlid, [
            ('key', key), ('value', en_of(pair)),
        ])
        tr.add('learn.tenant.override', 'value', xmlid, en_of(pair), vi_of(pair))
    return doc.render()


def gen_fixture(data):
    """The practice clinic, as an ES module.

    Stays a static asset and never becomes ORM rows (analysis §8): a fake
    patient that exists only in a JS file cannot be picked up by a report or
    included in an export.
    """
    src = open(os.path.join(PROTO, 'practice-data.js'), encoding='utf-8').read()
    header = ('/* %s */\n' % BANNER.replace('\n', '\n   ')
              + '/** @odoo-module **/\n\n')
    exports = ('\nexport { B, PRACTICE_META, CASE, PRACTICE, MENU, RETIRED,'
               ' STATUS_LABELS };\n')
    # TENANT_DEFAULTS / tenantValue are NOT exported: in the product the tokens
    # arrive resolved in the bundle, per company. Exporting the fixture's copy
    # would give the engine a second, always-wrong source.
    return header + src + exports


# ---------------------------------------------------------------------- driver
def dump():
    out = subprocess.run(
        ['node', os.path.join(HERE, 'dump_content.js')],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if regenerating would change any file')
    args = ap.parse_args()

    data = dump()
    tr = Trans()
    files = {
        'data/learn_strings.xml': gen_strings(data, tr),
        'data/learn_glossary.xml': gen_glossary(data, tr),
        'data/learn_stations.xml': gen_stations(data, tr),
        'data/learn_lessons.xml': gen_lessons(data, tr),
        'data/learn_tenant_slots.xml': gen_overrides(data, tr),
        'data/learn_intents.xml': gen_intents(data, tr),
        'data/learn_screens.xml': gen_screens(data, tr),
        'data/learn_columns.xml': gen_columns(data, tr),
        'data/learn_missions.xml': gen_missions(data, tr),
        'static/src/engine/fixture.js': gen_fixture(data),
    }
    files['i18n/vi_VN.po'] = tr.render()

    # Parse everything we are about to write. A generator that can emit
    # malformed XML will eventually emit malformed XML — the "--" inside an XML
    # comment that this caught the first time is exactly the class of bug that
    # otherwise surfaces as a module that will not install.
    for rel, content in files.items():
        if not rel.endswith('.xml'):
            continue
        try:
            ET.fromstring(content)
        except ET.ParseError as exc:
            print('MALFORMED: %s — %s' % (rel, exc))
            return 3

    if tr.conflicts:
        print('CONFLICT: the same English text has two Vietnamese translations.')
        for en, a, b, ref in tr.conflicts:
            print('  msgid : %s' % en[:80])
            print('    (a) %s\n    (b) %s\n    at  %s' % (a[:80], b[:80], ref))
        return 2

    changed = []
    for rel, content in files.items():
        path = os.path.join(ADDON, rel)
        old = None
        if os.path.exists(path):
            old = open(path, encoding='utf-8').read()
        if old == content:
            continue
        changed.append(rel)
        if not args.check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)

    if args.check:
        if changed:
            print('STALE: regenerating would change %d file(s):' % len(changed))
            for c in changed:
                print('  %s' % c)
            print('Run: python3 docs/tutorial_crm/tools/gen_learn_data.py')
            return 1
        print('✓ generated data is up to date (%d files)' % len(files))
        return 0

    print('wrote %d file(s), %d unchanged' % (len(changed), len(files) - len(changed)))
    for c in changed:
        print('  %s' % c)
    print('  %d translatable string(s) in vi_VN.po' % len(tr.entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
