# -*- coding: utf-8 -*-

import json
from datetime import timedelta
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
        help='Transcript of AI coaching conversation (stored as JSON)'
    )

    # Helper fields for chat dialog
    ai_chat_input = fields.Text(
        string='Your Message',
        help='Type your message to the AI coach here'
    )

    ai_chat_history = fields.Text(
        string='Chat History',
        compute='_compute_ai_chat_history',
        help='Formatted chat conversation history'
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

    # ===================
    # BFSI-Specific Fields
    # ===================
    kpi_context = fields.Text(
        string='KPI Context',
        help='JSON snapshot of performance data at time of session'
    )

    coaching_strategy_id = fields.Many2one(
        'bfsi.coaching.strategy',
        string='Coaching Strategy',
        help='AI-generated strategy used for this session'
    )

    # Related fields from coaching strategy for form display
    strategy_opening_questions = fields.Text(
        related='coaching_strategy_id.opening_questions', string='Opening Questions', readonly=True
    )
    strategy_probing_questions = fields.Text(
        related='coaching_strategy_id.probing_questions', string='Probing Questions', readonly=True
    )
    strategy_closing_questions = fields.Text(
        related='coaching_strategy_id.closing_questions', string='Closing Questions', readonly=True
    )
    strategy_coaching_tips = fields.Text(
        related='coaching_strategy_id.coaching_tips', string='Coaching Tips', readonly=True
    )
    strategy_session_guide = fields.Html(
        related='coaching_strategy_id.session_guide', string='Session Guide', readonly=True
    )

    action_plan_id = fields.Many2one(
        'bfsi.action.plan',
        string='Action Plan',
        help='Action plan created from this session'
    )

    coached_by_type = fields.Selection([
        ('ai_direct', 'AI Direct (Self-Service)'),
        ('ai_assisted', 'AI-Assisted Manager Coaching'),
        ('human', 'Human Only')
    ], string='Coaching Method', default='ai_direct')

    is_bfsi_session = fields.Boolean(
        string='Is BFSI Session',
        default=False,
        help='Whether this is a BFSI performance coaching session'
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True
    )

    ai_suggested_questions = fields.Html(
        string='AI Suggested Questions',
        help='AI-generated coaching questions for the manager to ask during the session'
    )

    @api.depends('ai_transcript')
    def _compute_ai_chat_history(self):
        """Format AI transcript JSON into readable chat history"""
        for record in self:
            if not record.ai_transcript:
                record.ai_chat_history = "No messages yet. Start a conversation with your AI coach!"
                continue

            try:
                # Parse JSON transcript
                transcript_data = json.loads(record.ai_transcript)
                messages = transcript_data.get('messages', [])

                if not messages:
                    record.ai_chat_history = "No messages yet. Start a conversation with your AI coach!"
                    continue

                # Format messages into readable text
                formatted_lines = []
                for msg in messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    timestamp = msg.get('timestamp', '')

                    # Format timestamp if present
                    time_str = ''
                    if timestamp:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = f" [{dt.strftime('%H:%M')}]"
                        except:
                            pass

                    # Format based on role
                    if role == 'user':
                        formatted_lines.append(f"You{time_str}: {content}")
                    elif role == 'assistant':
                        formatted_lines.append(f"AI Coach{time_str}: {content}")
                    else:
                        formatted_lines.append(f"{role.title()}{time_str}: {content}")

                    formatted_lines.append("")  # Blank line between messages

                record.ai_chat_history = "\n".join(formatted_lines)

            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, show as plain text
                record.ai_chat_history = record.ai_transcript or "No messages yet."

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

    def action_suggest_questions(self):
        """Use AI to generate real-time coaching questions based on banker's KPIs and session topic"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            topic = dict(self._fields['topic'].selection).get(self.topic, 'General')

            # Get KPI context
            kpi_context = ''
            if self.kpi_context:
                kpi_context = self.kpi_context
            elif self.employee_id:
                try:
                    context = self.employee_id.get_performance_context_for_ai()
                    kpi_context = json.dumps(context, indent=2, default=str)
                except Exception:
                    kpi_context = 'No KPI data available'

            # Get strategy context if linked
            strategy_context = ''
            if self.coaching_strategy_id:
                strategy = self.coaching_strategy_id
                strategy_context = f"""
EXISTING COACHING STRATEGY:
- Strengths: {strategy.strengths or 'Not analyzed'}
- Improvement Areas: {strategy.improvement_areas or 'Not analyzed'}
- Coaching Themes: {strategy.coaching_themes or 'Not analyzed'}
"""

            prompt = f"""You are an expert sales coaching consultant for a bank. Generate a structured set of coaching questions for a branch manager to use during a coaching session with a banker.

SESSION DETAILS:
- Banker: {self.employee_id.name}
- Topic: {topic}
- Session Type: {dict(self._fields['session_type'].selection).get(self.session_type, 'AI Coaching')}

PERFORMANCE DATA:
{kpi_context or 'No KPI data available'}
{strategy_context}

Generate questions in EXACTLY this HTML format (do NOT use markdown):

<h4>🎯 Opening Questions</h4>
<p>Use these to start the conversation and build rapport</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>🔍 Probing Questions</h4>
<p>Use these to explore root causes and deeper issues</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>💡 Action-Oriented Questions</h4>
<p>Use these to drive commitments and next steps</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>📋 Coaching Tips</h4>
<ul>
<li>Tip text here</li>
</ul>

Generate 3-4 questions per category. Reference the banker's actual performance numbers where possible. Keep questions open-ended and non-judgmental."""

            response_text = ai_provider.generate_text(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7
            )

            if response_text:
                self.ai_suggested_questions = response_text
            else:
                self.ai_suggested_questions = '<p class="text-warning">Could not generate questions. Please try again.</p>'

        except ImportError:
            self.ai_suggested_questions = '<p class="text-danger">AI provider not configured. Please set up an AI provider in Configuration.</p>'
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"AI suggest questions failed: {e}")
            self.ai_suggested_questions = f'<p class="text-danger">Error generating questions: {str(e)}</p>'

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

            # Get transcript text — handle both JSON (legacy) and formatted text
            transcript_text = ''
            if self.ai_transcript:
                try:
                    import json
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                    transcript_text = '\n'.join([
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in messages
                    ])
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Already formatted text — use directly
                    transcript_text = self.ai_transcript

            if not transcript_text:
                transcript_text = self.discussion_notes or ''

            if transcript_text:
                summary = ai_provider.summarize_meeting(transcript_text)

                summary_html = f"""
                <h4>AI-Generated Summary</h4>
                <p><strong>Summary:</strong> {summary.get('summary', '')}</p>

                <p><strong>Key Points:</strong></p>
                <ul>
                    {''.join(f'<li>{point}</li>' for point in summary.get('key_points', []))}
                </ul>

                <p><strong>Recommended Next Steps:</strong></p>
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
        It reads from ai_chat_input, sends to AI, and appends both messages to transcript.
        """
        self.ensure_one()

        # Check if user has typed a message
        if not self.ai_chat_input or not self.ai_chat_input.strip():
            raise UserError(_('Please type a message in the input field before sending to AI.'))

        user_message = self.ai_chat_input.strip()

        try:
            # Parse existing transcript - handle both JSON and formatted text
            messages = []
            if self.ai_transcript:
                try:
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                except (json.JSONDecodeError, ValueError):
                    # Parse formatted text back into messages
                    messages = self._parse_formatted_transcript(self.ai_transcript)

            # Add user's message
            messages.append({
                'role': 'user',
                'content': user_message,
                'timestamp': fields.Datetime.now().isoformat()
            })

            # Send to AI
            result = self.action_send_ai_message(user_message)

            # Add AI response
            messages.append({
                'role': 'assistant',
                'content': result.get('response', 'No response received'),
                'timestamp': fields.Datetime.now().isoformat()
            })

            # Save as formatted readable text
            self.ai_transcript = self._format_chat_transcript(messages)

            # Clear the input field
            self.ai_chat_input = ''

            # Return action to reload the dialog form
            return {
                'type': 'ir.actions.act_window',
                'name': _('AI Coaching Chat'),
                'res_model': 'hr.coaching.session',
                'res_id': self.id,
                'view_mode': 'form',
                'views': [[self.env.ref('hr_development_ai.view_coaching_session_ai_chat_dialog').id, 'form']],
                'target': 'new',
                'context': {'dialog_size': 'large'}
            }

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"AI message from dialog failed: {e}")

            raise UserError(_(
                'Failed to send message to AI coach. Please try again.\n\n'
                'Error: %s'
            ) % str(e))

    def _format_chat_transcript(self, messages):
        """Format chat messages list into readable text"""
        if not messages:
            return ''
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(f"👤 You:\n{content}")
            elif role == 'assistant':
                lines.append(f"🤖 AI Coach:\n{content}")
            else:
                lines.append(f"{role}:\n{content}")
        return '\n\n─────────────────────\n\n'.join(lines)

    def _parse_formatted_transcript(self, text):
        """Parse formatted chat transcript text back into messages list"""
        if not text:
            return []
        separator = '─────────────────────'
        blocks = [b.strip() for b in text.split(separator) if b.strip()]
        messages = []
        for block in blocks:
            if block.startswith('👤 You:'):
                content = block[len('👤 You:'):].strip()
                messages.append({'role': 'user', 'content': content})
            elif block.startswith('🤖 AI Coach:'):
                content = block[len('🤖 AI Coach:'):].strip()
                messages.append({'role': 'assistant', 'content': content})
            else:
                # Fallback
                messages.append({'role': 'assistant', 'content': block})
        return messages

    # ===================
    # BFSI Methods
    # ===================
    def action_capture_kpi_context(self):
        """Capture current KPI context for the session"""
        self.ensure_one()

        context = self.employee_id.get_performance_context_for_ai()
        self.kpi_context = json.dumps(context, indent=2, default=str)
        self.is_bfsi_session = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('KPI Context Captured'),
                'message': _('Performance context has been captured for this session.'),
                'type': 'success',
            }
        }

    def action_create_action_plan(self):
        """Create an action plan from this coaching session"""
        self.ensure_one()

        if self.action_plan_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Action Plan'),
                'res_model': 'bfsi.action.plan',
                'res_id': self.action_plan_id.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
            }

        # Create new action plan
        plan = self.env['bfsi.action.plan'].create({
            'coaching_session_id': self.id,
            'employee_id': self.employee_id.id,
            'manager_id': self.coach_id.id if self.coach_id else False,
            'target_date': fields.Date.today() + timedelta(days=14),  # 2 weeks default
        })

        self.action_plan_id = plan.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Action Plan'),
            'res_model': 'bfsi.action.plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    def action_generate_action_items_ai(self):
        """Use AI to generate action items from the coaching conversation"""
        self.ensure_one()

        if not self.action_plan_id:
            self.action_create_action_plan()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get conversation transcript
            transcript = ''
            if self.ai_transcript:
                try:
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                    transcript = '\n'.join([
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in messages
                    ])
                except (json.JSONDecodeError, ValueError):
                    # Already formatted text — use directly
                    transcript = self.ai_transcript

            if not transcript:
                raise UserError(_('No coaching conversation found. Please have a conversation first.'))

            # Get KPI context
            kpi_context = self.kpi_context or '{}'

            prompt = f"""Based on the following coaching conversation and performance context, generate specific action items.

COACHING CONVERSATION:
{transcript}

PERFORMANCE CONTEXT:
{kpi_context}

Generate 3-5 specific, measurable action items in JSON format:
{{
    "action_items": [
        {{
            "name": "Action item title",
            "description": "Detailed description",
            "kpi_category": "input|behavior|output|outcome",
            "specific_kpi": "dials|connects|script_adherence|etc",
            "success_criteria": "How to measure success",
            "priority": "high|medium|low"
        }}
    ]
}}

Focus on:
1. SPECIFIC behaviors the banker can control
2. Measurable outcomes within 2 weeks
3. Addressing the root causes of performance gaps
"""

            response = ai_provider.generate_text(prompt, max_tokens=800, temperature=0.5)

            # Parse response
            try:
                data = json.loads(response)
            except:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise UserError(_('Could not parse AI response.'))

            # Valid selection values for bfsi.action.plan.item
            valid_kpi_categories = {'input', 'behavior', 'output', 'outcome'}
            valid_specific_kpis = {
                'dials', 'connects', 'meetings', 'script_adherence',
                'objection_handling', 'need_analysis', 'product_knowledge',
                'conversion', 'revenue', 'customer_satisfaction', 'other'
            }
            valid_priorities = {'high', 'medium', 'low'}

            # Create action items
            items_created = 0
            for idx, item in enumerate(data.get('action_items', []), 1):
                kpi_cat = item.get('kpi_category', '')
                spec_kpi = item.get('specific_kpi', '')
                priority = item.get('priority', 'medium')

                self.env['bfsi.action.plan.item'].create({
                    'action_plan_id': self.action_plan_id.id,
                    'sequence': idx * 10,
                    'name': item.get('name', 'Action Item'),
                    'description': item.get('description', ''),
                    'kpi_category': kpi_cat if kpi_cat in valid_kpi_categories else False,
                    'specific_kpi': spec_kpi if spec_kpi in valid_specific_kpis else 'other',
                    'success_criteria': item.get('success_criteria', ''),
                    'priority': priority if priority in valid_priorities else 'medium',
                })
                items_created += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action Items Generated'),
                    'message': _('%d action items have been created.') % items_created,
                    'type': 'success',
                }
            }

        except Exception as e:
            raise UserError(_('Failed to generate action items: %s') % str(e))

    def _get_bfsi_coaching_prompt(self, message):
        """Build enhanced coaching prompt with BFSI context"""
        self.ensure_one()

        session_type = dict(self._fields['session_type'].selection).get(self.session_type)
        topic = dict(self._fields['topic'].selection).get(self.topic)

        # Get performance context
        kpi_context = ''
        if self.kpi_context:
            kpi_context = f"\nPERFORMANCE CONTEXT:\n{self.kpi_context}"
        elif self.is_bfsi_session:
            context = self.employee_id.get_performance_context_for_ai()
            kpi_context = f"\nPERFORMANCE CONTEXT:\n{json.dumps(context, indent=2, default=str)}"

        # Get strategy if available
        strategy_context = ''
        if self.coaching_strategy_id:
            strategy_context = f"""
COACHING STRATEGY:
{self.coaching_strategy_id.ai_strategy or ''}

COACHING THEMES:
{self.coaching_strategy_id.coaching_themes or '[]'}
"""

        prompt = f"""You are an expert AI sales performance coach for a bank.

SESSION DETAILS:
- Type: {session_type}
- Topic: {topic}
- Banker: {self.employee_id.name}
- Coach: {self.coach_id.name if self.coach_id else 'AI Coach'}
{kpi_context}
{strategy_context}

The banker asks: {message}

Provide a supportive, professional coaching response that:
1. References their actual performance numbers when relevant
2. Focuses on specific behaviors they can improve
3. Offers 1-2 actionable next steps
4. Is encouraging but honest about areas for improvement
5. Asks a follow-up question to deepen the coaching conversation

Keep response under 200 words unless they ask for detailed guidance.

Response:"""

        return prompt
