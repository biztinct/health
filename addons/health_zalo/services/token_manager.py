# -*- coding: utf-8 -*-

from odoo import models, api
from .zalo_api import get_api_client
import logging

_logger = logging.getLogger(__name__)


class ZaloTokenManager(models.AbstractModel):
    """
    Service model for Zalo OAuth token management.

    Handles token exchange, refresh, and expiry checking.
    Provides automatic token refresh before expiry.
    """
    _name = 'zalo.token.manager'
    _description = 'Zalo Token Manager Service'

    @api.model
    def exchange_code_for_token(self, config, code):
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            config: zalo.config record
            code: Authorization code from OAuth callback

        Returns:
            Dict with access_token, refresh_token, expires_in
        """
        api_client = get_api_client(self.env)
        result = api_client.exchange_code_for_token(config, code)

        if result.get('access_token'):
            _logger.info(f'Successfully exchanged code for token: config={config.name}')
        else:
            _logger.error(f'Failed to exchange code: {result.get("error")}')

        return result

    @api.model
    def refresh_access_token(self, config):
        """
        Refresh access token using refresh token.

        Args:
            config: zalo.config record

        Returns:
            Dict with new access_token, refresh_token, expires_in
        """
        if not config.refresh_token:
            _logger.error(f'No refresh token available for config: {config.name}')
            return {'error': 'No refresh token available'}

        api_client = get_api_client(self.env)
        result = api_client.refresh_access_token(config)

        if result.get('access_token'):
            _logger.info(f'Successfully refreshed token: config={config.name}')
        else:
            _logger.error(f'Failed to refresh token: {result.get("error")}')

        return result
