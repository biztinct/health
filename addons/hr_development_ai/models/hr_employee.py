# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    # Skills
    skill_ids = fields.One2many(
        'hr.employee.skill',
        'employee_id',
        string='Skills'
    )

    skill_count = fields.Integer(
        string='Skills',
        compute='_compute_skill_count',
        store=True
    )

    avg_skill_proficiency = fields.Float(
        string='Avg. Proficiency',
        compute='_compute_avg_proficiency',
        store=True
    )

    # Dummy field for skills matrix widget attachment
    skills_matrix_data = fields.Text(
        string='Skills Matrix Data',
        help='Internal field for skills matrix visualization widget'
    )

    # Development
    development_plan_ids = fields.One2many(
        'hr.development.plan',
        'employee_id',
        string='Development Plans'
    )

    active_development_plan_id = fields.Many2one(
        'hr.development.plan',
        string='Active Plan',
        compute='_compute_active_plan',
        store=True
    )

    learning_enrollment_ids = fields.One2many(
        'hr.learning.enrollment',
        'employee_id',
        string='Learning Enrollments'
    )

    earned_certification_ids = fields.One2many(
        'hr.certification',
        'employee_id',
        string='Earned Certifications'
    )

    earned_certification_count = fields.Integer(
        string='Certifications',
        compute='_compute_certification_count',
        store=True
    )

    # Coaching
    coaching_session_ids = fields.One2many(
        'hr.coaching.session',
        'employee_id',
        string='Coaching Sessions'
    )

    coaching_nudge_ids = fields.One2many(
        'hr.coaching.nudge',
        'employee_id',
        string='Coaching Nudges'
    )

    unread_nudge_count = fields.Integer(
        string='Unread Nudges',
        compute='_compute_unread_nudges'
    )

    # Mentorship
    mentor_relationship_ids = fields.One2many(
        'hr.mentorship',
        'mentor_id',
        string='Mentoring'
    )

    mentee_relationship_ids = fields.One2many(
        'hr.mentorship',
        'mentee_id',
        string='Being Mentored'
    )

    is_mentor = fields.Boolean(
        string='Available as Mentor',
        default=False,
        help='This employee is available to mentor others'
    )

    mentoring_capacity = fields.Integer(
        string='Mentoring Capacity',
        default=3,
        help='Maximum number of mentees'
    )

    # Knowledge
    knowledge_expertise_ids = fields.Many2many(
        'hr.knowledge.node',
        'knowledge_node_expert_rel',
        'employee_id',
        'node_id',
        string='Knowledge Expertise'
    )

    # Career
    career_path_id = fields.Many2one(
        'hr.career.path',
        string='Career Path',
        help='Employee current career path'
    )

    career_goals = fields.Html(string='Career Goals')

    @api.depends('skill_ids')
    def _compute_skill_count(self):
        for employee in self:
            employee.skill_count = len(employee.skill_ids)

    @api.depends('skill_ids.proficiency_score')
    def _compute_avg_proficiency(self):
        for employee in self:
            if employee.skill_ids:
                employee.avg_skill_proficiency = sum(employee.skill_ids.mapped('proficiency_score')) / len(employee.skill_ids)
            else:
                employee.avg_skill_proficiency = 0.0

    @api.depends('earned_certification_ids')
    def _compute_certification_count(self):
        for employee in self:
            employee.earned_certification_count = len(employee.earned_certification_ids.filtered(lambda c: not c.is_expired))

    @api.depends('development_plan_ids.state')
    def _compute_active_plan(self):
        for employee in self:
            active_plan = employee.development_plan_ids.filtered(lambda p: p.state == 'active')
            employee.active_development_plan_id = active_plan[0] if active_plan else False

    def _compute_unread_nudges(self):
        for employee in self:
            employee.unread_nudge_count = len(employee.coaching_nudge_ids.filtered(lambda n: n.state == 'sent'))

    def action_view_skills(self):
        """View employee skills"""
        self.ensure_one()
        return {
            'name': f'Skills - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.skill',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def action_view_development_plan(self):
        """View development plan"""
        self.ensure_one()
        if self.active_development_plan_id:
            return {
                'name': 'Development Plan',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.development.plan',
                'view_mode': 'form',
                'res_id': self.active_development_plan_id.id
            }
        else:
            return {
                'name': 'Create Development Plan',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.development.plan',
                'view_mode': 'form',
                'context': {'default_employee_id': self.id},
                'target': 'new'
            }

    def action_infer_skills_ai(self):
        """Run AI skills inference"""
        self.ensure_one()

        # Run inference
        inference_engine = self.env['hr.skills.inference.engine']
        results = inference_engine.infer_skills_for_employee(self.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Skills Inference Complete',
                'message': f'Inferred {len(results)} skills from your work history',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_analyze_skill_gaps(self):
        """Analyze skill gaps for current job"""
        self.ensure_one()

        if not self.job_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Job Position',
                    'message': 'Employee must have a job position assigned',
                    'type': 'warning',
                }
            }

        # Run gap analysis
        gap_model = self.env['hr.skill.gap']
        analysis = gap_model.analyze_employee_for_job(self.id, self.job_id.id)

        # Show results
        return {
            'name': 'Skill Gap Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.skill.gap',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id), ('job_id', '=', self.job_id.id)],
            'context': {
                'search_default_major_gaps': 1  # Filter for major gaps
            }
        }

    def action_view_coaching_nudges(self):
        """View coaching nudges"""
        self.ensure_one()
        return {
            'name': 'Coaching Nudges',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.nudge',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def get_skills_matrix_data(self):
        """Get employee skills organized by category for matrix visualization

        Returns:
            dict: Skills data organized by categories
        """
        self.ensure_one()

        # Get all employee skills with their current and target levels
        skills_data = []
        categories_set = set()

        for skill in self.skill_ids:
            # Get current proficiency (1-5 scale)
            current_level = int(skill.proficiency_score / 20) if skill.proficiency_score else 0  # Convert 0-100 to 0-5
            current_level = max(1, min(5, current_level))  # Ensure in 1-5 range

            # Get target level (from development plan objectives or default to one level above current)
            target_level = current_level + 1 if current_level < 5 else 5

            # Check if there's a specific target in development plans
            if self.active_development_plan_id:
                # Look for objectives related to this skill
                for objective in self.active_development_plan_id.objective_ids:
                    if objective.skill_id and objective.skill_id.id == skill.skill_id.id:
                        # Could define target level in objective metadata
                        # For now, use a reasonable default
                        target_level = min(5, current_level + 2)
                        break

            # Get category name
            category_name = skill.skill_id.category_id.name if skill.skill_id.category_id else 'Uncategorized'
            categories_set.add(category_name)

            skills_data.append({
                'id': skill.id,
                'name': skill.skill_id.name,
                'category': category_name,
                'current_level': current_level,
                'target_level': target_level,
                'proficiency_score': skill.proficiency_score,
            })

        return {
            'categories': sorted(list(categories_set)),
            'skills': skills_data
        }
