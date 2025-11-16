# -*- coding: utf-8 -*-

import requests
import logging
import json
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZaloAPIClient:
    """
    Zalo Official Account API client wrapper.

    Handles all API calls to Zalo OA API v2.0.
    Provides methods for authentication, messaging, user management, etc.
    """

    def __init__(self, env):
        """Initialize API client with Odoo environment"""
        self.env = env

    def _make_request(self, method, endpoint, config, data=None, params=None, headers=None):
        """
        Make HTTP request to Zalo API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            config: zalo.config record
            data: Request body data (for POST/PUT)
            params: URL query parameters
            headers: Additional HTTP headers

        Returns:
            Dict with API response data

        Raises:
            UserError: If API call fails
        """
        # Get valid access token (auto-refresh if needed)
        access_token = config.get_valid_token()

        if not access_token:
            raise UserError(_('No valid access token available. Please connect to Zalo first.'))

        # Build full URL
        base_url = config.api_base_url
        api_version = config.api_version
        url = f"{base_url}/{api_version}/{endpoint}"

        # Prepare headers
        request_headers = {
            'Content-Type': 'application/json',
            'access_token': access_token,
        }
        if headers:
            request_headers.update(headers)

        # Make request
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=30,
            )

            # Parse response
            result = response.json() if response.text else {}

            # Check for API errors
            if response.status_code != 200:
                error_msg = result.get('message', result.get('error', 'Unknown error'))
                _logger.error(f'Zalo API error: {response.status_code} - {error_msg}')
                raise UserError(_('Zalo API error: %s') % error_msg)

            # Check error in response body
            if result.get('error') and result['error'] != 0:
                error_msg = result.get('message', 'Unknown error')
                _logger.error(f'Zalo API error: {error_msg}')
                raise UserError(_('Zalo API error: %s') % error_msg)

            return result

        except requests.exceptions.RequestException as e:
            _logger.error(f'Zalo API request failed: {e}')
            raise UserError(_('Failed to connect to Zalo API: %s') % str(e))

    # ============================================================
    # OAuth & Authentication
    # ============================================================

    def exchange_code_for_token(self, config, code):
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            config: zalo.config record
            code: Authorization code from OAuth callback

        Returns:
            Dict with tokens and expiry info
        """
        url = f"{config.api_base_url}/v4/access_token"

        data = {
            'app_id': config.app_id,
            'app_secret': config.app_secret,
            'code': code,
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            result = response.json()

            if result.get('access_token'):
                return result
            else:
                _logger.error(f'Token exchange failed: {result}')
                return {'error': result.get('message', 'Unknown error')}

        except Exception as e:
            _logger.error(f'Token exchange request failed: {e}')
            return {'error': str(e)}

    def refresh_access_token(self, config):
        """
        Refresh access token using refresh token.

        Args:
            config: zalo.config record

        Returns:
            Dict with new tokens
        """
        url = f"{config.api_base_url}/v4/access_token"

        data = {
            'app_id': config.app_id,
            'refresh_token': config.refresh_token,
            'grant_type': 'refresh_token',
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            result = response.json()

            if result.get('access_token'):
                return result
            else:
                _logger.error(f'Token refresh failed: {result}')
                return {'error': result.get('message', 'Unknown error')}

        except Exception as e:
            _logger.error(f'Token refresh request failed: {e}')
            return {'error': str(e)}

    # ============================================================
    # Official Account Info
    # ============================================================

    def get_oa_profile(self, config):
        """
        Get Official Account profile information.

        Args:
            config: zalo.config record

        Returns:
            Dict with OA profile data
        """
        return self._make_request('GET', 'oa/getoa', config)

    # ============================================================
    # Messaging - Send Messages
    # ============================================================

    def send_text_message(self, config, message_data):
        """
        Send text message to user.

        Args:
            config: zalo.config record
            message_data: Dict with recipient and message content

        Returns:
            Dict with send result
        """
        return self._make_request('POST', 'oa/message', config, data=message_data)

    def send_image_message(self, config, user_id, image_url):
        """
        Send image message to user.

        Args:
            config: zalo.config record
            user_id: Zalo user ID
            image_url: URL of image to send

        Returns:
            Dict with send result
        """
        message_data = {
            'recipient': {
                'user_id': user_id,
            },
            'message': {
                'attachment': {
                    'type': 'template',
                    'payload': {
                        'template_type': 'media',
                        'elements': [{
                            'media_type': 'image',
                            'url': image_url,
                        }],
                    },
                },
            },
        }

        return self._make_request('POST', 'oa/message', config, data=message_data)

    def send_file_message(self, config, user_id, file_url):
        """
        Send file attachment to user.

        Args:
            config: zalo.config record
            user_id: Zalo user ID
            file_url: URL of file to send

        Returns:
            Dict with send result
        """
        message_data = {
            'recipient': {
                'user_id': user_id,
            },
            'message': {
                'attachment': {
                    'type': 'file',
                    'payload': {
                        'url': file_url,
                    },
                },
            },
        }

        return self._make_request('POST', 'oa/message', config, data=message_data)

    # ============================================================
    # User Management
    # ============================================================

    def get_user_profile(self, config, user_id):
        """
        Get Zalo user profile information.

        Args:
            config: zalo.config record
            user_id: Zalo user ID

        Returns:
            Dict with user profile data
        """
        params = {'data': json.dumps({'user_id': user_id})}
        return self._make_request('GET', 'oa/getprofile', config, params=params)

    def get_followers(self, config, offset=0, count=50):
        """
        Get list of OA followers.

        Args:
            config: zalo.config record
            offset: Pagination offset
            count: Number of followers to retrieve

        Returns:
            Dict with followers list
        """
        params = {
            'data': json.dumps({
                'offset': offset,
                'count': count,
            })
        }
        return self._make_request('GET', 'oa/getfollowers', config, params=params)

    # ============================================================
    # Zalo Notification Service (ZNS)
    # ============================================================

    def send_zns_notification(self, config, phone, template_id, template_data):
        """
        Send ZNS template notification.

        Args:
            config: zalo.config record
            phone: Recipient phone number
            template_id: ZNS template ID
            template_data: Dict with template parameters

        Returns:
            Dict with send result
        """
        data = {
            'phone': phone,
            'template_id': template_id,
            'template_data': template_data,
        }

        return self._make_request('POST', 'message/template', config, data=data)

    # ============================================================
    # Webhook Management
    # ============================================================

    def register_webhook(self, config, event_types):
        """
        Register webhook URL with Zalo.

        Args:
            config: zalo.config record
            event_types: List of event types to subscribe to

        Returns:
            Dict with registration result
        """
        data = {
            'url': config.webhook_url,
            'event_types': event_types,
        }

        return self._make_request('POST', 'oa/webhook', config, data=data)

    def unregister_webhook(self, config):
        """
        Unregister webhook from Zalo.

        Args:
            config: zalo.config record

        Returns:
            Dict with unregistration result
        """
        return self._make_request('DELETE', 'oa/webhook', config)


# Factory method for Odoo models
def get_api_client(env):
    """Get ZaloAPIClient instance for Odoo environment"""
    return ZaloAPIClient(env)
