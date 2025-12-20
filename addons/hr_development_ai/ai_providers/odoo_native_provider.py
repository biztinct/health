# -*- coding: utf-8 -*-

import json
import logging
import re
from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)


class OdooNativeAIProvider(BaseAIProvider):
    """
    Odoo 19 Native AI provider
    Uses built-in Odoo AI features (AI Server Actions, AI Text Fields)
    Fallback to rule-based approaches when AI not available
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.odoo_env = config.get('env') if config else None

    def generate_text(self, prompt, max_tokens=500, temperature=0.7, **kwargs):
        """
        Generate text using Odoo 19 AI features
        Falls back to template-based generation if AI unavailable
        """
        # TODO: When Odoo 19 AI Server Actions are available, use them here
        # For now, use rule-based templates

        _logger.info("Using Odoo Native AI (template-based fallback)")

        if "coaching" in prompt.lower():
            return self._generate_coaching_template(prompt)
        elif "skill" in prompt.lower():
            return self._generate_skills_template(prompt)
        elif "summary" in prompt.lower() or "meeting" in prompt.lower():
            return self._generate_summary_template(prompt)
        else:
            return "Generated response (Odoo Native AI)"

    def analyze_sentiment(self, text):
        """Analyze sentiment using rule-based approach"""
        text_lower = text.lower()

        # Simple keyword-based sentiment
        positive_keywords = ['good', 'great', 'excellent', 'happy', 'satisfied', 'love', 'amazing', 'wonderful']
        negative_keywords = ['bad', 'poor', 'terrible', 'unhappy', 'disappointed', 'hate', 'awful', 'horrible']

        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.5 + (positive_count * 0.1), 0.95)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = max(0.5 - (negative_count * 0.1), 0.05)
        else:
            sentiment = "neutral"
            score = 0.5

        return {"sentiment": sentiment, "score": score}

    def extract_skills(self, text, skill_taxonomy=None):
        """Extract skills using keyword matching"""
        extracted_skills = []

        if not skill_taxonomy:
            # Default common skills
            skill_taxonomy = [
                'Python', 'JavaScript', 'Leadership', 'Communication',
                'Project Management', 'Data Analysis', 'SQL', 'Machine Learning'
            ]

        text_lower = text.lower()

        for skill in skill_taxonomy:
            if skill.lower() in text_lower:
                # Calculate confidence based on context
                confidence = 0.8 if f"{skill.lower()} " in text_lower else 0.6
                extracted_skills.append({
                    "skill": skill,
                    "confidence": confidence
                })

        return extracted_skills

    def generate_coaching_nudge(self, context):
        """Generate coaching nudge using templates"""
        situation = context.get('situation', 'general')
        employee_name = context.get('employee_name', 'Employee')

        templates = {
            'missed_deadline': {
                "message": f"Hi {employee_name}, it looks like a deadline was missed. Let's review what happened and create a plan to prevent this in the future.",
                "action_items": [
                    "Review task priorities and time estimates",
                    "Schedule a brief check-in to discuss blockers"
                ],
                "priority": "high"
            },
            'upcoming_meeting': {
                "message": f"Hi {employee_name}, you have an important meeting coming up. Take a few minutes to prepare key discussion points.",
                "action_items": [
                    "Review meeting agenda and objectives",
                    "Prepare questions and talking points"
                ],
                "priority": "medium"
            },
            'skill_gap_detected': {
                "message": f"Hi {employee_name}, we've identified an opportunity to develop new skills that align with your career goals.",
                "action_items": [
                    "Review recommended learning paths",
                    "Set aside time for skill development"
                ],
                "priority": "medium"
            },
            'general': {
                "message": f"Hi {employee_name}, keep up the great work! Regular reflection on your progress helps continuous improvement.",
                "action_items": [
                    "Review recent accomplishments",
                    "Identify areas for growth"
                ],
                "priority": "low"
            }
        }

        return templates.get(situation, templates['general'])

    def recommend_learning(self, employee_skills, job_requirements, available_courses):
        """Recommend learning using rule-based matching"""
        recommendations = []

        # Build skills gap dictionary
        employee_skill_dict = {s['skill']: s.get('level', 0) for s in employee_skills}
        required_skill_dict = {s['skill']: s.get('level', 5) for s in job_requirements}

        gaps = {}
        for skill, required_level in required_skill_dict.items():
            current_level = employee_skill_dict.get(skill, 0)
            if current_level < required_level:
                gaps[skill] = required_level - current_level

        # Match courses to gaps
        for course in available_courses:
            course_skills = course.get('skills', [])
            relevance_score = 0

            for skill in course_skills:
                if skill in gaps:
                    relevance_score += gaps[skill] * 0.3

            if relevance_score > 0:
                recommendations.append({
                    "course_id": course.get('id'),
                    "relevance_score": min(relevance_score, 0.99),
                    "reason": f"Helps close skill gaps in: {', '.join([s for s in course_skills if s in gaps])}"
                })

        # Sort by relevance
        recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
        return recommendations[:5]

    def match_mentor(self, mentee_profile, potential_mentors):
        """Match mentor using rule-based scoring"""
        matches = []

        mentee_skills = set(s['skill'] for s in mentee_profile.get('skills', []))
        mentee_goals = set(mentee_profile.get('career_goals', []))

        for mentor in potential_mentors:
            score = 0
            reasons = []

            mentor_skills = set(s['skill'] for s in mentor.get('skills', []))
            skill_overlap = mentee_skills & mentor_skills

            if skill_overlap:
                score += len(skill_overlap) * 0.2
                reasons.append(f"Expertise in {', '.join(list(skill_overlap)[:3])}")

            mentor_career = set(mentor.get('career_path', []))
            career_overlap = mentee_goals & mentor_career

            if career_overlap:
                score += 0.3
                reasons.append("Similar career trajectory")

            if mentor.get('mentoring_capacity', 0) > 0:
                score += 0.1
                reasons.append("Available for mentoring")

            if score > 0:
                matches.append({
                    "mentor_id": mentor.get('id'),
                    "match_score": min(score, 0.99),
                    "reason": "; ".join(reasons)
                })

        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches[:5]

    def summarize_meeting(self, transcript):
        """Summarize meeting using text extraction"""
        lines = transcript.split('\n')

        # Extract key points (lines with certain keywords)
        key_point_keywords = ['decided', 'agreed', 'conclusion', 'important', 'key', 'critical']
        action_keywords = ['action', 'todo', 'will', 'should', 'must', 'need to']
        decision_keywords = ['decided', 'agreed', 'approved', 'rejected']

        key_points = []
        action_items = []
        decisions = []

        for line in lines:
            line_lower = line.lower()

            if any(kw in line_lower for kw in key_point_keywords):
                key_points.append(line.strip())

            if any(kw in line_lower for kw in action_keywords):
                action_items.append(line.strip())

            if any(kw in line_lower for kw in decision_keywords):
                decisions.append(line.strip())

        return {
            "summary": f"Meeting covered {len(lines)} discussion points with {len(action_items)} action items identified.",
            "key_points": key_points[:5],
            "action_items": action_items[:5],
            "decisions": decisions[:5]
        }

    def extract_knowledge(self, project_data):
        """Extract knowledge using pattern matching"""
        knowledge = []

        project_name = project_data.get('name', 'Project')
        description = project_data.get('description', '')
        tasks = project_data.get('tasks', [])

        # Extract lessons from description
        if 'lesson' in description.lower() or 'learned' in description.lower():
            knowledge.append({
                "title": f"Lessons from {project_name}",
                "description": description[:500],
                "type": "lesson_learned",
                "confidence": 0.7,
                "related_skills": []
            })

        # Extract decisions
        if 'decided' in description.lower() or 'decision' in description.lower():
            knowledge.append({
                "title": f"Key decisions in {project_name}",
                "description": description[:500],
                "type": "decision",
                "confidence": 0.7,
                "related_skills": []
            })

        # Extract best practices from completed tasks
        completed_tasks = [t for t in tasks if t.get('stage') == 'done']
        if len(completed_tasks) > 5:
            knowledge.append({
                "title": f"Best practices from {project_name}",
                "description": f"Successfully completed {len(completed_tasks)} tasks using established methodologies.",
                "type": "best_practice",
                "confidence": 0.6,
                "related_skills": []
            })

        return knowledge

    def is_available(self):
        """Odoo Native AI is always available (uses fallbacks)"""
        return True

    def _generate_coaching_template(self, prompt):
        return "Focus on continuous improvement and regular skill development."

    def _generate_skills_template(self, prompt):
        return '["Python", "Leadership", "Communication"]'

    def _generate_summary_template(self, prompt):
        return '{"summary": "Meeting summary", "key_points": [], "action_items": [], "decisions": []}'
