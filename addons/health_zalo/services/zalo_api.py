# -*- coding: utf-8 -*-

import requests
import logging
import json
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# CC-D (defect Z8). The OAuth endpoints do NOT live on the OA API host: token
# exchange and refresh are `oauth.zaloapp.com/v4/oa/access_token` and the app
# secret travels in a `secret_key` HEADER, never in the body and never in the
# URL. The old code posted to `{api_base_url}/v4/access_token` with the secret
# in the JSON body (exchange) or no secret at all (refresh) — neither call
# could ever have worked.
ZALO_OAUTH_TOKEN_URL = 'https://oauth.zaloapp.com/v4/oa/access_token'
HTTP_TIMEOUT = 30


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

    def _token_request(self, config, payload):
        """POST the OAuth token endpoint: form body, secret in the HEADER.

        Never logs the payload — it carries a refresh token or an
        authorization code on every call.
        """
        app_secret = config.sudo().app_secret or ''
        if not app_secret:
            return {'error': 'no app secret configured'}
        headers = {'secret_key': app_secret}
        data = dict(payload, app_id=config.app_id)
        try:
            response = requests.post(ZALO_OAUTH_TOKEN_URL, data=data,
                                     headers=headers, timeout=HTTP_TIMEOUT)
            result = response.json() if response.text else {}
        except Exception as e:  # noqa: BLE001 — network/parse
            _logger.warning('Zalo token request failed: %s', e)
            return {'error': str(e)}
        if result.get('access_token'):
            return result
        _logger.warning('Zalo refused a token request (grant_type=%s)',
                        payload.get('grant_type'))
        return {'error': (result.get('error_description')
                          or result.get('message')
                          or result.get('error') or 'Unknown error')}

    def exchange_code_for_token(self, config, code):
        """
        Exchange authorization code for access/refresh tokens.

        LEGACY fallback only: the Channel Center's PKCE flow
        (``care.channel.oauth.session`` + ``ZaloAdapter``) is the supported
        path, and this one is never reached from the UI any more.
        """
        return self._token_request(config, {
            'grant_type': 'authorization_code',
            'code': code,
        })

    def refresh_access_token(self, config):
        """
        Refresh access token using refresh token.

        Only used for a config with NO framework connection: a linked config
        refreshes through ``ZaloAdapter.refresh_authorization`` so the
        rotation happens under a row lock and is persisted on an independent
        cursor before anything uses it.
        """
        refresh_token = config._effective_refresh_token()
        if not refresh_token:
            return {'error': 'No refresh token available'}
        return self._token_request(config, {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        })

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

        **The signature and the return contract are frozen** — ten consumer
        modules call exactly this, and every one of their tests patches it.
        CC-D adds only bookkeeping around it: a send Zalo accepted is the ONLY
        honest proof that ZNS works for this Official Account, so success
        flips the connection's ``outbound_ok`` and ``provider_approvals``
        checks and failure records a redacted reason. None of that may change
        what the caller sees, and none of it may raise on its own.
        """
        data = {
            'phone': phone,
            'template_id': template_id,
            'template_data': template_data,
        }

        connection = config.sudo()._connection() if config else False
        try:
            result = self._make_request('POST', 'message/template', config,
                                        data=data)
        except Exception as exc:  # noqa: BLE001 — re-raised untouched below
            if connection:
                auth = any(marker in str(exc).lower()
                           for marker in ('401', 'unauthorized',
                                          'access token', 'invalid token'))
                connection._note_send_failure(exc, auth_failure=auth)
            raise
        if connection:
            connection._note_outbound()
            # Template approval is a human Zalo review; an accepted send is
            # the evidence, and there is no attestation button anywhere.
            # Savepoint-isolated: bookkeeping never breaks a real message
            # (a caught IntegrityError would still poison the caller's
            # transaction without it — ledger §5.55).
            try:
                with self.env.cr.savepoint():
                    self.env['care.channel.readiness.check'].sudo() \
                        .upsert_check(connection, 'provider_approvals', 'pass')
            except Exception:  # noqa: BLE001
                _logger.exception('health_zalo: ZNS readiness wiring failed '
                                  'for connection %s', connection.id)
        return result

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
