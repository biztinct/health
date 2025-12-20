# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AICoachingWizard(models.TransientModel):
    _name = 'ai.coaching.wizard'
    _description = 'AI Coaching Chat Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id
    )

    topic = fields.Selection([
        ('skill_development', 'Skill Development'),
        ('career_planning', 'Career Planning'),
        ('performance', 'Performance Improvement'),
        ('goal_setting', 'Goal Setting'),
        ('general', 'General Coaching')
    ], string='Topic', required=True, default='general')

    user_message = fields.Text(
        string='Your Question/Situation',
        required=True
    )

    ai_response = fields.Html(
        string='AI Coach Response',
        readonly=True
    )

    conversation_history = fields.Text(
        string='Conversation History',
        readonly=True
    )

    ai_provider = fields.Char(
        string='AI Provider',
        compute='_compute_ai_provider'
    )

    def _compute_ai_provider(self):
        """Show which AI provider will be used"""
        for wizard in self:
            config = self.env['hr.ai.provider.config'].get_config()
            wizard.ai_provider = dict(config._fields['provider'].selection).get(config.provider, 'Unknown')

    def action_get_ai_response(self):
        """Get AI coaching response"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Build context
            context = {
                'employee_name': self.employee_id.name,
                'situation': self.topic,
                'relevant_data': {
                    'question': self.user_message,
                    'job': self.employee_id.job_id.name if self.employee_id.job_id else '',
                    'skills': [s.skill_id.name for s in self.employee_id.skill_ids[:10]],
                    'recent_coaching': []  # Could add recent nudges
                },
                'tone': 'supportive'
            }

            # Get coaching response
            result = ai_provider.generate_coaching_nudge(context)

            # Format response
            response_html = f"""
            <div class="ai_coaching_response">
                <h4>{result.get('message', '')}</h4>

                <h5>Suggested Actions:</h5>
                <ul>
                    {''.join(f'<li>{action}</li>' for action in result.get('action_items', []))}
                </ul>

                <p><em>Priority: {result.get('priority', 'medium').title()}</em></p>
            </div>
            """

            self.ai_response = response_html

            # Update conversation history
            history = self.conversation_history or ''
            history += f"\n\n--- You: ---\n{self.user_message}\n\n--- AI Coach: ---\n{result.get('message', '')}"
            self.conversation_history = history

            # Clear user message for next question
            self.user_message = ''

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ai.coaching.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Coaching Error',
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_save_as_session(self):
        """Save conversation as coaching session"""
        self.ensure_one()

        if not self.conversation_history:
            return

        session = self.env['hr.coaching.session'].create({
            'name': f'AI Coaching: {self.topic.replace("_", " ").title()}',
            'employee_id': self.employee_id.id,
            'session_type': 'ai',
            'topic': self.topic,
            'ai_transcript': self.conversation_history,
            'state': 'completed'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current'
        }
