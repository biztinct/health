# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, models, _
from odoo.exceptions import AccessError


class HealthSoftDeleteGuard(models.AbstractModel):
    _inherit = 'base'

    _health_owner_delete_exact_models = {
        'account.move',
        'account.move.line',
        'account.payment',
        'crm.lead',
        'crm.stage',
        'hr.employee',
        'product.pricelist',
        'product.product',
        'product.template',
        'res.partner',
        'res.users',
        'sale.order',
        'sale.order.line',
    }
    _health_owner_delete_prefixes = (
        'advanced.pricing.',
        'health.',
        'misa.',
    )

    @api.model
    def _health_owner_only_delete_model(self):
        return (
            self._name in self._health_owner_delete_exact_models
            or self._name.startswith(self._health_owner_delete_prefixes)
        )

    def unlink(self):
        is_transient = getattr(self, 'is_transient', None)
        if callable(is_transient) and is_transient():
            return super().unlink()
        if (
            self._health_owner_only_delete_model()
            and not getattr(self.env, 'su', False)
            and self.env.uid != SUPERUSER_ID
            and not self.env.user.has_group('health_base.group_healthcare_owner')
        ):
            raise AccessError(_(
                "Hard delete is restricted to Healthcare Owner users. "
                "Use Archive instead to deactivate records without deleting history."
            ))
        return super().unlink()
