# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
import json
import logging

_logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.
    All AI providers (Llama, OpenAI, Odoo Native, etc.) must implement this interface.
    """

    def __init__(self, config=None):
        """
        Initialize provider with configuration

        Args:
            config: Configuration dict or record with provider-specific settings
        """
        self.config = config or {}
        self.logger = _logger

    @abstractmethod
    def generate_text(self, prompt, max_tokens=500, temperature=0.7, **kwargs):
        """
        Generate text completion from prompt

        Args:
            prompt (str): Input prompt text
            max_tokens (int): Maximum tokens to generate
            temperature (float): Sampling temperature (0-1)
            **kwargs: Provider-specific parameters

        Returns:
            str: Generated text
        """
        pass

    @abstractmethod
    def analyze_sentiment(self, text):
        """
        Analyze sentiment of text

        Args:
            text (str): Text to analyze

        Returns:
            dict: {'sentiment': 'positive'|'negative'|'neutral', 'score': float}
        """
        pass

    @abstractmethod
    def extract_skills(self, text, skill_taxonomy=None):
        """
        Extract skills mentioned in text

        Args:
            text (str): Text to analyze (job description, task, etc.)
            skill_taxonomy (list): Optional list of known skills to match against

        Returns:
            list: [{'skill': 'Python', 'confidence': 0.95}, ...]
        """
        pass

    @abstractmethod
    def generate_coaching_nudge(self, context):
        """
        Generate personalized coaching suggestion

        Args:
            context (dict): Context data including:
                - employee_name
                - situation (missed_deadline, upcoming_meeting, skill_gap_detected, etc.)
                - relevant_data (KPIs, tasks, goals, etc.)
                - tone (supportive, motivational, direct)

        Returns:
            dict: {
                'message': 'Coaching suggestion text',
                'action_items': ['Action 1', 'Action 2'],
                'priority': 'high'|'medium'|'low'
            }
        """
        pass

    @abstractmethod
    def recommend_learning(self, employee_skills, job_requirements, available_courses):
        """
        Recommend learning paths based on skills gap

        Args:
            employee_skills (list): [{'skill': 'Python', 'level': 3}, ...]
            job_requirements (list): [{'skill': 'Python', 'level': 5}, ...]
            available_courses (list): [{'id': 1, 'name': 'Advanced Python', 'skills': [...]}, ...]

        Returns:
            list: Ranked list of recommended course IDs with reasoning
        """
        pass

    @abstractmethod
    def match_mentor(self, mentee_profile, potential_mentors):
        """
        AI-powered mentor matching

        Args:
            mentee_profile (dict): Mentee skills, goals, preferences
            potential_mentors (list): List of mentor profiles

        Returns:
            list: Ranked list of mentor IDs with match scores
        """
        pass

    @abstractmethod
    def summarize_meeting(self, transcript):
        """
        Summarize meeting transcript

        Args:
            transcript (str): Meeting transcript text

        Returns:
            dict: {
                'summary': 'Brief summary',
                'key_points': ['Point 1', 'Point 2'],
                'action_items': ['Action 1', 'Action 2'],
                'decisions': ['Decision 1']
            }
        """
        pass

    @abstractmethod
    def extract_knowledge(self, project_data):
        """
        Extract knowledge nodes from project/task data

        Args:
            project_data (dict): Project information including tasks, outcomes

        Returns:
            list: [
                {
                    'title': 'Knowledge title',
                    'description': 'Description',
                    'type': 'concept'|'decision'|'best_practice'|'lesson_learned',
                    'confidence': 0.85,
                    'related_skills': ['skill1', 'skill2']
                },
                ...
            ]
        """
        pass

    def is_available(self):
        """
        Check if provider is available and configured

        Returns:
            bool: True if provider can be used
        """
        return True

    def test_connection(self):
        """
        Test connection to AI service

        Returns:
            dict: {'success': bool, 'message': str, 'latency_ms': float}
        """
        try:
            start_time = self._get_current_time_ms()
            response = self.generate_text("Test connection", max_tokens=10)
            latency = self._get_current_time_ms() - start_time

            return {
                'success': True,
                'message': 'Connection successful',
                'latency_ms': latency,
                'response': response
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'latency_ms': 0
            }

    def _get_current_time_ms(self):
        """Helper to get current time in milliseconds"""
        import time
        return int(time.time() * 1000)

    def _parse_json_response(self, text):
        """
        Parse JSON from AI response, handling markdown code blocks

        Args:
            text (str): AI response that may contain JSON

        Returns:
            dict: Parsed JSON data
        """
        try:
            # Try direct JSON parse
            return json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # Try finding first { to last }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])

            raise ValueError(f"Could not parse JSON from response: {text[:100]}...")
