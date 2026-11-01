from odoo import SUPERUSER_ID, api
from odoo.addons.health_access.hooks import scope_operations_managers


def migrate(cr, version):
    if version:
        scope_operations_managers(api.Environment(cr, SUPERUSER_ID, {}))
