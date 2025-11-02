import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TimelineController(http.Controller):
    """
    Controller for timeline view operations and session management
    """

    @http.route('/health_fieldservice/timeline/clear_context', type='json', auth='user')
    def clear_timeline_context(self):
        """
        Clear timeline context from session when user closes/navigates away from timeline view.
        This should be called when:
        - User closes the timeline view without creating more assignments
        - User navigates to a different section
        - Session timeout occurs
        """
        user_id = request.env.user.id

        # Clear the timeline context from session
        request.env['health.staff.assignment']._clear_timeline_context(user_id)

        _logger.info("🧹 Timeline context cleared for user: %s", user_id)

        return {'status': 'success', 'message': 'Timeline context cleared'}
