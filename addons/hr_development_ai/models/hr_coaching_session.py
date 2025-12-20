# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRCoachingSession(models.Model):
    _name = 'hr.coaching.session'
    _description = 'Coaching Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc'

    name = fields.Char(string='Session Title', required=True, tracking=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Coachee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    coach_id = fields.Many2one(
        'hr.employee',
        string='Coach',
        ondelete='set null',
        tracking=True,
        help='Human coach (manager, mentor, or external coach)'
    )

    session_type = fields.Selection([
        ('ai', 'AI Coaching'),
        ('human', 'Human Coaching'),
        ('hybrid', 'Hybrid (AI + Human)')
    ], string='Type', required=True, default='ai', tracking=True)

    session_date = fields.Datetime(
        string='Session Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )

    duration = fields.Integer(
        string='Duration (minutes)',
        default=30
    )

    # Session content
    topic = fields.Selection([
        ('skill_development', 'Skill Development'),
        ('performance', 'Performance Improvement'),
        ('career_planning', 'Career Planning'),
        ('goal_setting', 'Goal Setting'),
        ('feedback', 'Feedback Discussion'),
        ('conflict_resolution', 'Conflict Resolution'),
        ('leadership', 'Leadership Development'),
        ('other', 'Other')
    ], string='Topic', required=True, default='skill_development')

    description = fields.Html(string='Description')

    discussion_notes = fields.Html(
        string='Discussion Notes',
        help='Notes from the coaching conversation'
    )

    ai_transcript = fields.Text(
        string='AI Transcript',
        help='Transcript of AI coaching conversation'
    )

    action_items = fields.Html(
        string='Action Items',
        help='Follow-up actions agreed upon'
    )

    # Outcomes
    outcome = fields.Selection([
        ('excellent', 'Excellent Progress'),
        ('good', 'Good Progress'),
        ('moderate', 'Moderate Progress'),
        ('needs_improvement', 'Needs Improvement')
    ], string='Outcome')

    employee_satisfaction = fields.Selection([
        ('5', 'Very Satisfied'),
        ('4', 'Satisfied'),
        ('3', 'Neutral'),
        ('2', 'Dissatisfied'),
        ('1', 'Very Dissatisfied')
    ], string='Employee Satisfaction')

    # Follow-up
    next_session_date = fields.Datetime(string='Next Session')

    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills Discussed',
        help='Skills addressed in this session'
    )

    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='scheduled', required=True, tracking=True)

    def action_start_session(self):
        """Start coaching session"""
        self.ensure_one()
        self.state = 'in_progress'

    def action_complete_session(self):
        """Complete coaching session"""
        self.ensure_one()
        self.state = 'completed'

        # Create follow-up activity if next session scheduled
        if self.next_session_date:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=self.next_session_date.date(),
                summary=f'Next coaching session: {self.name}',
                user_id=self.coach_id.user_id.id if self.coach_id else self.env.user.id
            )

    def action_cancel_session(self):
        """Cancel coaching session"""
        self.ensure_one()
        self.state = 'cancelled'

    def action_send_ai_message(self, message):
        """Send message to AI coach and get response

        Args:
            message (str): Message from user

        Returns:
            dict: Response containing AI message
        """
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Build conversation context
            context = {
                'session_type': dict(self._fields['session_type'].selection).get(self.session_type),
                'topic': dict(self._fields['topic'].selection).get(self.topic),
                'employee': self.employee_id.name,
                'coach': self.coach_id.name if self.coach_id else 'AI Coach',
            }

            # Get AI response
            response = ai_provider.get_coaching_response(message, context)

            return {
                'response': response.get('message', 'I apologize, I could not generate a response at this time.'),
                'suggestions': response.get('suggestions', [])
            }

        except ImportError:
            # AI provider not available, return fallback response
            return {
                'response': 'AI coaching is not currently available. Please consult with your manager or HR for coaching support.',
                'suggestions': []
            }
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"AI message failed: {e}")

            return {
                'response': 'I apologize, I encountered an error processing your message. Please try again or contact your manager.',
                'suggestions': []
            }

    def action_generate_ai_summary(self):
        """Generate AI summary of session"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Parse ai_transcript if it's JSON
            transcript_text = ''
            try:
                import json
                transcript_data = json.loads(self.ai_transcript) if self.ai_transcript else {}
                messages = transcript_data.get('messages', [])
                transcript_text = '\n'.join([
                    f"{msg['role'].upper()}: {msg['content']}"
                    for msg in messages
                ]) or self.discussion_notes or ''
            except (json.JSONDecodeError, KeyError):
                transcript_text = self.ai_transcript or self.discussion_notes or ''

            if transcript_text:
                summary = ai_provider.summarize_meeting(transcript_text)

                summary_html = f"""
                <h4>AI-Generated Summary</h4>
                <p><strong>Summary:</strong> {summary.get('summary', '')}</p>

                <p><strong>Key Points:</strong></p>
                <ul>
                    {''.join(f'<li>{point}</li>' for point in summary.get('key_points', []))}
                </ul>

                <p><strong>Action Items:</strong></p>
                <ul>
                    {''.join(f'<li>{action}</li>' for action in summary.get('action_items', []))}
                </ul>
                """

                self.action_items = summary_html

                return {
                    'message': 'Summary generated successfully',
                    'success': True
                }
            else:
                return {
                    'message': 'No transcript available to summarize',
                    'success': False
                }

        except ImportError:
            return {
                'message': 'AI provider not available',
                'success': False
            }
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"AI summary generation failed: {e}")

            return {
                'message': f'Failed to generate summary: {str(e)}',
                'success': False
            }
