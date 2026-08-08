# -*- coding: utf-8 -*-
"""The Care Coach's content and its resolver.

The Coach answers ONLY from stored blocks. There is no path from a question to
the screen that does not pass through a record an author wrote — which is what
lets it promise never to invent a price, a rate or a clinical fact.

The resolver is deterministic retrieval. `_resolve_hook` is the one seam where
an LLM can be plugged in later; note its contract, which is the whole point:
it returns an intent KEY chosen from the candidates, never text. The model may
choose what to say; it may not say it.
"""
import logging
import re
import unicodedata

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

# Words that carry no topic. Without this, "what dose of antibiotic should I
# give" matched "what does this page do" on the word "what" alone and the Coach
# answered a clinical question with a UI tour. Vietnamese entries are stored
# diacritic-folded, because that is how they arrive from _norm.
_STOP = {
    # English
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'am', 'do', 'does',
    'did', 'can', 'could', 'should', 'would', 'will', 'shall', 'may', 'might',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'this', 'that',
    'these', 'those', 'what', 'when', 'where', 'which', 'who', 'whom', 'how',
    'why', 'to', 'of', 'in', 'on', 'at', 'for', 'from', 'with', 'and', 'or',
    'not', 'if', 'then', 'so', 'here', 'there', 'get', 'got', 'have', 'has',
    'had', 'about', 'please', 'thing', 'things', 'one',
    # Vietnamese, folded
    'la', 'gi', 'nao', 'sao', 'the', 'nay', 'do', 'co', 'khong', 'toi', 'ban',
    'minh', 'cua', 'va', 'hay', 'thi', 'lam', 'duoc', 'cho', 'voi', 'tren',
    'trong', 'khi', 'nhu', 'de', 'bi', 'se', 'da', 'dang', 'mot', 'nhung',
    'nao', 'ai', 'dau', 'vi', 'ma', 'ra', 'len', 'xuong', 'phai',
    # 'bao nhieu' is Vietnamese for 'how much / how many'. Without it,
    # "lieu khang sinh la bao nhieu" (what dose of antibiotic) matched the
    # PRICE intent on the quantity word alone — a clinical question
    # answered with a billing refusal.
    'bao', 'nhieu', 'may',
}

# Clinical questions, refused BEFORE retrieval rather than scored against it.
#
# This is a safety boundary, not a matching problem. "vết thương có bị nhiễm
# trùng không" (is the wound infected) shares two real topic words with the
# consent intent, which is about whether you may DISCUSS a wound — so retrieval
# scored it as a hit and the Coach answered a clinical question with consent
# policy. Confidently off-target on a clinical system is the one failure mode
# worth spending a deny-list on.
#
# Stored diacritic-folded, matched against the folded question.
_CLINICAL_MARKERS = (
    # English
    'dose', 'dosage', 'antibiotic', 'blood pressure', 'infected', 'infection',
    'diagnos', 'symptom', 'prescri', 'medication', 'mg per', 'wound care plan',
    # Vietnamese, folded
    'lieu', 'khang sinh', 'huyet ap', 'nhiem trung', 'chan doan', 'trieu chung',
    'ke don', 'don thuoc', 'lieu luong',
)


def _is_clinical(question):
    nq = _norm(question)
    return any(m in nq for m in _CLINICAL_MARKERS)


_SCORE_FLOOR = 20
_ON_SCREEN_BONUS = 25


def _norm(text):
    """Lowercase, strip diacritics, fold đ, drop punctuation.

    Vietnamese is typed with and without tone marks depending on the keyboard
    and the hurry, so a matcher that needs the marks matches nothing when it is
    needed most.
    """
    s = (text or '').lower().replace('đ', 'd')
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\s]+', ' ', s).strip()


def _topic_words(text):
    return {w for w in _norm(text).split() if w and w not in _STOP and len(w) > 1}


class LearnScreen(models.Model):
    _name = 'learn.screen'
    _description = 'Learn screen'
    _order = 'sequence, key'

    key = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    blurb = fields.Text(translate=True, help="What this screen is, in one sentence.")
    next_step = fields.Text(
        translate=True,
        help="The honest answer to 'what should I do next here'.")
    action_tags = fields.Char(
        help="Optional manual override. Normally EMPTY: the matchers are read "
             "from the sidebar leaf named by sidebar_key, so the Coach and the "
             "sidebar can never disagree about which screen is showing.")
    sidebar_key = fields.Char(help="xml-id of the leaf, for the visibility check.")
    suggest_ids = fields.Many2many('learn.intent', string='Suggested questions')

    _sql_constraints = [('key_uniq', 'unique(key)', 'A screen key must be unique.')]

    def _matchers(self):
        """How to tell that THIS screen is the one on display.

        Read from the sidebar leaf rather than hard-coded here. Only three of
        the eight CRM leaves are client actions with a tag; the rest are
        act_windows identified by xml-id or model — so a tag-only map silently
        failed to detect five of eight screens, and the Coach told the learner
        it had no lessons for a screen it had a full lesson for.

        Reusing the leaf's own declaration means the Coach resolves the screen
        exactly the way the sidebar decides which leaf to highlight.
        """
        self.ensure_one()
        tags, xmlids, models_ = set(), set(), set()

        def split(val):
            return {v.strip() for v in (val or '').split(',') if v.strip()}

        tags |= split(self.action_tags)
        if self.sidebar_key:
            item = self.env.ref(self.sidebar_key, raise_if_not_found=False)
            if item:
                item = item.sudo()
                tags |= split(item.action_tag) | split(item.match_action_tags)
                xmlids |= split(item.action_xmlid) | split(item.match_action_xmlids)
                models_ |= split(item.match_models)
        return sorted(tags), sorted(xmlids), sorted(models_)


class LearnIntent(models.Model):
    _name = 'learn.intent'
    _description = 'Learn coach intent'
    _order = 'key'

    key = fields.Char(required=True, index=True)
    label = fields.Char(required=True, translate=True,
                        help="The question as a person would ask it.")
    screens = fields.Char(default='*',
                          help="'*' or a comma-separated list of learn.screen keys.")
    dynamic = fields.Selection(
        selection=lambda self: self._selection_dynamic(), default='none', required=True)
    show_me = fields.Char(help="Comma-separated anchor keys this answer can point at.")
    simpler = fields.Text(translate=True, help="The 'explain more simply' rewrite.")
    practice_key = fields.Char(help="A Phase-3 mission id. Inert until then.")
    active = fields.Boolean(default=True)
    offer = fields.Boolean(
        default=True,
        help="Show this as a suggested question. A refusal must stay REACHABLE "
             "but never advertised: offering 'ask me something clinical' invites "
             "exactly the question the Coach exists to decline.")
    phrase_ids = fields.One2many('learn.intent.phrase', 'intent_id')
    block_ids = fields.One2many('learn.intent.block', 'intent_id')

    _sql_constraints = [('key_uniq', 'unique(key)', 'An intent key must be unique.')]

    @api.model
    def _selection_dynamic(self):
        return [('none', self.env._('Static blocks')),
                ('screen_blurb', self.env._("The screen's own description")),
                ('next_step', self.env._('What to do next here'))]

    # ------------------------------------------------------------------
    def _covers_screen(self, screen_key):
        self.ensure_one()
        raw = (self.screens or '*').strip()
        if raw == '*':
            return True
        return screen_key in [s.strip() for s in raw.split(',') if s.strip()]

    # -------------------------------------------------------- the resolver
    @api.model
    def _score(self, question, intent, screen_key):
        """Exact > substring > reverse-substring > topic overlap."""
        nq = _norm(question)
        if not nq:
            return 0
        best = 0
        for phrase in intent.phrase_ids:
            np = _norm(phrase.text)
            if not np:
                continue
            if nq == np:
                best = max(best, 100)
            elif np in nq:
                best = max(best, 80)
            elif nq in np and len(nq) >= 6:
                best = max(best, 60)
        if best < 60:
            # Topic overlap, but never on one shared common word: that is how a
            # clinical question ends up answered with a UI tour.
            qw = _topic_words(question)
            for phrase in intent.phrase_ids:
                shared = qw & _topic_words(phrase.text)
                if len(shared) >= 2:
                    best = max(best, 55)
                elif len(shared) == 1 and len(next(iter(shared))) >= 6:
                    best = max(best, 40)
        if best and screen_key and intent._covers_screen(screen_key) \
                and (intent.screens or '*') != '*':
            best += _ON_SCREEN_BONUS
        return best

    @api.model
    def _resolve_hook(self, question, screen_key, candidates):
        """THE SEAM.

        Returns an intent key from `candidates`, or None. An LLM implementation
        replaces the body and keeps the contract: it may CHOOSE from the
        candidates, it may not author a reply. Everything the learner reads
        stays a block someone wrote and a test can check.
        """
        scored = [(self._score(question, i, screen_key), i.key) for i in candidates]
        scored = [s for s in scored if s[0] >= _SCORE_FLOOR]
        if not scored:
            return None
        scored.sort(key=lambda s: (-s[0], s[1]))
        return scored[0][1]

    @api.model
    def resolve(self, question, screen_key=None):
        # The clinical guard runs FIRST and does not go through scoring. A
        # deterministic refusal is the only acceptable behaviour here: a
        # retrieval score is a guess, and a guess about a patient's condition
        # is exactly what this system must never make.
        if _is_clinical(question):
            return 'clinical' if self.search_count([('key', '=', 'clinical')]) else None
        candidates = self.search([]).filtered(
            lambda i: not screen_key or i._covers_screen(screen_key))
        return self._resolve_hook(question, screen_key, candidates)


    # ------------------------------------------------------- capability
    @api.model
    def _capability(self, screen_key=None):
        """What this reader can actually do here.

        Read from the REAL gates — the sidebar's own visibility call and the
        real groups — never from a role name the tutorial keeps a copy of. If
        the CRM manager group is renamed or a leaf is re-gated, the Coach's
        answer changes with it, because it is asking the same question the
        product asks.
        """
        user = self.env.user
        if user.has_group('access_roles.access_role_group_administrator'):
            return 'owner'
        if screen_key:
            screen = self.env['learn.screen'].sudo().search(
                [('key', '=', screen_key)], limit=1)
            if screen and screen.sidebar_key:
                item = self.env.ref(screen.sidebar_key, raise_if_not_found=False)
                visible = self.env['learn.station']._visible_sidebar_item_ids()
                if not item or item.id not in visible:
                    return 'no_access'
        if user.has_group('health_crm.group_health_crm_manager'):
            return 'manager'
        return 'operator'

    # ------------------------------------------------------- answering
    def _answer_tree(self, capability, screen):
        """One language's worth of answer. Zipped by _answer below."""
        self.ensure_one()
        blocks = [b for b in self.block_ids
                  if b.capability in ('any', capability)]
        if not blocks and self.block_ids:
            # An intent with capability-specific blocks but none for this
            # reader would otherwise answer with silence. Say the most
            # restrictive thing we hold rather than nothing.
            blocks = [b for b in self.block_ids if b.capability == 'no_access']
        out = [b._block_dict() for b in blocks]
        if self.dynamic == 'screen_blurb' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': screen.blurb or '', 'steps': []})
        elif self.dynamic == 'next_step' and screen:
            out.insert(0, {'capability': 'any', 'kind': 'p',
                           'body': screen.next_step or '', 'steps': []})
        return {
            'key': self.key,
            'label': self.label,
            'simpler': self.simpler or '',
            'blocks': out,
        }

    @api.model
    def _answer(self, intent_key, screen_key):
        """The full bilingual answer payload for one intent."""
        from .learn_station import _zip_bilingual
        capability = self._capability(screen_key)

        def build(lang):
            env = self.with_context(lang=lang)
            intent = env.search([('key', '=', intent_key)], limit=1)
            if not intent:
                return None
            screen = env.env['learn.screen'].sudo().search(
                [('key', '=', screen_key)], limit=1) if screen_key else None
            return intent._answer_tree(capability, screen)

        en, vi = build('en_US'), build('vi_VN')
        if not en:
            return None
        payload = _zip_bilingual(en, vi)
        intent = self.search([('key', '=', intent_key)], limit=1)
        payload.update({
            'capability': capability,
            'show_me': [a.strip() for a in (intent.show_me or '').split(',') if a.strip()],
            'practice_key': intent.practice_key or '',
        })
        return payload

    @api.model
    def ask(self, question, screen_key=None):
        """The Coach's one entry point.

        Order matters. Curated intents first, then the column glossary, then
        the composer, then an honest miss — each fallback is strictly less
        certain than the one before it, so the most reliable answer always
        wins.
        """
        key = self.resolve(question, screen_key)
        if key:
            answer = self._answer(key, screen_key)
            if answer:
                answer['matched'] = True
                return answer

        # "What is Activity Date used for?" — a question about a COLUMN, not a
        # procedure. It was the single most obvious miss in review, and it is
        # deterministic: no model needed to look up a written definition.
        column = self.env['learn.column'].match(question, screen_key)
        if column:
            return self._column_answer(column, screen_key)

        composed = self._compose(question, screen_key)
        if composed:
            return composed

        return {
            'matched': False,
            'capability': self._capability(screen_key),
            'suggest': self._suggestions(screen_key),
        }



    # ==================================================================
    # THE COMPOSER — an LLM over OUR OWN CONTENT, and nothing else
    # ==================================================================
    # Retrieval answers a question it has an intent for. This answers a
    # question that no single intent covers, by composing from several pieces
    # of material we wrote.
    #
    # WHAT IS AND IS NOT SENT
    # -----------------------
    # Sent: the learner's question (scrubbed, see _scrub) and our own tutorial
    # text for the screen they are on. NOT sent: any patient, contact, booking
    # or invoice record. The corpus is the material in this module, so there is
    # no PHI in the request regardless of which provider is configured.
    #
    # The question itself is user-typed, so it is scrubbed first: someone can
    # type a patient's name into a help box, and that would otherwise travel to
    # a hosted provider.
    #
    # SOFT DEPENDENCY on purpose. hr_development_ai owns the provider
    # abstraction (`hr.ai.provider.config`, llama / mistral / openai). Declaring
    # a hard dependency would make the Coach uninstallable without it and would
    # be a second provider registry to keep in step. If it is absent or nothing
    # is configured, the composer is simply unavailable and the Coach falls
    # back to the honest miss it gave before.

    # Anything that looks like it identifies a person or a record. Scrubbed
    # from the question before it leaves this server.
    _SCRUB = [
        (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'), '[email]'),
        (re.compile(r'(?:\+?84|0)\d[\d\s.-]{7,}\d'), '[phone]'),
        (re.compile(r'#\d{2,}'), '[record]'),
        (re.compile(r'\b\d{6,}\b'), '[number]'),
    ]

    @api.model
    def _scrub(self, question):
        """Remove record-shaped references before the question leaves us."""
        out = question or ''
        for pattern, replacement in self._SCRUB:
            out = pattern.sub(replacement, out)
        return out[:400]

    @api.model
    def _provider(self):
        """The configured provider, or None. Never raises."""
        if 'hr.ai.provider.config' not in self.env:
            return None
        try:
            config = self.env['hr.ai.provider.config'].sudo().search(
                [('company_id', '=', self.env.company.id), ('is_active', '=', True)],
                limit=1)
            if not config:
                return None
            from odoo.addons.hr_development_ai.ai_providers.provider_factory import (
                AIProviderFactory)
            return AIProviderFactory.get_provider(env=self.env,
                                                  company_id=self.env.company.id)
        except Exception:
            _logger.info("Learn coach: no usable AI provider", exc_info=True)
            return None

    @api.model
    def _corpus(self, screen_key, lang):
        """Everything we have written about this screen, as plain text."""
        env = self.with_context(lang=lang)
        parts = []
        screen = env.env['learn.screen'].sudo().search(
            [('key', '=', screen_key)], limit=1) if screen_key else None
        if screen:
            parts.append('SCREEN: %s — %s' % (screen.name, screen.blurb or ''))
            station = env.env['learn.station'].sudo().search(
                [('key', '=', screen_key)], limit=1)
            for lesson in station.lesson_ids:
                for step in lesson.step_ids:
                    parts.append('- %s: %s' % (step.title, (step.body or '')))
            for col in env.env['learn.column'].sudo().search(
                    [('screen', '=', screen_key)]):
                parts.append('COLUMN %s: %s' % (col.label, col.body))
        for intent in env.search([]).filtered(
                lambda i: not screen_key or i._covers_screen(screen_key)):
            for block in intent.block_ids:
                if block.capability in ('any',) and block.body:
                    parts.append('%s: %s' % (intent.label, block.body))
        text = '\n'.join(parts)
        return text[:12000]

    @api.model
    def _compose(self, question, screen_key):
        """Compose an answer from our own material, or return None.

        Returns None on ANY doubt — no provider, no corpus, an empty or
        suspiciously long reply. The honest miss is always an acceptable
        outcome; a fluent invention is not.
        """
        provider = self._provider()
        if not provider:
            return None
        corpus = self._corpus(screen_key, 'en_US')
        if not corpus.strip():
            return None
        scrubbed = self._scrub(question)
        prompt = (
            "You are a help assistant inside a healthcare CRM. Answer the "
            "question USING ONLY the material below. If the material does not "
            "contain the answer, reply with exactly: NO_ANSWER.\n"
            "Never invent a price, a rate, a clinical fact or a number that is "
            "not in the material. Never claim to have performed an action. "
            "Answer in at most four sentences, plainly.\n\n"
            "MATERIAL:\n%s\n\nQUESTION: %s\nANSWER:" % (corpus, scrubbed))
        try:
            reply = provider.generate_text(prompt, max_tokens=300, temperature=0.2)
        except Exception:
            _logger.info("Learn coach: composer call failed", exc_info=True)
            return None
        reply = (reply or '').strip()
        if not reply or 'NO_ANSWER' in reply or len(reply) > 1500:
            return None

        from .learn_station import _zip_bilingual
        tree = {
            'key': 'composed',
            'label': self._scrub(question),
            'simpler': '',
            'blocks': [
                {'capability': 'any', 'kind': 'p', 'body': reply, 'steps': []},
            ],
        }
        payload = _zip_bilingual(tree, tree)
        payload.update({
            'matched': True,
            'capability': self._capability(screen_key),
            'show_me': [],
            'practice_key': '',
            # Flagged so the drawer can say so. A composed answer is written by
            # a model FROM our material — the learner is entitled to know which
            # kind of answer they are reading.
            'source_kind': 'composed',
        })
        return payload

    @api.model
    def _column_answer(self, column, screen_key):
        """A column definition, shaped like any other answer."""
        from .learn_station import _zip_bilingual

        def build(lang):
            col = column.with_context(lang=lang)
            return {
                'key': 'column:%s' % col.key,
                'label': col.label,
                'simpler': '',
                'blocks': [
                    {'capability': 'any', 'kind': 'p', 'body': col.body, 'steps': []},
                    {'capability': 'any', 'kind': 'source', 'steps': [],
                     'body': col.env['learn.screen'].sudo().search(
                         [('key', '=', screen_key)], limit=1).name or screen_key},
                ],
            }

        payload = _zip_bilingual(build('en_US'), build('vi_VN'))
        payload.update({'matched': True, 'capability': self._capability(screen_key),
                        'show_me': [], 'practice_key': '', 'source_kind': 'column'})
        return payload

    @api.model
    def _suggestions(self, screen_key):
        """What the Coach can answer here, named. A bare "I don't know" tells
        the learner nothing about where to go next."""
        from .learn_station import _zip_bilingual
        screen = self.env['learn.screen'].sudo().search(
            [('key', '=', screen_key)], limit=1) if screen_key else None

        def build(lang):
            env = self.with_context(lang=lang)
            if screen:
                intents = env.browse(screen.suggest_ids.ids)
            else:
                intents = env.search(
                    [('screens', '=', '*'), ('offer', '=', True)], limit=6)
            return [{'key': i.key, 'label': i.label} for i in intents]

        return _zip_bilingual(build('en_US'), build('vi_VN'))

    @api.model
    def coach_bundle(self):
        """Screens + suggestions, both languages, fetched once per session so
        the drawer opens instantly rather than after a round-trip."""
        from .learn_station import _zip_bilingual

        def build(lang):
            env = self.env['learn.screen'].with_context(lang=lang).sudo()
            return {
                'screens': [{
                    'key': s.key,
                    'name': s.name,
                    'blurb': s.blurb or '',
                    'next_step': s.next_step or '',
                    'action_tags': s._matchers()[0],
                    'action_xmlids': s._matchers()[1],
                    'models': s._matchers()[2],
                    'suggest': [{'key': i.key, 'label': i.label} for i in s.suggest_ids],
                } for s in env.search([])],
                # What the Coach can answer ANYWHERE. Without this, a screen it
                # does not cover is a dead end: an honest "no lessons here yet"
                # and then nothing at all, which leaves the stuck person exactly
                # as stuck.
                'global_suggest': [
                    {'key': i.key, 'label': i.label}
                    for i in self.with_context(lang=lang).search(
                        [('screens', '=', '*'), ('offer', '=', True)],
                        order='key', limit=6)
                ],
            }

        bundle = _zip_bilingual(build('en_US'), build('vi_VN'))
        bundle['tokens'] = self.env['learn.tenant.override'].resolved_tokens()
        bundle['chrome'] = self.env['learn.station']._content_bundle()['chrome']
        return bundle


class LearnIntentPhrase(models.Model):
    """A trigger phrase.

    NOT translatable, deliberately: the prototype's match lists mix English and
    Vietnamese in one bag, which is correct. A learner types in whichever
    language they are thinking in — often mid-shift, often without tone marks —
    and both have to hit the same intent.
    """
    _name = 'learn.intent.phrase'
    _description = 'Learn coach trigger phrase'
    _order = 'intent_id, id'

    intent_id = fields.Many2one('learn.intent', required=True, ondelete='cascade')
    text = fields.Char(required=True)


class LearnIntentBlock(models.Model):
    _name = 'learn.intent.block'
    _description = 'Learn coach answer block'
    _order = 'sequence, id'

    intent_id = fields.Many2one('learn.intent', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    capability = fields.Selection(
        selection=lambda self: self._selection_capability(),
        default='any', required=True,
        help="Which reader this block is for. Read from the REAL gates, not "
             "from a role name the tutorial keeps its own copy of.")
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(), required=True, default='p')
    body = fields.Text(translate=True)
    step_ids = fields.One2many('learn.intent.step', 'block_id')

    @api.model
    def _selection_capability(self):
        return [
            ('any', self.env._('Everyone')),
            ('no_access', self.env._('Cannot see this screen')),
            ('operator', self.env._('Can use the screen')),
            ('manager', self.env._('CRM Manager')),
            ('owner', self.env._('Owner / administrator')),
        ]

    @api.model
    def _selection_kind(self):
        return [
            ('p', self.env._('Paragraph')),
            ('steps', self.env._('Numbered steps')),
            ('calc', self.env._('Urgency breakdown')),
            ('calc_kpi', self.env._('Conversion breakdown')),
            ('ok', self.env._('Confirmation')),
            ('warn', self.env._('Caution')),
            ('refusal', self.env._('Your role cannot do this')),
            ('who', self.env._('Who can')),
            ('how', self.env._('How to get access')),
            ('source', self.env._('Grounded in')),
        ]

    def _block_dict(self):
        self.ensure_one()
        return {
            'capability': self.capability,
            'kind': self.kind,
            'body': self.body or '',
            'steps': [{'text': s.text, 'anchor': s.anchor or ''} for s in self.step_ids],
        }


class LearnIntentStep(models.Model):
    _name = 'learn.intent.step'
    _description = 'Learn coach answer step'
    _order = 'sequence, id'

    block_id = fields.Many2one('learn.intent.block', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    text = fields.Text(required=True, translate=True)
    anchor = fields.Char(help="Anchor key to point at. Must be in anchors.json.")


class LearnColumn(models.Model):
    """What a column on a screen actually means.

    WHY THIS IS CURATED AND NOT READ FROM ir.model.fields
    ----------------------------------------------------
    Measured on this database before writing a line of it: of 239 fields on
    crm.lead, only 126 carry any help text at all, and most of what exists is
    Odoo's own boilerplate ("Icon to indicate an exception activity"). The
    field a learner actually asked about — activity_date_deadline — has the
    label "Next Activity Deadline" and NO help.

    So a schema-driven answer would restate the column header back at the
    person who just read it. What answers "what is activity date used for?" is
    domain knowledge: it is the next scheduled follow-up, the Activities board
    is where it comes from, and on a pivot it tells you whether a lead is being
    worked or has gone quiet. That has to be written.
    """
    _name = 'learn.column'
    _description = 'Learn screen column'
    _order = 'screen, sequence, id'

    screen = fields.Char(required=True, index=True)
    key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True, translate=True,
                        help="The column header exactly as it appears on screen.")
    body = fields.Text(required=True, translate=True,
                       help="One honest sentence: what it is for, and what it is not.")

    _sql_constraints = [
        ('screen_key_uniq', 'unique(screen, key)', 'One entry per column per screen.'),
    ]

    @api.model
    def match(self, question, screen_key):
        """Find the column a question is asking about.

        Deliberately narrow: the question must contain the column's label (or
        its label must contain the question's topic words). A loose match here
        would answer "what is the status of my request" with a column
        definition, which is worse than missing.
        """
        if not screen_key:
            return None
        nq = _norm(question)
        if not nq:
            return None
        best, best_len = None, 0
        for col in self.search([('screen', '=', screen_key)]):
            for lang in ('en_US', 'vi_VN'):
                label = _norm(col.with_context(lang=lang).label)
                if label and len(label) > 3 and label in nq and len(label) > best_len:
                    best, best_len = col, len(label)
        return best

    def _column_dict(self):
        self.ensure_one()
        return {'key': self.key, 'label': self.label, 'body': self.body}
