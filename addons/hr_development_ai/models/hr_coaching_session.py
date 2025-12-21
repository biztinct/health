# -*- coding: utf-8 -*-

import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError


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

            # Build coaching prompt with context
            session_type = dict(self._fields['session_type'].selection).get(self.session_type)
            topic = dict(self._fields['topic'].selection).get(self.topic)

            prompt = f"""You are an AI coaching assistant helping with a {session_type} coaching session.
Session Topic: {topic}
Employee: {self.employee_id.name}
Coach: {self.coach_id.name if self.coach_id else 'AI Coach'}

The employee asks: {message}

Provide a supportive, professional coaching response that:
- Addresses their question or concern
- Offers constructive guidance
- Encourages growth and development
- Is specific and actionable

Response:"""

            # Get AI response using generate_text
            response_text = ai_provider.generate_text(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )

            return {
                'response': response_text if response_text else 'I apologize, I could not generate a response at this time.',
                'suggestions': []
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

    def action_open_ai_chat(self):
        """Open AI Chat dialog"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Coaching Chat',
            'res_model': 'hr.coaching.session',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('hr_development_ai.view_coaching_session_ai_chat_dialog').id,
            'target': 'new',
            'context': {'dialog_size': 'large'}
        }

    def action_send_ai_message_from_dialog(self):
        """Send message to AI from dialog and append response to transcript

        This method is called from the dialog's "Send to AI" button.
        It reads the current ai_transcript, sends it to AI, and appends the response.
        """
        self.ensure_one()

        if not self.ai_transcript or not self.ai_transcript.strip():
            raise UserError(_('Please type a message before sending to AI.'))

        try:
            # Parse existing transcript as JSON if possible
            try:
                transcript_data = json.loads(self.ai_transcript)
                messages = transcript_data.get('messages', [])
            except (json.JSONDecodeError, ValueError):
                # If not JSON, treat as plain text - create first user message
                messages = [{
                    'role': 'user',
                    'content': self.ai_transcript.strip(),
                    'timestamp': fields.Datetime.now().isoformat()
                }]

            # Get the last message to send to AI
            if messages:
                last_message = messages[-1]['content']
            else:
                last_message = self.ai_transcript.strip()

            # Send to AI
            result = self.action_send_ai_message(last_message)

            # Append AI response to messages
            messages.append({
                'role': 'assistant',
                'content': result.get('response', 'No response received'),
                'timestamp': fields.Datetime.now().isoformat()
            })

            # Save updated transcript as JSON
            self.ai_transcript = json.dumps({
                'messages': messages,
                'updated_at': fields.Datetime.now().isoformat()
            }, indent=2)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Response Received'),
                    'message': _('The AI coach has responded to your message.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"AI message from dialog failed: {e}")

            raise UserError(_(
                'Failed to send message to AI coach. Please try again.\n\n'
                'Error: %s'
            ) % str(e))
