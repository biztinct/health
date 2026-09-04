# -*- coding: utf-8 -*-
import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BaseModelRequiredFields(models.AbstractModel):
    """Override BaseModel to enforce configurable required fields.

    This runs at the 'base' level, so it automatically applies to ALL models.
    It only activates when there are matching field.requirement.rule records
    for the model being saved. Models with no rules configured are completely
    unaffected — zero performance impact via early exit.
    """
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        """Validate configurable required fields on create."""
        records = super().create(vals_list)

        # Check each created record against the requirement rules
        for record in records:
            record._check_configurable_required_fields()

        return records

    def write(self, vals):
        """Validate configurable required fields on write."""
        result = super().write(vals)

        # Only check if we're writing fields that might relate to requirements
        # or if the state changed (which might activate new requirements)
        if vals:
            for record in self:
                record._check_configurable_required_fields()

        return result

    def _check_configurable_required_fields(self):
        """Check if configurable required fields are filled.

        This method is called after create/write to validate that all
        configured mandatory fields have values. If any are missing,
        a UserError is raised with a clear list.
        """
        self.ensure_one()
        model_name = self._name

        # Performance guard: skip transient models, system models, and
        # models that should never have requirement rules
        SKIP_PREFIXES = ('ir.', 'base.', 'bus.', 'mail.', 'res.config.')
        SKIP_MODELS = (
            'field.requirement.rule', 'biz.access.role', 'biz.access.ability',
            'res.users', 'res.groups',
        )
        if (
            self._transient
            or model_name in SKIP_MODELS
            or any(model_name.startswith(p) for p in SKIP_PREFIXES)
        ):
            return

        # Prevent recursion via context flag
        if self.env.context.get('_skip_field_requirements'):
            return

        # Check if this model has any rules at all (cached via search)
        RequirementRule = self.env.get('field.requirement.rule')
        if RequirementRule is None:
            # Module not fully installed yet
            return

        # Use context flag to prevent recursion
        RequirementRule = RequirementRule.with_context(_skip_field_requirements=True)

        # Get current state if the model has a state field
        state = None
        if 'state' in self._fields:
            state = self.state

        try:
            required_fields = RequirementRule.get_required_fields(
                model_name, state=state
            )
        except Exception:
            # Don't block saves if the requirement system has issues
            _logger.warning(
                'Error checking field requirements for %s, skipping',
                model_name, exc_info=True
            )
            return

        if not required_fields:
            return

        # Check each required field for a value
        missing = []
        for field_name in required_fields:
            if field_name not in self._fields:
                continue

            field_obj = self._fields[field_name]
            value = self[field_name]

            # Check for "empty" based on field type
            is_empty = False
            if field_obj.type in ('char', 'text', 'html'):
                is_empty = not value or (isinstance(value, str) and not value.strip())
            elif field_obj.type in ('many2one',):
                is_empty = not value
            elif field_obj.type in ('many2many',):
                is_empty = not value
            elif field_obj.type in ('integer', 'float', 'monetary'):
                # 0 is allowed — only None/False is "empty"
                is_empty = value is False or value is None
            elif field_obj.type == 'boolean':
                # Booleans are never truly "empty" — skip them
                continue
            elif field_obj.type in ('date', 'datetime'):
                is_empty = not value
            elif field_obj.type == 'selection':
                is_empty = not value
            else:
                is_empty = not value

            if is_empty:
                label = field_obj.string or field_name
                missing.append(label)

        if missing:
            model_desc = self._description or model_name
            raise UserError(_(
                "The following mandatory fields must be filled on %(model)s:\n\n%(fields)s",
                model=model_desc,
                fields='\n'.join(f'• {f}' for f in missing),
            ))
