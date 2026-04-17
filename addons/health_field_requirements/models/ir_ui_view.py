# -*- coding: utf-8 -*-
import logging
from lxml import etree
from odoo import models

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    """Extend ir.ui.view to dynamically add required="1" on fields
    configured via field.requirement.rule.

    This produces the native Odoo visual experience:
    - Red asterisks on required fields
    - Inline "This field is required" errors on save attempt
    """
    _inherit = 'ir.ui.view'

    def _postprocess_access_rights(self, tree):
        """Add required attributes based on field requirement rules."""
        tree = super()._postprocess_access_rights(tree)

        current_model = tree.get('model_access_rights')
        if not current_model:
            return tree

        try:
            RequirementRule = self.env.get('field.requirement.rule')
            if RequirementRule is None:
                return tree

            # Get all rules for this model (with state info)
            field_states = RequirementRule.get_required_fields_with_states(
                current_model
            )
            if not field_states:
                return tree

            for field_name, states in field_states.items():
                for field_node in tree.xpath(f'//field[@name="{field_name}"]'):
                    # Skip fields that are already required in the base view
                    if field_node.get('required') == '1':
                        continue

                    # Skip invisible fields — no point making them required
                    if field_node.get('invisible') == '1':
                        continue

                    if not states:
                        # Always required — simple static required
                        field_node.set('required', '1')
                    else:
                        # State-dependent — generate dynamic expression
                        # e.g., required="state in ('confirmed', 'assigned')"
                        state_str = ', '.join(f"'{s}'" for s in states)
                        field_node.set('required', f"state in ({state_str})")

        except Exception:
            _logger.warning(
                'Error applying field requirements to view for model %s',
                current_model, exc_info=True
            )

        return tree
