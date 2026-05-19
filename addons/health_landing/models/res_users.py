# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.fields import Date


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def get_admin_dashboard_data(self):
        today = Date.context_today(self)

        active_users = self.env["res.users"].search_count([
            ("active", "=", True),
            ("share", "=", False),
        ])

        active_facilities = self.env["health.facility"].search_count([
            ("active", "=", True),
        ])

        service_types = self.env["health.service.type"].search_count([
            ("active", "=", True),
        ])

        pricing_rules = self.env["advanced.pricing.rule"].search_count([])

        equipment_items = self.env["health.portable.equipment"].search_count([])

        audit_today = 0
        try:
            audit_today = self.env["health.audit.log.view"].search_count([
                ("create_date", ">=", today.strftime("%Y-%m-%d 00:00:00")),
            ])
        except Exception:
            pass

        recent_audit = []
        try:
            logs = self.env["health.audit.log.view"].search(
                [], order="create_date desc", limit=10,
            )
            for log in logs:
                icon = "fa-pencil"
                if hasattr(log, "action_type"):
                    action_map = {
                        "create": "fa-plus",
                        "write": "fa-pencil",
                        "unlink": "fa-trash",
                    }
                    icon = action_map.get(log.action_type, "fa-pencil")

                recent_audit.append({
                    "id": log.id,
                    "description": getattr(log, "description", "") or
                                   getattr(log, "name", f"Audit #{log.id}"),
                    "user_name": log.create_uid.name if log.create_uid else "System",
                    "time_ago": self._format_time_ago(log.create_date),
                    "icon": icon,
                })
        except Exception:
            pass

        return {
            "kpis": {
                "active_users": active_users,
                "active_facilities": active_facilities,
                "service_types": service_types,
                "pricing_rules": pricing_rules,
                "equipment_items": equipment_items,
                "audit_today": audit_today,
            },
            "recent_audit": recent_audit,
        }

    @api.model
    def _format_time_ago(self, dt):
        if not dt:
            return ""
        from datetime import datetime
        now = datetime.now()
        if hasattr(dt, 'replace'):
            dt = dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins}m ago"
        if seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        days = int(seconds / 86400)
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d")
