# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class BFSICoachingStrategy(models.Model):
    _name = 'bfsi.coaching.strategy'
    _description = 'AI-Generated Coaching Strategy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Strategy Name',
        compute='_compute_name',
        store=True
    )

    # Who this strategy is for
    banker_id = fields.Many2one(
        'hr.employee',
        string='Banker',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Branch Manager',
        tracking=True,
        help='Manager who requested this strategy'
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        related='banker_id.branch_id',
        store=True
    )

    # Performance context at time of strategy generation
    kpi_snapshot_date = fields.Date(
        string='KPI Snapshot Date',
        default=fields.Date.today
    )

    performance_kpi_id = fields.Many2one(
        'bfsi.performance.kpi',
        string='Performance KPI Reference',
        help='The KPI record used to generate this strategy'
    )

    # AI Analysis Results
    performance_summary = fields.Html(
        string='Performance Summary',
        help='AI-generated summary of current performance'
    )

    root_cause_analysis = fields.Html(
        string='Root Cause Analysis',
        help='AI analysis of root causes for performance gaps'
    )

    strengths = fields.Text(
        string='Identified Strengths',
        help='JSON array of strength areas'
    )

    improvement_areas = fields.Text(
        string='Improvement Areas',
        help='JSON array of areas needing improvement'
    )

    coaching_themes = fields.Text(
        string='Coaching Themes',
        help='JSON array of recommended coaching themes'
    )

    # Generated Strategy
    ai_strategy = fields.Html(
        string='AI Coaching Strategy',
        help='The main coaching strategy and approach'
    )

    proposed_plan = fields.Html(
        string='Proposed Coaching Plan',
        help='Structured coaching plan with steps'
    )

    session_guide = fields.Html(
        string='Session Guide',
        help='Step-by-step guide for conducting the coaching session'
    )

    # Coaching questions and prompts for manager
    opening_questions = fields.Text(
        string='Opening Questions',
        help='JSON array of questions to start the session'
    )

    probing_questions = fields.Text(
        string='Probing Questions',
        help='JSON array of deeper exploration questions'
    )

    closing_questions = fields.Text(
        string='Closing Questions',
        help='JSON array of questions to close the session'
    )

    coaching_tips = fields.Text(
        string='Coaching Tips',
        help='JSON array of tips for the manager'
    )

    # Roleplay scenarios for manager practice
    roleplay_scenarios = fields.Text(
        string='Roleplay Scenarios',
        help='JSON array of practice scenarios for sandbox'
    )

    roleplay_conversation = fields.Text(
        string='Roleplay Conversation',
        help='JSON transcript of roleplay practice session'
    )

    # Micro-learning recommendations
    learning_recommendations = fields.Text(
        string='Learning Recommendations',
        help='JSON array of recommended learning content'
    )

    # Linked session
    coaching_session_id = fields.Many2one(
        'hr.coaching.session',
        string='Coaching Session',
        help='The coaching session this strategy was used for'
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('reviewed', 'Reviewed'),
        ('in_use', 'In Use'),
        ('completed', 'Completed'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)

    # AI metadata
    ai_provider = fields.Char(string='AI Provider')
    generation_date = fields.Datetime(string='Generation Date')
    ai_confidence = fields.Float(
        string='AI Confidence',
        digits=(3, 2),
        help='AI confidence score for the strategy (0-1)'
    )

    @api.depends('banker_id', 'kpi_snapshot_date')
    def _compute_name(self):
        for strategy in self:
            if strategy.banker_id:
                strategy.name = f"Strategy for {strategy.banker_id.name} ({strategy.kpi_snapshot_date or 'Draft'})"
            else:
                strategy.name = "New Coaching Strategy"

    def action_generate_strategy(self):
        """Generate AI coaching strategy based on banker's performance"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get latest KPI for the banker
            kpi = self.env['bfsi.performance.kpi'].search([
                ('employee_id', '=', self.banker_id.id)
            ], order='period_date desc', limit=1)

            if not kpi:
                raise UserError(_('No performance data found for this banker. Please enter KPI data first.'))

            self.performance_kpi_id = kpi.id
            self.kpi_snapshot_date = kpi.period_date

            # Get target for context
            target = self.env['bfsi.kpi.target'].get_target_for_employee(
                self.banker_id.id,
                kpi.period_date
            )

            # Build comprehensive prompt
            kpi_summary = kpi.get_kpi_summary_for_ai()
            target_summary = target.get_target_summary_for_ai() if target else "No targets defined"

            prompt = f"""You are an expert sales coaching consultant for a bank. Generate a comprehensive coaching strategy.

BANKER PROFILE:
- Name: {self.banker_id.name}
- Role: {self.banker_id.job_id.name if self.banker_id.job_id else 'Banker'}
- Branch: {self.banker_id.branch_id.name if self.banker_id.branch_id else 'N/A'}

CURRENT PERFORMANCE:
{kpi_summary}

TARGETS:
{target_summary}

Generate a detailed coaching strategy in the following JSON format:
{{
    "performance_summary": "Brief 2-3 sentence summary of current performance",
    "root_cause_analysis": "Analysis of why there are gaps (if any)",
    "strengths": ["strength1", "strength2", "strength3"],
    "improvement_areas": ["area1", "area2", "area3"],
    "coaching_themes": ["theme1", "theme2"],
    "strategy": "Main coaching strategy and approach (2-3 paragraphs)",
    "proposed_plan": "Structured 4-week coaching plan with milestones",
    "session_guide": {{
        "opening": "How to open the session",
        "exploration": "Key areas to explore",
        "action_planning": "How to develop action items",
        "closing": "How to close effectively"
    }},
    "opening_questions": ["question1", "question2", "question3"],
    "probing_questions": ["question1", "question2", "question3"],
    "closing_questions": ["question1", "question2"],
    "coaching_tips": ["tip1", "tip2", "tip3"],
    "roleplay_scenarios": [
        {{
            "title": "Scenario title",
            "situation": "Description of the scenario",
            "banker_personality": "How the banker might respond",
            "coaching_goal": "What to achieve in this scenario"
        }}
    ],
    "learning_recommendations": [
        {{
            "topic": "Topic name",
            "why": "Why this is recommended",
            "format": "Video/Article/Exercise"
        }}
    ],
    "confidence": 0.85
}}

Focus on:
1. SPECIFIC and ACTIONABLE recommendations based on the actual numbers
2. Behavior-focused coaching (what the banker can control)
3. Quick wins that can show improvement within 1-2 weeks
4. Building on existing strengths while addressing gaps
"""

            response = ai_provider.generate_text(prompt, max_tokens=2000, temperature=0.7)

            # Parse the JSON response
            try:
                strategy_data = json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    strategy_data = json.loads(json_match.group())
                else:
                    raise UserError(_('AI response could not be parsed. Please try again.'))

            # Update fields from AI response
            self.write({
                'performance_summary': strategy_data.get('performance_summary', ''),
                'root_cause_analysis': strategy_data.get('root_cause_analysis', ''),
                'strengths': json.dumps(strategy_data.get('strengths', [])),
                'improvement_areas': json.dumps(strategy_data.get('improvement_areas', [])),
                'coaching_themes': json.dumps(strategy_data.get('coaching_themes', [])),
                'ai_strategy': strategy_data.get('strategy', ''),
                'proposed_plan': strategy_data.get('proposed_plan', ''),
                'session_guide': json.dumps(strategy_data.get('session_guide', {}), indent=2),
                'opening_questions': json.dumps(strategy_data.get('opening_questions', [])),
                'probing_questions': json.dumps(strategy_data.get('probing_questions', [])),
                'closing_questions': json.dumps(strategy_data.get('closing_questions', [])),
                'coaching_tips': json.dumps(strategy_data.get('coaching_tips', [])),
                'roleplay_scenarios': json.dumps(strategy_data.get('roleplay_scenarios', [])),
                'learning_recommendations': json.dumps(strategy_data.get('learning_recommendations', [])),
                'ai_confidence': strategy_data.get('confidence', 0.75),
                'ai_provider': 'openai',
                'generation_date': fields.Datetime.now(),
                'state': 'generated'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Strategy Generated'),
                    'message': _('AI coaching strategy has been generated successfully.'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Strategy generation failed: {e}")
            raise UserError(_('Failed to generate strategy: %s') % str(e))

    def action_start_roleplay(self):
        """Open roleplay sandbox for manager practice"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Coaching Roleplay Practice'),
            'res_model': 'bfsi.coaching.roleplay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_strategy_id': self.id,
                'default_banker_id': self.banker_id.id,
            }
        }

    def action_create_session(self):
        """Create a coaching session using this strategy"""
        self.ensure_one()

        session = self.env['hr.coaching.session'].create({
            'name': f'Coaching: {self.banker_id.name}',
            'employee_id': self.banker_id.id,
            'coach_id': self.manager_id.id,
            'session_type': 'hybrid',
            'topic': 'performance',
            'description': self.ai_strategy,
            'coaching_strategy_id': self.id,
        })

        self.write({
            'coaching_session_id': session.id,
            'state': 'in_use'
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Coaching Session'),
            'res_model': 'hr.coaching.session',
            'res_id': session.id,
            'view_mode': 'form',
        }

    def action_mark_complete(self):
        """Mark strategy as completed after session"""
        self.ensure_one()
        self.state = 'completed'

    def get_formatted_questions(self, question_type='opening'):
        """Get formatted questions for display"""
        self.ensure_one()
        field_map = {
            'opening': self.opening_questions,
            'probing': self.probing_questions,
            'closing': self.closing_questions
        }

        questions_json = field_map.get(question_type)
        if not questions_json:
            return []

        try:
            return json.loads(questions_json)
        except json.JSONDecodeError:
            return []

    def get_formatted_themes(self):
        """Get formatted coaching themes"""
        self.ensure_one()
        if not self.coaching_themes:
            return []
        try:
            return json.loads(self.coaching_themes)
        except json.JSONDecodeError:
            return []

    def get_roleplay_scenarios(self):
        """Get formatted roleplay scenarios"""
        self.ensure_one()
        if not self.roleplay_scenarios:
            return []
        try:
            return json.loads(self.roleplay_scenarios)
        except json.JSONDecodeError:
            return []


class BFSICoachingRoleplayWizard(models.TransientModel):
    _name = 'bfsi.coaching.roleplay.wizard'
    _description = 'Coaching Roleplay Practice Wizard'

    strategy_id = fields.Many2one(
        'bfsi.coaching.strategy',
        string='Strategy',
        required=True
    )

    banker_id = fields.Many2one(
        'hr.employee',
        string='Banker (AI will simulate)',
        required=True
    )

    scenario_index = fields.Integer(
        string='Scenario Index',
        default=0
    )

    current_scenario = fields.Text(
        string='Current Scenario',
        compute='_compute_current_scenario'
    )

    conversation_history = fields.Text(
        string='Conversation History',
        help='JSON array of conversation messages'
    )

    manager_message = fields.Text(
        string='Your Message',
        help='Type your coaching message to practice'
    )

    ai_response = fields.Text(
        string='Banker Response (AI)',
        readonly=True
    )

    feedback = fields.Html(
        string='Coaching Feedback',
        readonly=True
    )

    @api.depends('strategy_id', 'scenario_index')
    def _compute_current_scenario(self):
        for wizard in self:
            scenarios = wizard.strategy_id.get_roleplay_scenarios() if wizard.strategy_id else []
            if scenarios and wizard.scenario_index < len(scenarios):
                scenario = scenarios[wizard.scenario_index]
                wizard.current_scenario = json.dumps(scenario, indent=2)
            else:
                wizard.current_scenario = "No scenarios available"

    def action_send_message(self):
        """Send manager's message and get AI response as banker"""
        self.ensure_one()

        if not self.manager_message:
            raise UserError(_('Please enter a message.'))

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Parse current scenario
            scenarios = self.strategy_id.get_roleplay_scenarios()
            scenario = scenarios[self.scenario_index] if scenarios else {}

            # Parse conversation history
            history = json.loads(self.conversation_history) if self.conversation_history else []

            # Add manager's message to history
            history.append({
                'role': 'manager',
                'content': self.manager_message
            })

            # Build prompt for AI to respond as banker
            prompt = f"""You are roleplaying as a banker named {self.banker_id.name} in a coaching practice session.

SCENARIO:
{json.dumps(scenario, indent=2)}

CONVERSATION SO FAR:
{json.dumps(history, indent=2)}

MANAGER'S LATEST MESSAGE:
{self.manager_message}

Respond as the banker would respond, staying in character based on the scenario.
Also provide brief coaching feedback on how the manager handled this part of the conversation.

Format your response as JSON:
{{
    "banker_response": "The banker's response",
    "feedback": "Brief coaching feedback for the manager (1-2 sentences)"
}}
"""

            response = ai_provider.generate_text(prompt, max_tokens=500, temperature=0.7)

            # Parse response
            try:
                response_data = json.loads(response)
            except json.JSONDecodeError:
                response_data = {
                    'banker_response': response,
                    'feedback': ''
                }

            # Add banker response to history
            history.append({
                'role': 'banker',
                'content': response_data.get('banker_response', '')
            })

            self.write({
                'ai_response': response_data.get('banker_response', ''),
                'feedback': response_data.get('feedback', ''),
                'conversation_history': json.dumps(history),
                'manager_message': ''  # Clear input
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'bfsi.coaching.roleplay.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            raise UserError(_('Roleplay failed: %s') % str(e))

    def action_next_scenario(self):
        """Move to next scenario"""
        self.ensure_one()
        scenarios = self.strategy_id.get_roleplay_scenarios()
        if self.scenario_index < len(scenarios) - 1:
            self.write({
                'scenario_index': self.scenario_index + 1,
                'conversation_history': '',
                'ai_response': '',
                'feedback': '',
                'manager_message': ''
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bfsi.coaching.roleplay.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_save_practice(self):
        """Save the practice session to strategy"""
        self.ensure_one()
        self.strategy_id.roleplay_conversation = self.conversation_history

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Practice Saved'),
                'message': _('Your roleplay practice session has been saved.'),
                'type': 'success',
            }
        }
