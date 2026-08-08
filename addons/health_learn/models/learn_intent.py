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
import re
import unicodedata

from odoo import api, fields, models, tools

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
        help="Comma-separated product action tags that resolve to this screen. "
             "Data rather than a hard-coded map, so a new tag is a data change.")
    sidebar_key = fields.Char(help="xml-id of the leaf, for the visibility check.")
    suggest_ids = fields.Many2many('learn.intent', string='Suggested questions')

    _sql_constraints = [('key_uniq', 'unique(key)', 'A screen key must be unique.')]


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

        Returns an answer, or a fallback that NAMES what it can answer here.
        Never free text: everything the learner reads is a stored block.
        """
        key = self.resolve(question, screen_key)
        if key:
            answer = self._answer(key, screen_key)
            if answer:
                answer['matched'] = True
                return answer
        return {
            'matched': False,
            'capability': self._capability(screen_key),
            'suggest': self._suggestions(screen_key),
        }

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
                    'action_tags': [t.strip() for t in (s.action_tags or '').split(',') if t.strip()],
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
