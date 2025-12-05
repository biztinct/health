# -*- coding: utf-8 -*-

import requests
import logging
from datetime import datetime, timedelta
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIP24hAPI:
    """
    VoIP24h API Client.

    Handles all API communication with VoIP24h service including
    authentication, call history retrieval, and recording downloads.
    """

    def __init__(self, config):
        """
        Initialize API client with configuration.

        Args:
            config: voip.config record
        """
        self.config = config
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.account_id = config.account_id
        self.base_url = config.api_base_url
        self.session = requests.Session()

    def _get_headers(self):
        """Get headers for API requests"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Add auth token if available
        if self.config.access_token:
            headers['Authorization'] = f'Bearer {self.config.access_token}'

        return headers

    def authenticate(self):
        """
        Authenticate with VoIP24h API and get access token.

        Returns:
            dict: Authentication response with token
        """
        try:
            url = f"{self.base_url}/auth/login"
            payload = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'account_id': self.account_id,
            }

            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Update config with token
            self.config.write({
                'access_token': data.get('access_token'),
                'token_expires_at': datetime.now() + timedelta(seconds=data.get('expires_in', 3600)),
                'token_type': data.get('token_type', 'Bearer'),
                'state': 'connected',
                'error_message': False,
            })

            _logger.info('VoIP24h authentication successful')
            return data

        except requests.exceptions.RequestException as e:
            _logger.error(f'VoIP24h authentication failed: {e}', exc_info=True)
            self.config.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise UserError(f'Authentication failed: {e}')

    def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.config.access_token:
            self.authenticate()
        elif self.config.token_expires_at and self.config.token_expires_at < datetime.now():
            # Token expired, re-authenticate
            self.authenticate()

    def get_call_history(self, from_date=None, to_date=None, limit=100, offset=0):
        """
        Fetch call history from VoIP24h.

        Args:
            from_date: Start date for call history
            to_date: End date for call history
            limit: Maximum number of calls to retrieve
            offset: Offset for pagination

        Returns:
            list: List of call records
        """
        try:
            self._ensure_authenticated()

            url = f"{self.base_url}/calls/history"
            params = {
                'account_id': self.account_id,
                'limit': limit,
                'offset': offset,
            }

            if from_date:
                params['from_date'] = from_date.isoformat()
            if to_date:
                params['to_date'] = to_date.isoformat()

            response = self.session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            calls = data.get('data', [])

            _logger.info(f'Retrieved {len(calls)} call records from VoIP24h')
            return calls

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to fetch call history: {e}', exc_info=True)
            raise UserError(f'Failed to fetch call history: {e}')

    def get_call_details(self, call_id):
        """
        Get detailed information for a specific call.

        Args:
            call_id: Unique call identifier

        Returns:
            dict: Call details
        """
        try:
            self._ensure_authenticated()

            url = f"{self.base_url}/calls/{call_id}"
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to fetch call details: {e}', exc_info=True)
            raise UserError(f'Failed to fetch call details: {e}')

    def get_recording_url(self, call_id):
        """
        Get recording download URL for a call.

        Args:
            call_id: Unique call identifier

        Returns:
            str: Recording URL
        """
        try:
            self._ensure_authenticated()

            url = f"{self.base_url}/calls/{call_id}/recording"
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            return data.get('recording_url')

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to get recording URL: {e}', exc_info=True)
            return None

    def download_recording(self, recording_url):
        """
        Download recording file from URL.

        Args:
            recording_url: URL to download recording from

        Returns:
            bytes: Recording file data
        """
        try:
            response = self.session.get(recording_url, timeout=60)
            response.raise_for_status()

            return response.content

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to download recording: {e}', exc_info=True)
            raise UserError(f'Failed to download recording: {e}')

    def initiate_call(self, from_extension, to_number):
        """
        Initiate outbound call via click-to-dial.

        Args:
            from_extension: Extension number to call from
            to_number: Phone number to call

        Returns:
            dict: Call initiation response
        """
        try:
            self._ensure_authenticated()

            url = f"{self.base_url}/calls/initiate"
            payload = {
                'account_id': self.account_id,
                'from_extension': from_extension,
                'to_number': to_number,
            }

            response = self.session.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            _logger.info(f'Initiated call from {from_extension} to {to_number}')
            return response.json()

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to initiate call: {e}', exc_info=True)
            raise UserError(f'Failed to initiate call: {e}')

    def get_extensions(self):
        """
        Get list of all extensions/lines.

        Returns:
            list: List of extensions
        """
        try:
            self._ensure_authenticated()

            url = f"{self.base_url}/extensions"
            params = {'account_id': self.account_id}

            response = self.session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            return data.get('data', [])

        except requests.exceptions.RequestException as e:
            _logger.error(f'Failed to fetch extensions: {e}', exc_info=True)
            return []

    def test_connection(self):
        """
        Test API connection and authentication.

        Returns:
            bool: True if connection successful
        """
        try:
            self.authenticate()
            return True
        except Exception as e:
            _logger.error(f'Connection test failed: {e}')
            return False
