# -*- coding: utf-8 -*-
"""
BFSI Coaching Flow — orchestration API for the OWL guided coaching wizard.

One model, three RPC entry points that power the end-to-end manager journey
(Diagnose -> Strategy -> Session -> Action Plan) without the user ever leaving
the wizard or touching a raw backend form:

    coaching_get_context(banker_id)   -> data for steps 1 & 2 (diagnosis + strategy)
    coaching_ai_enhance(banker_id, s) -> optional richer AI text for a section
    coaching_commit(banker_id, vals)  -> creates strategy + session + action plan

Everything is data-driven from KPIs vs targets so the wizard is always fast and
works even when no AI provider is configured; AI only *enhances* on demand.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import json
import logging
import re

_logger = logging.getLogger(__name__)

# emoji & pictograph ranges — project rule: SVG icons only, never emoji.
# Stored AI content from before that rule still carries them; payloads are
# scrubbed at render time so old data displays clean everywhere.
_EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF'
    '\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF\U0000FE0F\U00002190-\U000021FF'
    '\U00002700-\U000027BF\U0001F300-\U0001F5FF]+'
)


def _strip_emoji(text):
    if not text:
        return text
    return _EMOJI_RE.sub('', str(text)).replace('  ', ' ')

# Avatar colours keyed by banker_type (kept in sync with the dashboard palette)
_TYPE_COLOR = {
    'wealth_manager': '#EF4444',
    'loan_officer': '#F59E0B',
    'rm': '#3B82F6',
    'telesales': '#1E40AF',
    'field_sales': '#3B82F6',
    'insurance_advisor': '#14B8A6',
    'banker': '#3B82F6',
}
_ROLE_LABEL = {
    'rm': 'Relationship Manager', 'branch_manager': 'Branch Manager',
    'regional_manager': 'Regional Manager', 'telesales': 'Telesales Agent',
    'field_sales': 'Field Sales Officer', 'loan_officer': 'Loan Officer',
    'insurance_advisor': 'Insurance Advisor', 'wealth_manager': 'Wealth Manager',
    'banker': 'Banker',
}


class BFSICoachingFlow(models.AbstractModel):
    _name = 'bfsi.coaching.flow'
    _description = 'BFSI Guided Coaching Flow API'

    # ════════════════════════════════════════════════════════════════
    #  STEP 1 + 2 — diagnosis & strategy in a single fast call
    # ════════════════════════════════════════════════════════════════
    @api.model
    def coaching_get_context(self, banker_id):
        emp = self.env['hr.employee'].sudo().browse(int(banker_id))
        if not emp.exists():
            return {'error': 'Banker not found'}

        KPI = self.env['bfsi.performance.kpi'].sudo()
        snap = self.env['bfsi.scoring'].employee_snapshot(emp.id)
        latest = KPI.browse(snap['kpi_id']) if snap['kpi_id'] else KPI
        target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(emp.id)

        rev_target = (target.target_revenue if target else 0) or 0
        rev = latest.revenue or 0 if latest else 0
        rev_pct = round(rev / rev_target * 100) if rev_target else 0

        bars, strengths, gaps = self._build_kpi_bars(latest, target)
        root_cause = self._build_root_cause(emp, latest, gaps)
        strategy = self._build_strategy(gaps)

        # ── one active strategy per banker: reuse it while it's current ──
        Scoring = self.env['bfsi.scoring']
        existing = self.env['bfsi.coaching.strategy'].sudo().search([
            ('banker_id', '=', emp.id),
            ('state', 'in', ['generated', 'reviewed', 'in_use']),
        ], order='create_date desc', limit=1)
        # "fresh" = no newer KPI data has arrived since the strategy was built
        is_fresh = bool(existing) and (
            not latest
            or (existing.kpi_snapshot_date
                and existing.kpi_snapshot_date >= latest.period_date))
        existing_payload = False
        if existing:
            existing_payload = {
                'id': existing.id,
                'date': Scoring.fmt_date(existing.kpi_snapshot_date or existing.create_date),
                'confidence': round(existing.ai_confidence or 0),
                'is_fresh': is_fresh,
            }
            if is_fresh:
                # serve the STORED playbook so the wizard shows the real strategy
                strategy = {
                    'themes': _split_lines(existing.coaching_themes) or strategy['themes'],
                    'opening': _split_lines(existing.opening_questions) or strategy['opening'],
                    'probing': _split_lines(existing.probing_questions) or strategy['probing'],
                    'closing': _split_lines(existing.closing_questions) or strategy['closing'],
                    'tips': _split_lines(existing.coaching_tips) or strategy['tips'],
                    'items': strategy['items'],
                }

        return {
            'existing_strategy': existing_payload,
            'banker': {
                'id': emp.id,
                'name': emp.name,
                'role': self._role(emp),
                'initial': (emp.name or '?').strip()[:1].upper(),
                'color': _TYPE_COLOR.get(emp.banker_type, '#3B82F6'),
                'score': snap['score'],
                'rank': snap['rank'],
                'move': snap['movement'],
                'rev_pct': rev_pct,
                'branch': emp.branch_id.name if emp.branch_id else '',
                'priority': snap['priority'],
            },
            'trend': snap['trend'],
            'bars': bars,
            'strengths': strengths or ['Shows up consistently', 'Engaged in the role'],
            'gaps': gaps_list(gaps) or ['Needs more performance data to pinpoint gaps'],
            'root_cause': root_cause,
            'confidence': 88 if (latest and target) else 60,
            'themes': strategy['themes'],
            'opening': strategy['opening'],
            'probing': strategy['probing'],
            'closing': strategy['closing'],
            'tips': strategy['tips'],
            'suggested_items': strategy['items'],
            'has_ai': self._ai_available(),
            'has_data': bool(latest),
        }

    # ── KPI vs target bars + strengths/gaps ──────────────────────────
    def _build_kpi_bars(self, kpi, target):
        if not kpi:
            return [], [], []
        # (label, category, value, target, gap_phrase, strength_phrase)
        specs = [
            ('Dials/hour', 'input', kpi.dials_per_hour,
             getattr(target, 'target_dials_per_hour', 0) if target else 0,
             'Activity too low — not enough conversations',
             'Strong call activity'),
            ('Objection handling', 'beh', kpi.objection_handling_score,
             getattr(target, 'target_objection_handling', 75) if target else 75,
             'Losing deals when clients push back',
             'Handles objections well'),
            ('Conversion rate', 'out', kpi.conversion_rate,
             getattr(target, 'target_conversion_rate', 18) if target else 18,
             'Conversations not turning into sales',
             'Converts opportunities efficiently'),
            ('Script adherence', 'beh', kpi.script_adherence,
             getattr(target, 'target_script_adherence', 80) if target else 80,
             'Drifting from the proven script',
             'Disciplined on the script'),
            ('Need analysis', 'beh', kpi.need_analysis_quality,
             getattr(target, 'target_need_analysis', 75) if target else 75,
             'Proposing before understanding the client',
             'Strong discovery / needs analysis'),
            ('Customer satisfaction', 'out', kpi.customer_satisfaction,
             getattr(target, 'target_customer_satisfaction', 85) if target else 85,
             'Clients not delighted',
             'Clients are highly satisfied'),
        ]
        bars, strengths, gaps = [], [], []
        for label, cat, val, tgt, gap_phrase, str_phrase in specs:
            val = round(val or 0, 1)
            tgt = round(tgt or 0, 1)
            if not tgt:
                continue
            below = val < tgt
            # extra keys (below/phrase/deficit) let the wizard show WHY each
            # talking point exists; existing consumers ignore them harmlessly
            bars.append({
                'name': label, 'cat': cat, 'value': val, 'target': tgt,
                'below': below,
                'phrase': gap_phrase if below else str_phrase,
                'deficit': round((tgt - val) / tgt * 100) if (tgt and below) else 0,
            })
            if not below:
                strengths.append('%s (%s vs %s target)' % (str_phrase, _fmt(val), _fmt(tgt)))
            else:
                gaps.append({
                    'label': label, 'cat': cat, 'value': val, 'target': tgt,
                    'phrase': gap_phrase,
                    'deficit': round((tgt - val) / tgt * 100) if tgt else 0,
                })
        # only keep the 4 most relevant bars (biggest gaps first, then strengths)
        bars.sort(key=lambda b: (b['value'] / b['target']) if b['target'] else 1)
        bars = bars[:4]
        gaps.sort(key=lambda g: g['deficit'], reverse=True)
        return bars, strengths[:3], gaps[:3]

    def _build_root_cause(self, emp, kpi, gaps):
        first = emp.name.split(' ')[0] if emp.name else 'This banker'
        if not kpi:
            return ("No recent KPI data for %s yet. Start with a baseline conversation "
                    "and set clear daily targets." % first)
        if not gaps:
            return ("%s is meeting targets across the board. Coaching here is about "
                    "stretch goals and keeping the momentum." % first)
        top = gaps[0]
        line = "%s's biggest gap is %s — %s (%s vs %s target, %s%% below). " % (
            first, top['label'].lower(), top['phrase'].lower(),
            _fmt(top['value']), _fmt(top['target']), top['deficit'])
        if len(gaps) > 1:
            line += "It compounds with %s. " % gaps[1]['label'].lower()
        line += "Focus the session on the one highest-leverage behaviour and lock a measurable commitment."
        return line

    # ── strategy (questions / themes / tips / suggested items) ───────
    def _build_strategy(self, gaps):
        top_cat = gaps[0]['cat'] if gaps else 'beh'
        top_label = gaps[0]['label'] if gaps else 'performance'
        themes = [g['label'] for g in gaps[:3]] or ['Consistency', 'Confidence']
        themes += ['Quick wins this week']

        opening = [
            "How do you feel your week went compared to where you wanted to be?",
            "What was your best client conversation — what made it work?",
            "Where do you feel you're losing momentum right now?",
        ]
        probing = [
            "On %s you're below target — what's getting in the way?" % top_label.lower(),
            "Walk me through the last opportunity you lost. What happened?",
            "If we fixed just ONE thing this week, what would move the needle most?",
        ]
        closing = [
            "What's one specific technique you'll try on your next 3 clients?",
            "What number can you commit to this week — realistic but a stretch?",
            "How do you want me to check in with you?",
        ]
        tips = [
            "Anchor every commitment to a number and a date — avoid 'try harder'.",
            "Build on a strength first, then tackle the gap.",
            "Have them say the commitment out loud — verbal commitments stick.",
        ]
        items = self._suggested_items(gaps)
        return {'themes': themes, 'opening': opening, 'probing': probing,
                'closing': closing, 'tips': tips, 'items': items}

    def _suggested_items(self, gaps):
        # map gap category -> a concrete, KPI-linked action item
        recipe = {
            'Objection handling': ('Use "feel-felt-found" on every price objection',
                                   'behavior', 'objection_handling'),
            'Dials/hour': ('Hit the daily dial target, logged each day',
                           'input', 'dials'),
            'Conversion rate': ('Shadow the branch top performer on 2 closing calls',
                                'output', 'conversion'),
            'Script adherence': ('Re-certify on the call script this week',
                                 'behavior', 'script_adherence'),
            'Need analysis': ('Run a full discovery before any proposal',
                              'behavior', 'need_analysis'),
            'Customer satisfaction': ('Follow up every client within 24h',
                                      'output', 'customer_satisfaction'),
        }
        items = []
        for g in gaps[:3]:
            title, cat, kpi = recipe.get(g['label'],
                                         ('Improve %s' % g['label'].lower(), 'behavior', 'other'))
            items.append({
                'title': title, 'kpi_category': cat, 'specific_kpi': kpi,
                'kpi_label': g['label'],
                'from_val': _fmt(g['value']), 'to_val': _fmt(g['target']),
                'target_value': g['target'],
            })
        if not items:
            items.append({'title': 'Set a baseline goal and review next week',
                          'kpi_category': 'outcome', 'specific_kpi': 'other',
                          'kpi_label': 'Overall', 'from_val': '', 'to_val': '',
                          'target_value': 0})
        return items

    # ════════════════════════════════════════════════════════════════
    #  COACHING QUEUE — ranked "who needs me now + why" for the home
    # ════════════════════════════════════════════════════════════════
    @api.model
    def coaching_queue(self, branch_id=None):
        """Return bankers ranked by coaching priority, each with a one-line
        AI 'why' and whether they already have an active plan."""
        if not branch_id:
            emp = self.env.user.employee_id
            branch_id = emp.branch_id.id if emp and emp.branch_id else None
        if not branch_id:
            return {'rows': []}

        branch = self.env['bfsi.branch'].sudo().browse(int(branch_id))
        KPI = self.env['bfsi.performance.kpi'].sudo()
        Plan = self.env['bfsi.action.plan'].sudo()
        Scoring = self.env['bfsi.scoring']
        prio_rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

        rows = []
        # only front-line bankers are coaching targets, never managers
        targets = branch.banker_ids.filtered(
            lambda e: e.active and e.banker_type not in ('branch_manager', 'regional_manager')
        )
        for banker in targets:
            snap = Scoring.employee_snapshot(banker.id)
            latest = KPI.browse(snap['kpi_id']) if snap['kpi_id'] else KPI
            target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(banker.id)
            _bars, _str, gaps = self._build_kpi_bars(latest, target)
            score = snap['score']
            prio = snap['priority']
            move = snap['movement']
            rank = snap['rank']

            # one-line "why"
            if gaps:
                why = "Root cause: %s" % gaps[0]['label'].lower()
            elif move > 0:
                why = "Improving (+%d ranks) — reinforce what's working" % move
            elif score >= 50:
                why = "On track — coach to stretch & mentor"
            else:
                why = "Below branch average — needs a plan"

            active_plans = Plan.search_count([
                ('employee_id', '=', banker.id),
                ('state', 'in', ['committed', 'in_progress']),
            ])

            rows.append({
                'id': banker.id,
                'name': banker.name,
                'role': self._role(banker),
                'initial': (banker.name or '?').strip()[:1].upper(),
                'color': _TYPE_COLOR.get(banker.banker_type, '#3B82F6'),
                'score': score,
                'kpi_id': snap['kpi_id'],
                'trend': snap['trend'],
                'rank': rank,
                'move': move,
                'priority': prio,
                'priority_label': {'critical': 'Critical', 'high': 'High',
                                   'medium': 'Medium', 'low': 'On track'}.get(prio, prio),
                'why': why,
                'active_plans': active_plans,
                'being_coached': active_plans > 0,
                'needs_coaching': prio in ('critical', 'high'),
            })

        rows.sort(key=lambda r: (prio_rank.get(r['priority'], 9), r['score']))
        return {'rows': rows, 'branch_name': branch.name}

    # ════════════════════════════════════════════════════════════════
    #  Optional AI enhancement for a section (lazy, on demand)
    # ════════════════════════════════════════════════════════════════
    @api.model
    def coaching_ai_enhance(self, banker_id, section):
        if not self._ai_available():
            return {'ok': False, 'text': ''}
        emp = self.env['hr.employee'].sudo().browse(int(banker_id))
        try:
            from ..ai_providers.provider_factory import get_ai_provider
            provider = get_ai_provider(self.env)
            ctx = emp.get_performance_context_for_ai()
            prompt = (
                "You are an expert bank sales coach. Based on this performance "
                "context, write a concise, specific %s (3-4 sentences, no preamble):\n%s"
                % (section.replace('_', ' '), json.dumps(ctx, default=str)[:1800])
            )
            text = provider.generate_text(prompt, max_tokens=260, temperature=0.6)
            return {'ok': True, 'text': text}
        except Exception as e:  # noqa: BLE001
            _logger.warning('coaching_ai_enhance failed: %s', e)
            return {'ok': False, 'text': ''}

    # ════════════════════════════════════════════════════════════════
    #  STEP 3 + 4 — commit the whole flow atomically
    # ════════════════════════════════════════════════════════════════
    @api.model
    def coaching_commit(self, banker_id, vals):
        emp = self.env['hr.employee'].sudo().browse(int(banker_id))
        if not emp.exists():
            raise UserError(_('Banker not found.'))
        vals = vals or {}

        manager = (emp.branch_id.manager_id if emp.branch_id and emp.branch_id.manager_id
                   else self.env.user.employee_id)
        today = fields.Date.today()
        freq = vals.get('check_in', 'weekly')
        horizon = {'daily': 7, 'weekly': 14, 'biweekly': 28, 'monthly': 30}.get(freq, 14)
        target_date = today + timedelta(days=horizon)

        # 1) the strategy: REUSE the banker's active strategy when the wizard
        #    confirmed it's still current — one active playbook per banker.
        #    Only build a new record when none exists / it went stale, and
        #    archive whatever it supersedes so duplicates can't pile up.
        Strategy = self.env['bfsi.coaching.strategy'].sudo()
        strategy = None
        reuse_id = vals.get('strategy_id')
        if reuse_id:
            candidate = Strategy.browse(int(reuse_id))
            if (candidate.exists() and candidate.banker_id.id == emp.id
                    and candidate.state in ('generated', 'reviewed', 'in_use')):
                strategy = candidate
                strategy.write({'state': 'in_use'})
                # exactly ONE active strategy per banker — archive the rest
                Strategy.search([
                    ('banker_id', '=', emp.id),
                    ('state', 'in', ['generated', 'reviewed', 'in_use']),
                    ('id', '!=', strategy.id),
                ]).write({'state': 'archived'})

        if not strategy:
            # supersede: whatever was active is now history
            Strategy.search([
                ('banker_id', '=', emp.id),
                ('state', 'in', ['generated', 'reviewed', 'in_use']),
            ]).write({'state': 'archived'})

            KPI = self.env['bfsi.performance.kpi'].sudo()
            snap = self.env['bfsi.scoring'].employee_snapshot(emp.id)
            latest = KPI.browse(snap['kpi_id']) if snap['kpi_id'] else KPI
            target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(emp.id)
            _bars, strengths, gaps = self._build_kpi_bars(latest, target)
            root_cause = self._build_root_cause(emp, latest, gaps)
            strategy = Strategy.create({
                'banker_id': emp.id,
                'manager_id': manager.id if manager else False,
                'state': 'in_use',
                'coaching_themes': _join(vals.get('themes')),
                'opening_questions': _join(vals.get('opening')),
                'probing_questions': _join(vals.get('probing')),
                'closing_questions': _join(vals.get('closing')),
                'performance_kpi_id': latest.id or False,
                'kpi_snapshot_date': latest.period_date if latest else today,
                'root_cause_analysis': _to_html(root_cause),
                'strengths': _join(strengths),
                'improvement_areas': _join(gaps_list(gaps)),
                'ai_confidence': 88 if (latest and target) else 60,
                'generation_date': fields.Datetime.now(),
            })

        # 2) coaching session (already conducted in the wizard)
        session = self.env['hr.coaching.session'].sudo().create({
            'name': _('Coaching: %s') % emp.name,
            'employee_id': emp.id,
            'coach_id': manager.id if manager else False,
            'session_type': 'hybrid',
            'topic': 'performance',
            'state': 'completed',
            'is_bfsi_session': True,
            'discussion_notes': _to_html(vals.get('notes')),
            'outcome': vals.get('outcome') or 'moderate',
            'employee_satisfaction': vals.get('satisfaction') or False,
            'coaching_strategy_id': strategy.id,
            'coached_by_type': 'ai_assisted',
        })

        # 3) action plan with KPI-linked items
        item_cmds = []
        for it in (vals.get('action_items') or []):
            item_cmds.append((0, 0, {
                'name': it.get('title') or 'Action item',
                'kpi_category': it.get('kpi_category') or 'behavior',
                'specific_kpi': it.get('specific_kpi') or 'other',
                'target_value': it.get('target_value') or 0,
                'target_end_date': target_date,
                'priority': it.get('priority') or 'high',
                'weight': 1.0,
            }))
        plan = self.env['bfsi.action.plan'].sudo().create({
            'employee_id': emp.id,
            'manager_id': manager.id if manager else False,
            'coaching_session_id': session.id,
            'commitment_date': today,
            'target_date': target_date,
            'check_in_frequency': freq,
            'state': 'committed',
            'action_item_ids': item_cmds,
        })

        # cross-link
        session.sudo().write({'action_plan_id': plan.id})
        strategy.sudo().write({'coaching_session_id': session.id})

        return {
            'ok': True,
            'session_id': session.id,
            'plan_id': plan.id,
            'strategy_id': strategy.id,
            'banker_name': emp.name,
            'item_count': len(item_cmds),
        }

    # ════════════════════════════════════════════════════════════════
    #  WORKSPACE DRAWER — enriched detail payload for the OWL workspace
    # ════════════════════════════════════════════════════════════════
    @api.model
    def workspace_drawer_data(self, model, res_id):
        """Single aggregator that returns a flat, template-ready dict for the
        slide-over drawer of any workspace record. sudo() like the rest of
        this model so the drawer can read related employee/branch context."""
        res_id = int(res_id)
        dispatch = {
            'hr.coaching.session': self._drawer_session,
            'bfsi.coaching.strategy': self._drawer_strategy,
            'bfsi.action.plan': self._drawer_plan,
            'bfsi.performance.kpi': self._drawer_kpi,
            'bfsi.branch': self._drawer_branch,
            'bfsi.region': self._drawer_region,
        }
        handler = dispatch.get(model)
        if not handler:
            return {'error': 'Unsupported model %s' % model}
        rec = self.env[model].sudo().browse(res_id)
        if not rec.exists():
            return {'error': 'Record not found'}
        return handler(rec)

    def _emp_head(self, emp):
        """Common avatar/name/role header block for a person."""
        if not emp:
            return {}
        return {
            'id': emp.id,
            'name': emp.name,
            'role': self._role(emp),
            'initial': (emp.name or '?').strip()[:1].upper(),
            'color': _TYPE_COLOR.get(emp.banker_type, '#3B82F6'),
        }

    def _employee_story(self, emp):
        """Reuse the KPI-vs-target bars + root cause for a banker (drawer context)."""
        if not emp:
            return {'bars': [], 'root_cause': ''}
        KPI = self.env['bfsi.performance.kpi'].sudo()
        latest = KPI.search([('employee_id', '=', emp.id)],
                            order='period_date desc', limit=1)
        target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(emp.id)
        bars, _strengths, gaps = self._build_kpi_bars(latest, target)
        return {'bars': bars, 'root_cause': self._build_root_cause(emp, latest, gaps)}

    # ── SESSION ──────────────────────────────────────────────────────
    def _drawer_session(self, s):
        guide = self._session_guide(s)
        return {
            'kind': 'session',
            'id': s.id,
            'name': s.name,
            'state': s.state,
            'employee': self._emp_head(s.employee_id),
            'coach': self._emp_head(s.coach_id),
            'session_type': s.session_type,
            'session_type_label': dict(s._fields['session_type'].selection).get(s.session_type, ''),
            'topic_label': dict(s._fields['topic'].selection).get(s.topic, ''),
            'session_date': self.env['bfsi.scoring'].fmt_datetime(s.session_date),
            'session_date_raw': s.session_date.isoformat() if s.session_date else '',
            'session_date_relative': self.env['bfsi.scoring'].fmt_relative(s.session_date),
            'duration': s.duration,
            'outcome': s.outcome or '',
            'outcome_label': dict(s._fields['outcome'].selection).get(s.outcome, '') if s.outcome else '',
            'description': _strip_emoji(s.description or ''),
            'discussion_notes': _strip_emoji(s.discussion_notes or ''),
            'ai_summary': _strip_emoji(s.action_items or ''),
            'ai_chat_history': _strip_emoji(s.ai_chat_history or ''),
            'has_chat': s.session_type in ('ai', 'hybrid'),
            'strategy_id': s.coaching_strategy_id.id or False,
            'strategy_name': s.coaching_strategy_id.name or '',
            'plan_id': s.action_plan_id.id or False,
            'plan_name': s.action_plan_id.name or '',
            'guide': guide,
            'story': self._employee_story(s.employee_id),
            'ai_available': self._ai_available(),
        }

    def _session_guide(self, s):
        """Consolidate the 9 overlapping AI fields into ONE phase-organized guide.
        Prefer structured strategy questions + per-phase talking points; fall
        back to the legacy single blob only when no strategy is linked."""
        phases = [
            ('opening', 'Opening — build rapport', s.strategy_opening_questions, s.ai_suggestion_opening),
            ('probing', 'Probing — find root cause', s.strategy_probing_questions, s.ai_suggestion_probing),
            ('closing', 'Closing — drive commitment', s.strategy_closing_questions, s.ai_suggestion_closing),
        ]
        out_phases = []
        for key, label, questions_txt, tips_html in phases:
            out_phases.append({
                'key': key,
                'label': label,
                'questions': _split_lines(questions_txt),
                'tips_html': _strip_emoji(tips_html or ''),
            })
        has_strategy = bool(s.coaching_strategy_id)
        return {
            'phases': out_phases,
            'general_tips': _split_lines(s.strategy_coaching_tips),
            'general_tips_html': _strip_emoji(s.ai_suggestion_tips or ''),
            # legacy fallback shown only when there is no structured strategy
            'legacy_html': _strip_emoji(s.ai_suggested_questions or s.strategy_session_guide or '')
                           if not has_strategy else '',
            'has_strategy': has_strategy,
        }

    # ── STRATEGY ─────────────────────────────────────────────────────
    def _drawer_strategy(self, st):
        return {
            'kind': 'strategy',
            'id': st.id,
            'name': st.name,
            'state': st.state,
            'banker': self._emp_head(st.banker_id),
            'manager': self._emp_head(st.manager_id),
            'ai_confidence': round(st.ai_confidence or 0),
            'snapshot_date': self.env['bfsi.scoring'].fmt_date(st.kpi_snapshot_date),
            'snapshot_date_raw': st.kpi_snapshot_date.isoformat() if st.kpi_snapshot_date else '',
            'performance_summary': _strip_emoji(st.performance_summary or ''),
            'root_cause_analysis': _strip_emoji(st.root_cause_analysis or ''),
            'strengths': _split_lines(st.strengths),
            'improvement_areas': _split_lines(st.improvement_areas),
            'themes': _split_lines(st.coaching_themes),
            'ai_strategy': _strip_emoji(st.ai_strategy or ''),
            'proposed_plan': _strip_emoji(st.proposed_plan or ''),
            'opening_questions': _split_lines(st.opening_questions),
            'probing_questions': _split_lines(st.probing_questions),
            'closing_questions': _split_lines(st.closing_questions),
            'coaching_tips': _split_lines(st.coaching_tips),
            'session_guide': _strip_emoji(st.session_guide or ''),
            'has_roleplay': bool(st.roleplay_scenarios),
            'session_id': st.coaching_session_id.id or False,
            'ai_available': self._ai_available(),
        }

    # ── ACTION PLAN ──────────────────────────────────────────────────
    def _drawer_plan(self, p):
        Scoring = self.env['bfsi.scoring']
        items = [{
            'id': it.id,
            'name': it.name,
            'description': it.description or '',
            'progress': round(it.progress or 0),
            'state': it.state,
            'priority': it.priority,
            'kpi_category': it.kpi_category or '',
            'specific_kpi': dict(it._fields['specific_kpi'].selection).get(it.specific_kpi, '') if it.specific_kpi else '',
            'target_value': it.target_value or 0,
            'target_end_date': Scoring.fmt_date(it.target_end_date),
        } for it in p.action_item_ids]
        d = p.days_remaining or 0
        if p.state in ('completed', 'cancelled'):
            timeline_label = ''
        elif d < 0:
            timeline_label = _('Overdue by %s days') % (-d)
        elif d == 0:
            timeline_label = _('Due today')
        else:
            timeline_label = _('%s days remaining') % d
        return {
            'kind': 'plan',
            'id': p.id,
            'name': p.name,
            'state': p.state,
            'employee': self._emp_head(p.employee_id),
            'manager': self._emp_head(p.manager_id),
            'progress': round(p.progress_percentage or 0),
            'item_count': p.action_item_count,
            'completed_items': p.completed_items,
            'is_overdue': p.is_overdue,
            'days_remaining': max(0, d),
            'overdue_days': max(0, -d),
            'timeline_label': timeline_label,
            'branch_name': p.branch_id.name if p.branch_id else '',
            'last_update': Scoring.fmt_relative(p.last_update_date),
            'effectiveness_label': dict(p._fields['effectiveness_rating'].selection).get(p.effectiveness_rating, '') if p.effectiveness_rating else '',
            'commitment_date': Scoring.fmt_date(p.commitment_date),
            'target_date': Scoring.fmt_date(p.target_date),
            'target_date_relative': Scoring.fmt_relative(p.target_date),
            'completion_date': Scoring.fmt_date(p.completion_date),
            'check_in_frequency': p.check_in_frequency or '',
            'next_check_in_date': Scoring.fmt_date(p.next_check_in_date),
            'next_check_in_relative': Scoring.fmt_relative(p.next_check_in_date),
            'employee_notes': _strip_emoji(p.employee_notes or ''),
            'employee_feedback': p.employee_feedback or '',
            'manager_review': p.manager_review or '',
            'effectiveness_rating': p.effectiveness_rating or '',
            'ai_recommendations': _strip_emoji(p.ai_recommendations or ''),
            'session_id': p.coaching_session_id.id or False,
            'items': items,
        }

    # ── KPI (Performance, phase 2) ───────────────────────────────────
    def _drawer_kpi(self, k):
        Scoring = self.env['bfsi.scoring']
        snap = Scoring.employee_snapshot(k.employee_id.id)
        target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(k.employee_id.id)
        bars, _s, gaps = self._build_kpi_bars(k, target)

        def num(v, digits=1):
            v = v or 0
            return ('%g' % round(v, digits))

        # full breakdown so the drawer fully replaces the backend form
        breakdown = [
            {'key': 'input', 'label': 'Activity (input)', 'icon': 'phone', 'rows': [
                ('Dials/hour', num(k.dials_per_hour)),
                ('Total dials', str(k.total_dials or 0)),
                ('Connects', '%s (%s%%)' % (k.connects or 0, num(k.connect_rate))),
                ('Meetings scheduled', str(k.meetings_scheduled or 0)),
                ('Meetings conducted', str(k.meetings_conducted or 0)),
                ('Hours worked', num(k.hours_worked)),
            ]},
            {'key': 'behavior', 'label': 'Behaviour', 'icon': 'gauge', 'rows': [
                ('Script adherence', num(k.script_adherence) + '%'),
                ('Objection handling', num(k.objection_handling_score)),
                ('Need analysis', num(k.need_analysis_quality)),
                ('Product knowledge', num(k.product_knowledge_score)),
                ('Compliance', num(k.compliance_score)),
                ('Customer satisfaction', num(k.customer_satisfaction)),
            ]},
            {'key': 'output', 'label': 'Output & outcome', 'icon': 'trending-up', 'rows': [
                ('Conversions', '%s (%s%%)' % (k.conversions or 0, num(k.conversion_rate))),
                ('Products sold', str(k.products_sold or 0)),
                ('Leads generated', str(k.leads_generated or 0)),
                ('Proposals submitted', str(k.proposals_submitted or 0)),
                ('Revenue', Scoring.fmt_currency(k.revenue or 0, k.currency_id)),
                ('Commission', Scoring.fmt_currency(k.commission or 0, k.currency_id)),
            ]},
        ]
        for sec in breakdown:
            sec['rows'] = [{'label': l, 'value': v} for l, v in sec['rows']]

        return {
            'breakdown': breakdown,
            'period_type_label': dict(k._fields['period_type'].selection).get(k.period_type, ''),
            'deviation': round(k.deviation_score or 0, 1),
            'notes': k.notes or '',
            'kind': 'kpi',
            'id': k.id,
            'name': k.display_name,
            'employee': self._emp_head(k.employee_id),
            'period_date': Scoring.fmt_date(k.period_date),
            'period_date_relative': Scoring.fmt_relative(k.period_date),
            'overall_score': round(k.overall_score or 0),
            'branch_rank': k.branch_rank,
            'rank_movement': k.rank_movement,
            'coaching_priority': k.coaching_priority or 'low',
            'revenue': k.revenue or 0,
            'revenue_formatted': Scoring.fmt_currency(k.revenue or 0, k.currency_id),
            'conversions': k.conversions or 0,
            'trend': snap['trend'],
            'bars': bars,
            'root_cause': self._build_root_cause(k.employee_id, k, gaps),
            'ai_analysis': _strip_emoji(k.ai_analysis or ''),
            'can_coach': True,
        }

    # ── BRANCH / REGION (Organization, phase 3) ──────────────────────
    def _drawer_branch(self, b):
        roster = [{
            **self._emp_head(e),
            'score': round(e.latest_overall_score or 0),
            'rank': e.current_month_rank or 0,
            'priority': e.coaching_priority or 'low',
        } for e in b.banker_ids.filtered(
            lambda e: e.active and e.banker_type not in (
                'branch_manager', 'regional_manager'))]
        return {
            'kind': 'branch',
            'id': b.id,
            'name': b.name,
            'code': b.code or '',
            'manager': self._emp_head(b.manager_id),
            'region': b.region_id.name if b.region_id else '',
            'banker_count': b.banker_count,
            'avg_score': round(b.avg_performance_score or 0),
            'needs_coaching': b.bankers_needing_coaching,
            'roster': sorted(roster, key=lambda r: r['rank'] or 99),
        }

    def _drawer_region(self, r):
        branches = [{
            'id': br.id, 'name': br.name, 'code': br.code or '',
            'banker_count': br.banker_count,
            'avg_score': round(br.avg_performance_score or 0),
        } for br in r.branch_ids]
        return {
            'kind': 'region',
            'id': r.id,
            'name': r.name,
            'code': r.code or '',
            'manager': self._emp_head(r.regional_manager_id),
            'branch_count': r.branch_count,
            'branches': branches,
        }

    # ════════════════════════════════════════════════════════════════
    #  WORKSPACE API — one adaptive workspace, role-aware
    # ════════════════════════════════════════════════════════════════
    def _current_employee(self):
        emp = self.env.user.employee_id
        if not emp:
            emp = self.env['hr.employee'].sudo().search(
                [('user_id', '=', self.env.uid)], limit=1)
        return emp

    def _workspace_role(self):
        user = self.env.user
        if user.has_group('hr_development_ai.group_bfsi_regional_manager'):
            return 'regional_manager'
        if user.has_group('hr_development_ai.group_bfsi_branch_manager'):
            return 'branch_manager'
        return 'banker'

    def _managed_branches(self, emp, role):
        """Branches the current user may see — scoped BEFORE any sudo read."""
        Branch = self.env['bfsi.branch'].sudo()
        if self.env.user.has_group('hr_development_ai.group_hr_development_admin'):
            return Branch.search([])
        if role == 'regional_manager':
            regions = self.env['bfsi.region'].sudo().search(
                [('regional_manager_id', '=', emp.id)])
            branches = regions.mapped('branch_ids')
            if not branches and emp.branch_id:
                branches = emp.branch_id
            return branches
        if role == 'branch_manager':
            branches = Branch.search([('manager_id', '=', emp.id)])
            if not branches and emp.branch_id:
                branches = emp.branch_id
            return branches
        return Branch.browse()

    def _can_view_employee(self, requester, role, target):
        if target.id == requester.id:
            return True
        if role == 'banker':
            return False
        branches = self._managed_branches(requester, role)
        return bool(target.branch_id and target.branch_id.id in branches.ids)

    @api.model
    def workspace_home_data(self):
        """One RPC that resolves the user's role and returns everything the
        adaptive Home screen needs."""
        emp = self._current_employee()
        if not emp:
            return {'error': 'No employee record linked to this user'}
        role = self._workspace_role()
        Scoring = self.env['bfsi.scoring']
        today = fields.Date.today()

        out = {
            'role': role,
            'is_admin': self.env.user.has_group('hr_development_ai.group_hr_development_admin'),
            'ai_available': self._ai_available(),
            'user': {
                **self._emp_head(emp),
                'branch_id': emp.branch_id.id if emp.branch_id else False,
                'branch_name': emp.branch_id.name if emp.branch_id else '',
            },
            'today_label': Scoring.fmt_date(today),
        }

        if role == 'banker':
            out['me'] = self._home_banker(emp)
            return out

        if role == 'branch_manager':
            branches = self._managed_branches(emp, role)
            branch = branches[:1]
            out['branches'] = [{'id': b.id, 'name': b.name} for b in branches]
            if branch:
                out.update(self._home_branch(branch, emp))
            return out

        # regional manager
        branches = self._managed_branches(emp, role)
        rollup = []
        for b in branches:
            snap = Scoring.branch_snapshot(b.id)
            rollup.append({
                **snap,
                'code': b.code or '',
                'manager': self._emp_head(b.manager_id),
                'region': b.region_id.name if b.region_id else '',
                'sessions_this_month': b.coaching_sessions_this_month,
                'plan_completion_rate': round(b.action_plan_completion_rate or 0),
            })
        rollup.sort(key=lambda r: r['avg_score'], reverse=True)
        out['branch_rollup'] = rollup
        return out

    def _home_banker(self, emp):
        """My 360 payload for a banker's own home."""
        Scoring = self.env['bfsi.scoring']
        snap = Scoring.employee_snapshot(emp.id)
        story = self._employee_story(emp)
        Plan = self.env['bfsi.action.plan'].sudo()
        plans = Plan.search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ['committed', 'in_progress', 'overdue']),
        ], order='target_date asc', limit=5)
        Session = self.env['hr.coaching.session'].sudo()
        sessions = Session.search([('employee_id', '=', emp.id)],
                                  order='session_date desc', limit=5)
        Nudge = self.env['hr.coaching.nudge'].sudo()
        nudges = Nudge.search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ['sent', 'read']),
        ], order='create_date desc', limit=3)
        return {
            'snapshot': snap,
            'bars': story['bars'],
            'root_cause': story['root_cause'],
            'plans': [self._drawer_plan(p) for p in plans],
            'sessions': self._session_rows(sessions),
            'nudges': [{
                'id': n.id, 'title': n.title, 'message': n.message or '',
                'priority': n.priority,
            } for n in nudges],
        }

    def _home_branch(self, branch, emp):
        """Team cockpit payload for a branch manager's home."""
        Scoring = self.env['bfsi.scoring']
        snap = Scoring.branch_snapshot(branch.id)
        queue = self.coaching_queue(branch.id)
        Plan = self.env['bfsi.action.plan'].sudo()
        today = fields.Date.today()
        banker_ids = branch.banker_ids.filtered(
            lambda e: e.active and e.banker_type not in (
                'branch_manager', 'regional_manager')).ids
        active_plans = Plan.search([
            ('employee_id', 'in', banker_ids),
            ('state', 'in', ['committed', 'in_progress', 'overdue']),
        ])
        checkins = active_plans.filtered(
            lambda p: p.next_check_in_date and p.next_check_in_date <= today)
        return {
            'branch': {'id': branch.id, 'name': branch.name},
            'kpi_strip': {
                'avg_score': snap['avg_score'],
                'coverage': snap['coverage'],
                'coverage_label': snap['coverage_label'],
                'needs_coaching': snap['needs_coaching'],
                'revenue': snap['latest_revenue'],
                'revenue_formatted': snap['latest_revenue_formatted'],
                'active_plans': len(active_plans),
                'overdue_plans': len(active_plans.filtered('is_overdue')),
                'sessions_this_month': branch.coaching_sessions_this_month,
                'plan_completion_rate': round(branch.action_plan_completion_rate or 0),
            },
            'queue': queue.get('rows', []),
            'checkins_due': [{
                'plan_id': p.id,
                'name': p.name,
                'employee': self._emp_head(p.employee_id),
                'progress': round(p.progress_percentage or 0),
                'due': Scoring.fmt_relative(p.next_check_in_date),
                'is_overdue': p.is_overdue,
            } for p in checkins.sorted(key=lambda p: p.next_check_in_date)[:8]],
        }

    @api.model
    def workspace_branch_cockpit(self, branch_id):
        """Team cockpit payload for one branch — used when a regional manager
        (or admin) drills into a branch from the rollup."""
        emp = self._current_employee()
        if not emp:
            return {'error': 'No employee record linked to this user'}
        role = self._workspace_role()
        branches = self._managed_branches(emp, role)
        branch = branches.filtered(lambda b: b.id == int(branch_id))
        if not branch:
            return {'error': 'You can only view branches in your own scope'}
        return self._home_branch(branch, emp)

    def _session_rows(self, sessions):
        Scoring = self.env['bfsi.scoring']
        return [{
            'id': s.id,
            'name': s.name,
            'state': s.state,
            'session_type': s.session_type,
            'topic_label': dict(s._fields['topic'].selection).get(s.topic, ''),
            'date': Scoring.fmt_date(s.session_date),
            'date_relative': Scoring.fmt_relative(s.session_date),
            'outcome': s.outcome or '',
            'outcome_label': dict(s._fields['outcome'].selection).get(s.outcome, '') if s.outcome else '',
            'coach': self._emp_head(s.coach_id),
            'plan_id': s.action_plan_id.id or False,
        } for s in sessions]

    @api.model
    def person_360_data(self, employee_id):
        """The Person 360 hub: everything about one banker in one call.
        Access: self, or a manager whose scope contains the banker's branch."""
        requester = self._current_employee()
        if not requester:
            return {'error': 'No employee record linked to this user'}
        role = self._workspace_role()
        emp = self.env['hr.employee'].sudo().browse(int(employee_id))
        if not emp.exists():
            return {'error': 'Employee not found'}
        if not self._can_view_employee(requester, role, emp):
            return {'error': 'You can only view people on your own team'}

        Scoring = self.env['bfsi.scoring']
        snap = Scoring.employee_snapshot(emp.id)
        story = self._employee_story(emp)
        Plan = self.env['bfsi.action.plan'].sudo()
        plans = Plan.search([('employee_id', '=', emp.id)],
                            order='create_date desc', limit=10)
        Session = self.env['hr.coaching.session'].sudo()
        sessions = Session.search([('employee_id', '=', emp.id)],
                                  order='session_date desc', limit=10)
        Strategy = self.env['bfsi.coaching.strategy'].sudo()
        strategies = Strategy.search([('banker_id', '=', emp.id)],
                                     order='create_date desc', limit=5)
        is_self = emp.id == requester.id
        return {
            'employee': {
                **self._emp_head(emp),
                'branch_name': emp.branch_id.name if emp.branch_id else '',
                'avatar_url': '/web/image/hr.employee/%d/avatar_128' % emp.id,
            },
            'snapshot': snap,
            'bars': story['bars'],
            'root_cause': story['root_cause'],
            'plans': [self._drawer_plan(p) for p in plans],
            'sessions': self._session_rows(sessions),
            'strategies': [{
                'id': st.id,
                'name': st.name,
                'state': st.state,
                'confidence': round(st.ai_confidence or 0),
                'date': Scoring.fmt_date(st.kpi_snapshot_date),
                'themes': _split_lines(st.coaching_themes)[:3],
            } for st in strategies],
            'can_coach': not is_self and role in ('branch_manager', 'regional_manager'),
            'is_self': is_self,
            'ai_available': self._ai_available(),
        }

    # Whitelisted in-flow editing — the only write path the workspace uses
    _SAVE_WHITELIST = {
        'hr.coaching.session': {'outcome', 'employee_satisfaction', 'discussion_notes',
                                'next_session_date', 'topic', 'duration'},
        'bfsi.action.plan': {'target_date', 'check_in_frequency', 'employee_notes',
                             'employee_feedback', 'manager_review', 'effectiveness_rating'},
        'bfsi.action.plan.item': {'name', 'description', 'target_value',
                                  'target_end_date', 'priority', 'progress', 'state'},
    }

    def _record_employee(self, rec):
        if rec._name == 'bfsi.action.plan.item':
            return rec.action_plan_id.employee_id
        if rec._name == 'bfsi.coaching.strategy':
            return rec.banker_id
        return rec.employee_id

    @api.model
    def workspace_record_save(self, model, res_id, vals):
        """Inline edit endpoint for the workspace drawers/dialogs.
        Only whitelisted fields, only on records in the user's scope."""
        allowed = self._SAVE_WHITELIST.get(model)
        if not allowed:
            raise UserError(_('Editing %s from the workspace is not allowed.') % model)
        rec = self.env[model].sudo().browse(int(res_id))
        if not rec.exists():
            raise UserError(_('Record not found.'))
        requester = self._current_employee()
        role = self._workspace_role()
        target = self._record_employee(rec)
        if not requester or not self._can_view_employee(requester, role, target):
            raise UserError(_('You can only update records for your own team.'))
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}
        if not clean:
            raise UserError(_('No editable fields in this update.'))
        rec.write(clean)
        # return a refreshed drawer payload so the UI updates in place
        if model == 'bfsi.action.plan.item':
            return self.workspace_drawer_data('bfsi.action.plan', rec.action_plan_id.id)
        return self.workspace_drawer_data(model, rec.id)

    @api.model
    def workspace_report_progress(self, plan_id, notes):
        """In-drawer progress report — replaces the old backend wizard.
        Appends a timestamped note and rolls the plan state forward."""
        plan = self.env['bfsi.action.plan'].sudo().browse(int(plan_id))
        if not plan.exists():
            raise UserError(_('Plan not found.'))
        requester = self._current_employee()
        role = self._workspace_role()
        if not requester or not self._can_view_employee(requester, role, plan.employee_id):
            raise UserError(_('You can only update plans for your own team.'))
        notes = (notes or '').strip()
        if notes:
            stamp = self.env['bfsi.scoring'].fmt_datetime(fields.Datetime.now())
            plan.employee_notes = ((plan.employee_notes or '')
                                   + '\n\n[%s]\n%s' % (stamp, notes)).strip()
        plan.last_update_date = fields.Datetime.now()
        if plan.state == 'committed':
            plan.state = 'in_progress'
        if plan.progress_percentage >= 100:
            plan.state = 'completed'
            plan.completion_date = fields.Date.today()
        plan._set_next_check_in_date()
        return self.workspace_drawer_data('bfsi.action.plan', plan.id)

    @api.model
    def workspace_plan_action(self, plan_id, action):
        """Run a plan lifecycle button (commit / start / complete / cancel)
        scoped + sudo, so per-user permission quirks on the notification
        side-effect can't make a simple state change fail. Returns the
        refreshed drawer payload."""
        allowed = {'action_commit', 'action_start', 'action_complete', 'action_cancel'}
        if action not in allowed:
            raise UserError(_('Action not allowed.'))
        plan = self.env['bfsi.action.plan'].sudo().browse(int(plan_id))
        if not plan.exists():
            raise UserError(_('Plan not found.'))
        requester = self._current_employee()
        role = self._workspace_role()
        if not requester or not self._can_view_employee(requester, role, plan.employee_id):
            raise UserError(_('You can only update plans for your own team.'))
        getattr(plan, action)()
        return self.workspace_drawer_data('bfsi.action.plan', plan.id)

    @api.model
    def workspace_session_action(self, session_id, action):
        """Run a session lifecycle button (start / complete) scoped + sudo."""
        allowed = {'action_start_session', 'action_complete_session',
                   'action_generate_ai_summary', 'action_create_action_plan'}
        if action not in allowed:
            raise UserError(_('Action not allowed.'))
        session = self.env['hr.coaching.session'].sudo().browse(int(session_id))
        if not session.exists():
            raise UserError(_('Session not found.'))
        requester = self._current_employee()
        role = self._workspace_role()
        if not requester or not self._can_view_employee(requester, role, session.employee_id):
            raise UserError(_('You can only update sessions for your own team.'))
        result = getattr(session, action)()
        payload = self.workspace_drawer_data('hr.coaching.session', session.id)
        if isinstance(result, dict):
            # surface a follow-on action (e.g. open a created plan)
            if result.get('type'):
                payload['follow_action'] = result
            # surface a user-facing message + success flag for the toast
            if 'message' in result:
                payload['action_message'] = result['message']
                payload['action_ok'] = result.get('success', True)
        return payload

    @api.model
    def workspace_session_chat(self, session_id, message):
        """In-drawer AI chat on a session — sends, PERSISTS to the transcript
        and returns the refreshed drawer payload (no popup dialog)."""
        session = self.env['hr.coaching.session'].sudo().browse(int(session_id))
        if not session.exists():
            raise UserError(_('Session not found.'))
        requester = self._current_employee()
        role = self._workspace_role()
        if not requester or not self._can_view_employee(requester, role, session.employee_id):
            raise UserError(_('You can only chat on sessions for your own team.'))
        message = (message or '').strip()
        if not message:
            raise UserError(_('Type a message first.'))
        result = session.action_send_ai_message(message)
        reply = _strip_emoji((result or {}).get('response') or '')
        # persist both turns so the conversation survives reloads.
        # transcripts exist in two historical formats: JSON and marker text.
        history = []
        if session.ai_transcript:
            try:
                data = json.loads(session.ai_transcript)
                raw = data.get('messages', data) if isinstance(data, dict) else data
                history = [m for m in raw if isinstance(m, dict) and m.get('content')]
            except (ValueError, TypeError):
                history = session._parse_formatted_transcript(session.ai_transcript)
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': reply})
        session.ai_transcript = session._format_chat_transcript(history)
        return self.workspace_drawer_data('hr.coaching.session', session.id)

    @api.model
    def workspace_quick_session(self, employee_id, vals):
        """Log a quick check-in session without the full wizard."""
        requester = self._current_employee()
        role = self._workspace_role()
        emp = self.env['hr.employee'].sudo().browse(int(employee_id))
        if not emp.exists():
            raise UserError(_('Employee not found.'))
        if not requester or not self._can_view_employee(requester, role, emp):
            raise UserError(_('You can only log sessions for your own team.'))
        vals = vals or {}
        if not vals.get('outcome'):
            raise UserError(_('Record the session outcome before saving.'))
        session = self.env['hr.coaching.session'].sudo().create({
            'name': vals.get('name') or _('Check-in: %s') % emp.name,
            'employee_id': emp.id,
            'coach_id': requester.id,
            'session_type': 'human',
            'topic': vals.get('topic') or 'performance',
            'state': 'completed',
            'is_bfsi_session': True,
            'duration': vals.get('duration') or 0.25,
            'discussion_notes': _to_html(vals.get('notes')),
            'outcome': vals['outcome'],
            'employee_satisfaction': vals.get('satisfaction') or False,
        })
        # roll the plan's next check-in forward
        plan_id = vals.get('plan_id')
        if plan_id:
            plan = self.env['bfsi.action.plan'].sudo().browse(int(plan_id))
            if plan.exists() and plan.employee_id.id == emp.id:
                plan._set_next_check_in_date()
        return {'ok': True, 'session_id': session.id}

    # ════════════════════════════════════════════════════════════════
    #  SETTINGS API — KPI Targets & Integrations, fully in-workspace
    # ════════════════════════════════════════════════════════════════
    _SETTINGS_FIELDS = {
        'bfsi.kpi.target': {
            'employee_id', 'job_id', 'branch_id', 'banker_type', 'period_type',
            'valid_from', 'valid_to', 'is_active', 'priority', 'notes',
            'target_overall_score', 'target_revenue', 'target_dials_per_hour',
            'target_total_dials', 'target_connects', 'target_meetings_scheduled',
            'target_meetings_conducted', 'target_script_adherence',
            'target_objection_handling', 'target_need_analysis',
            'target_product_knowledge', 'target_compliance',
            'target_customer_satisfaction', 'target_conversions',
            'target_conversion_rate',
        },
        'bfsi.kpi.integration': {
            'name', 'source_system', 'api_base_url', 'auth_type', 'api_key',
            'api_secret', 'username', 'sync_frequency', 'active',
            'data_endpoint', 'employee_endpoint', 'notes',
        },
        'hr.ai.provider.config': {
            'provider', 'is_active', 'model_name', 'timeout',
            'openai_api_key', 'llama_endpoint', 'mistral_endpoint',
        },
    }

    def _assert_settings_admin(self):
        if not self.env.user.has_group('hr_development_ai.group_hr_development_admin'):
            raise UserError(_('Only administrators can change coaching settings.'))

    @api.model
    def workspace_settings_data(self):
        """Everything the in-workspace Settings screen needs in one call."""
        self._assert_settings_admin()
        Scoring = self.env['bfsi.scoring']
        Target = self.env['bfsi.kpi.target'].sudo()
        targets = []
        for t in Target.search([], order='is_active desc, priority, id desc'):
            targets.append({
                'id': t.id,
                'name': t.name,
                'scope': (t.employee_id.name or t.job_id.name
                          or dict(t._fields['banker_type'].selection).get(t.banker_type)
                          or t.branch_id.name or _('Everyone')),
                'employee_id': t.employee_id.id or False,
                'job_id': t.job_id.id or False,
                'branch_id': t.branch_id.id or False,
                'banker_type': t.banker_type or '',
                'period_type': t.period_type,
                'period_label': dict(t._fields['period_type'].selection).get(t.period_type, ''),
                'valid_from': fields.Date.to_string(t.valid_from) if t.valid_from else '',
                'valid_from_label': Scoring.fmt_date(t.valid_from),
                'valid_to': fields.Date.to_string(t.valid_to) if t.valid_to else '',
                'valid_to_label': Scoring.fmt_date(t.valid_to),
                'is_active': t.is_active,
                'priority': t.priority,
                'notes': t.notes or '',
                'score': round(t.target_overall_score or 0),
                'revenue': t.target_revenue or 0,
                'revenue_formatted': Scoring.fmt_currency(t.target_revenue or 0),
                'values': {f: getattr(t, f) or 0 for f in (
                    'target_overall_score', 'target_revenue', 'target_dials_per_hour',
                    'target_total_dials', 'target_connects', 'target_meetings_scheduled',
                    'target_meetings_conducted', 'target_script_adherence',
                    'target_objection_handling', 'target_need_analysis',
                    'target_product_knowledge', 'target_compliance',
                    'target_customer_satisfaction', 'target_conversions',
                    'target_conversion_rate')},
            })

        Integration = self.env['bfsi.kpi.integration'].sudo()
        integrations = []
        for i in Integration.search([('active', 'in', [True, False])]):
            integrations.append({
                'id': i.id,
                'name': i.name,
                'source_system': i.source_system,
                'source_label': dict(i._fields['source_system'].selection).get(i.source_system, ''),
                'state': i.state,
                'state_label': dict(i._fields['state'].selection).get(i.state, ''),
                'active': i.active,
                'api_base_url': i.api_base_url or '',
                'auth_type': i.auth_type or '',
                'sync_frequency': i.sync_frequency or 'manual',
                'sync_label': dict(i._fields['sync_frequency'].selection).get(i.sync_frequency, ''),
                'last_sync': Scoring.fmt_relative(i.last_sync_date) if i.last_sync_date else _('Never synced'),
                'last_sync_status': i.last_sync_status or '',
                'records_synced': i.records_synced or 0,
                'data_endpoint': i.data_endpoint or '',
                'notes': i.notes or '',
            })

        # AI providers (LLM config) — modern UI replaces the native form
        Provider = self.env['hr.ai.provider.config'].sudo()
        providers = []
        for p in Provider.search([]):
            providers.append({
                'id': p.id,
                'company': p.company_id.name or '',
                'provider': p.provider,
                'provider_label': dict(p._fields['provider'].selection).get(p.provider, ''),
                'is_active': p.is_active,
                'status': p.connection_status or 'not_tested',
                'status_label': dict(p._fields['connection_status'].selection).get(p.connection_status, ''),
                'model_name': p.model_name or '',
                'timeout': p.timeout or 60,
                'llama_endpoint': p.llama_endpoint or '',
                'mistral_endpoint': p.mistral_endpoint or '',
                'has_api_key': bool(p.openai_api_key),
                'last_tested': Scoring.fmt_relative(p.last_test_date) if p.last_test_date else _('Never tested'),
                'last_result': p.last_test_result or '',
            })

        emp = self.env['hr.employee'].sudo()
        bankers = emp.search([('banker_type', 'not in', ('branch_manager', 'regional_manager')),
                              ('banker_type', '!=', False), ('active', '=', True)])
        return {
            'targets': targets,
            'integrations': integrations,
            'providers': providers,
            'options': {
                'ai_providers': [{'v': v, 'l': l} for v, l in
                                 self.env['hr.ai.provider.config']._fields['provider'].selection],
                'banker_types': [{'v': v, 'l': l} for v, l in
                                 self.env['bfsi.kpi.target']._fields['banker_type'].selection],
                'period_types': [{'v': v, 'l': l} for v, l in
                                 self.env['bfsi.kpi.target']._fields['period_type'].selection],
                'branches': [{'v': b.id, 'l': b.name} for b in
                             self.env['bfsi.branch'].sudo().search([])],
                'jobs': [{'v': j.id, 'l': j.name} for j in
                         self.env['hr.job'].sudo().search([])],
                'employees': [{'v': e.id, 'l': e.name} for e in bankers],
                'source_systems': [{'v': v, 'l': l} for v, l in
                                   self.env['bfsi.kpi.integration']._fields['source_system'].selection],
                'auth_types': [{'v': v, 'l': l} for v, l in
                               self.env['bfsi.kpi.integration']._fields['auth_type'].selection],
                'sync_frequencies': [{'v': v, 'l': l} for v, l in
                                     self.env['bfsi.kpi.integration']._fields['sync_frequency'].selection],
            },
        }

    @api.model
    def workspace_settings_save(self, model, res_id, vals):
        """Create or update a settings record (whitelisted fields, admin only)."""
        self._assert_settings_admin()
        allowed = self._SETTINGS_FIELDS.get(model)
        if not allowed:
            raise UserError(_('Model %s cannot be edited here.') % model)
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}
        # empty strings from selects → False for relational/selection fields
        for k, v in clean.items():
            if v in ('', None):
                clean[k] = False
        Model = self.env[model].sudo()
        if res_id:
            rec = Model.browse(int(res_id))
            if not rec.exists():
                raise UserError(_('Record not found.'))
            rec.write(clean)
        else:
            rec = Model.create(clean)
        return {'ok': True, 'id': rec.id}

    @api.model
    def workspace_settings_action(self, model, res_id, method):
        """Run a whitelisted button action (test connection / sync now)."""
        self._assert_settings_admin()
        allowed = {'bfsi.kpi.integration': {'action_test_connection', 'action_sync_now',
                                            'action_mark_active', 'action_mark_draft'},
                   'hr.ai.provider.config': {'action_test_connection', 'action_test_all_providers'}}
        if method not in allowed.get(model, set()):
            raise UserError(_('Action not allowed.'))
        rec = self.env[model].sudo().browse(int(res_id))
        if not rec.exists():
            raise UserError(_('Record not found.'))
        getattr(rec, method)()
        return {'ok': True}

    _ROWS_MODELS = ('hr.coaching.session', 'bfsi.action.plan',
                    'bfsi.coaching.strategy', 'bfsi.performance.kpi',
                    'bfsi.branch', 'bfsi.region')

    @api.model
    def workspace_rows(self, model, domain, fields_list, order=None, limit=80, offset=0):
        """search_read with server-side formatting for the workspace lists.
        Runs WITHOUT sudo so ACLs and record rules stay in force."""
        if model not in self._ROWS_MODELS:
            raise UserError(_('Model %s is not available in the workspace.') % model)
        Model = self.env[model]
        records = Model.search_read(domain or [], fields_list or [],
                                    order=order or None,
                                    limit=min(int(limit or 80), 200),
                                    offset=int(offset or 0))
        total = Model.search_count(domain or [])
        Scoring = self.env['bfsi.scoring']
        fdefs = Model._fields
        for row in records:
            for fname in list(row.keys()):
                f = fdefs.get(fname)
                if not f or row[fname] in (False, None):
                    continue
                if f.type == 'date':
                    row[fname + '_fmt'] = Scoring.fmt_date(
                        fields.Date.from_string(row[fname]))
                    row[fname + '_rel'] = Scoring.fmt_relative(
                        fields.Date.from_string(row[fname]))
                elif f.type == 'datetime':
                    row[fname + '_fmt'] = Scoring.fmt_datetime(
                        fields.Datetime.from_string(row[fname]))
                    row[fname + '_rel'] = Scoring.fmt_relative(
                        fields.Datetime.from_string(row[fname]))
                elif f.type == 'monetary':
                    row[fname + '_fmt'] = Scoring.fmt_currency(row[fname])
                elif f.type == 'float' and fname.endswith(('score', 'percentage', 'confidence')):
                    row[fname + '_fmt'] = str(round(row[fname]))
        return {'rows': records, 'total': total}

    # ════════════════════════════════════════════════════════════════
    #  helpers
    # ════════════════════════════════════════════════════════════════
    @api.model
    def _ai_available(self):
        try:
            return bool(self.env['hr.ai.provider.config'].sudo().search([
                ('is_active', '=', True),
                ('connection_status', '=', 'success'),
            ], limit=1))
        except Exception:  # noqa: BLE001
            return False

    def _role(self, emp):
        if emp.job_id:
            return emp.job_id.name
        return _ROLE_LABEL.get(emp.banker_type, emp.banker_type or 'Banker')


def _split_lines(text):
    """Split a stored multi-line/numbered text field into clean list items.
    Strips leading numbering / bullets (mirrors hr_coaching_session.get_quick_questions)."""
    if not text:
        return []
    if isinstance(text, (list, tuple)):
        return [str(x) for x in text if str(x).strip()]
    out = []
    for raw in str(text).splitlines():
        line = raw.strip().lstrip('0123456789.').lstrip('•-–*▸💡 ').strip()
        if line:
            out.append(line)
    return out


def _fmt(v):
    v = v or 0
    return ('%g' % round(v, 1))


def gaps_list(gaps):
    return ['%s — %s' % (g['label'], g['phrase']) for g in gaps]


def _join(seq):
    if not seq:
        return ''
    if isinstance(seq, str):
        return seq
    return '\n'.join('%d. %s' % (i + 1, s) for i, s in enumerate(seq))


def _to_html(text):
    if not text:
        return ''
    safe = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('\n', '<br/>'))
    return '<p>%s</p>' % safe
