from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Video room base URL. Room URL = <base>/<room_slug>. Self-hosting Jitsi
    # with signed JWT room tokens is the documented v2 upgrade path.
    th_video_base_url = fields.Char(
        string='Telehealth Video Base URL',
        config_parameter='health_telehealth.video_base_url',
        default='https://meet.jit.si')
    # ZNS template id (rides messaging enabled/dry_run; empty => no row).
    th_zns_template_join = fields.Char(
        string='Telehealth Join ZNS Template ID',
        config_parameter='health_telehealth.zns_template_join')
    # Master switch. Default True: session creation is inert paperwork; sends
    # still ride health_messaging.enabled/dry_run (OFF/dry on vietuat).
    th_enabled = fields.Boolean(
        string='Enable Telehealth Sessions',
        config_parameter='health_telehealth.enabled',
        default=True)
