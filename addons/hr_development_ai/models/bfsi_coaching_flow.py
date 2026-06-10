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

_logger = logging.getLogger(__name__)

# Avatar colours keyed by banker_type (kept in sync with the dashboard palette)
_TYPE_COLOR = {
    'wealth_manager': '#EF4444',
    'loan_officer': '#F59E0B',
    'rm': '#6366F1',
    'telesales': '#7C3AED',
    'field_sales': '#3B82F6',
    'insurance_advisor': '#14B8A6',
    'banker': '#6366F1',
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
        latest = KPI.search([('employee_id', '=', emp.id)],
                            order='period_date desc', limit=1)
        target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(emp.id)

        # trend (oldest -> newest) of overall_score
        hist = KPI.search([('employee_id', '=', emp.id)],
                          order='period_date desc', limit=8)
        trend = list(reversed([round(k.overall_score or 0) for k in hist])) or [0]

        score = round(latest.overall_score or 0) if latest else 0
        rev_target = (target.target_revenue if target else 0) or 0
        rev = latest.revenue or 0 if latest else 0
        rev_pct = round(rev / rev_target * 100) if rev_target else 0

        bars, strengths, gaps = self._build_kpi_bars(latest, target)
        root_cause = self._build_root_cause(emp, latest, gaps)
        strategy = self._build_strategy(gaps)

        return {
            'banker': {
                'id': emp.id,
                'name': emp.name,
                'role': self._role(emp),
                'initial': (emp.name or '?').strip()[:1].upper(),
                'color': _TYPE_COLOR.get(emp.banker_type, '#6366F1'),
                'score': score,
                'rank': latest.branch_rank if latest else 0,
                'move': latest.rank_movement if latest else 0,
                'rev_pct': rev_pct,
                'branch': emp.branch_id.name if emp.branch_id else '',
                'priority': (latest.coaching_priority if latest else 'low') or 'low',
            },
            'trend': trend,
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
            bars.append({'name': label, 'cat': cat, 'value': val, 'target': tgt})
            if val >= tgt:
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
        prio_rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

        rows = []
        # only front-line bankers are coaching targets, never managers
        targets = branch.banker_ids.filtered(
            lambda e: e.active and e.banker_type not in ('branch_manager', 'regional_manager')
        )
        for banker in targets:
            latest = KPI.search([('employee_id', '=', banker.id)],
                                order='period_date desc', limit=1)
            target = self.env['bfsi.kpi.target'].sudo().get_target_for_employee(banker.id)
            _bars, _str, gaps = self._build_kpi_bars(latest, target)
            score = round(latest.overall_score or 0) if latest else 0
            prio = (latest.coaching_priority if latest else 'low') or 'low'
            move = latest.rank_movement if latest else 0
            rank = latest.branch_rank if latest else 0

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
                'color': _TYPE_COLOR.get(banker.banker_type, '#6366F1'),
                'score': score,
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

        # 1) lightweight strategy record (links everything, audit trail)
        strategy = self.env['bfsi.coaching.strategy'].sudo().create({
            'banker_id': emp.id,
            'manager_id': manager.id if manager else False,
            'state': 'in_use',
            'coaching_themes': _join(vals.get('themes')),
            'opening_questions': _join(vals.get('opening')),
            'probing_questions': _join(vals.get('probing')),
            'closing_questions': _join(vals.get('closing')),
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
