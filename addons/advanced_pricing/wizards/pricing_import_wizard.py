# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import io
import logging
import re

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None
    _logger.warning("openpyxl not installed. Excel import will not work.")


class PricingImportWizard(models.TransientModel):
    _name = 'advanced.pricing.import.wizard'
    _description = 'Import Pricing Rules from Excel'

    file = fields.Binary('Excel File', required=True)
    filename = fields.Char('Filename')
    engine_id = fields.Many2one('advanced.pricing.engine', 'Target Engine', required=True)

    import_type = fields.Selection([
        ('base', 'Base Price List (Products)'),
        ('adjustments', 'Adjustments (Pricing Rules)'),
        ('both', 'Both (Products + Rules)'),
    ], string='Import Type', default='both', required=True,
       help='What to import from the Excel file')

    # Import results
    import_log = fields.Text('Import Log', readonly=True)

    # -------------------------------------------------------------------------
    # Mapping constants
    # -------------------------------------------------------------------------

    # Maps Excel Adjustment_Type_en → module action_type
    ADJUSTMENT_TYPE_MAP = {
        'add': 'add',
        'thêm': 'add',
        'multiply': 'multiply',
        'nhân': 'multiply',
        'replace': 'fixed',
        'thay thế': 'fixed',
        'discount base price': 'discount',
        'giảm giá': 'discount',
    }

    # Maps Excel Trigger_Source_en → module trigger_source selection key
    TRIGGER_SOURCE_MAP = {
        'booking/form': 'booking_form',
        'đặt chỗ/biểu mẫu': 'booking_form',
        'app clock': 'app_clock',
        'đồng hồ ứng dụng': 'app_clock',
        'provider after service': 'provider_after_service',
        'nhà cung cấp sau dịch vụ': 'provider_after_service',
        'public holidays table': 'public_holidays_table',
        'bảng ngày lễ': 'public_holidays_table',
        'cmf + booking form': 'cmf_booking_form',
        'quotation on booking form': 'quotation_booking_form',
        'báo giá trên biểu mẫu đặt chỗ': 'quotation_booking_form',
        'service duration log; booking form;': 'service_duration_log',
        'booking form & provider after service': 'booking_form_provider',
        'booking/form & provider after service': 'booking_form_provider',
    }

    # Maps Excel rounding_rule text → selection key
    ROUNDING_RULE_MAP = {
        'round up to next 1,000': 'round_1000',
        'round up to next 5 mins': 'round_5min',
        'round up to next 30 mins': 'round_30min',
        'rounded up to next 30 mins': 'round_30min',
        'round up to next half hour': 'round_half_hour',
        'rounded up to next hour': 'round_hour',
        'round up to next hour': 'round_hour',
    }

    # Maps Excel unit_en → UoM names
    UNIT_MAP = {
        'per_service': 'Units',
        'per_hour': 'Hours',
        'per_injection': 'Units',
        'per_wound': 'Units',
        'per_package': 'Units',
    }

    def import_rules(self):
        """Import rules and/or products from Excel file"""
        self.ensure_one()

        if not openpyxl:
            raise UserError(_("The openpyxl library is required for Excel import. "
                            "Please install it: pip install openpyxl"))

        # Decode the file
        try:
            file_data = base64.b64decode(self.file)
            wb = openpyxl.load_workbook(io.BytesIO(file_data), data_only=True)
        except Exception as e:
            raise UserError(_("Could not read Excel file: %s") % str(e))

        log_lines = []
        log_lines.append(f"=== Import started for: {self.filename} ===")
        log_lines.append(f"Sheets found: {wb.sheetnames}")

        products_created = 0
        products_updated = 0
        rules_created = 0
        rules_skipped = 0
        category_cache = {}  # Shared cache: (parent_en, child_en) -> categ_id

        # Import base products
        if self.import_type in ('base', 'both'):
            for sheet_name in wb.sheetnames:
                if 'Base_Clean' in sheet_name:
                    log_lines.append(f"\n--- Processing Base sheet: {sheet_name} ---")
                    result = self._import_base_sheet(wb[sheet_name], log_lines, category_cache)
                    products_created += result['created']
                    products_updated += result['updated']

        # Import adjustment rules
        if self.import_type in ('adjustments', 'both'):
            for sheet_name in wb.sheetnames:
                if 'Adjustments_Clean' in sheet_name:
                    log_lines.append(f"\n--- Processing Adjustments sheet: {sheet_name} ---")
                    result = self._import_adjustments_sheet(wb[sheet_name], log_lines)
                    rules_created += result['created']
                    rules_skipped += result['skipped']

        # Summary
        log_lines.append(f"\n=== Import Complete ===")
        log_lines.append(f"Products created: {products_created}")
        log_lines.append(f"Products updated: {products_updated}")
        log_lines.append(f"Pricing rules created: {rules_created}")
        log_lines.append(f"Pricing rules skipped: {rules_skipped}")

        self.import_log = '\n'.join(log_lines)

        # Return view to show the log
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _import_base_sheet(self, ws, log_lines, category_cache):
        """Import products from a Base sheet.

        Expected columns (1-indexed):
        1:row_order, 2:province, 3:item_code, 4:service_type_vi, 5:service_type_en,
        6:service_category_vi, 7:service_category_en, 8:service_name_vi, 9:service_name_en,
        10:item_description_vi, 11:item_description_en, 12:unit_vi, 13:unit_en,
        14:base_fee_vnd, 15:currency, 16:rounding_rule, 17:item_active,
        18:valid_from, 19:valid_to, 20:price_version
        """
        result = {'created': 0, 'updated': 0}
        ProductTemplate = self.env['product.template']
        ProductCategory = self.env['product.category']

        for row_idx in range(2, ws.max_row + 1):
            try:
                item_code = self._cell_val(ws, row_idx, 3)
                if not item_code:
                    continue

                province = self._cell_val(ws, row_idx, 2) or ''
                service_type_vi = self._cell_val(ws, row_idx, 4) or ''
                service_type_en = self._cell_val(ws, row_idx, 5) or ''
                service_category_vi = self._cell_val(ws, row_idx, 6) or ''
                service_category_en = self._cell_val(ws, row_idx, 7) or ''
                service_name_vi = self._cell_val(ws, row_idx, 8) or ''
                service_name_en = self._cell_val(ws, row_idx, 9) or ''
                item_description_vi = self._cell_val(ws, row_idx, 10) or ''
                item_description_en = self._cell_val(ws, row_idx, 11) or ''
                unit_en = self._cell_val(ws, row_idx, 13) or 'per_service'
                base_fee = self._parse_numeric(self._cell_val(ws, row_idx, 14))
                rounding_rule_text = (self._cell_val(ws, row_idx, 16) or '').strip().lower()
                item_active_raw = self._cell_val(ws, row_idx, 17)
                item_active = str(item_active_raw).strip().lower() in ('true', '1', 'yes') if item_active_raw else True

                # Build product name (use English description as name)
                product_name = item_description_en or item_code

                # Find or create product category hierarchy:
                # Parent: service_type_en (e.g., "Doctor Service")
                # Child: service_category_en (e.g., "Internal Medicine")
                cache_key = (service_type_en, service_category_en)
                if cache_key in category_cache:
                    categ_id = category_cache[cache_key]
                else:
                    categ_id = self._get_or_create_category(
                        service_type_en, service_type_vi,
                        service_category_en, service_category_vi,
                        log_lines
                    )
                    category_cache[cache_key] = categ_id

                # Find UoM
                uom_id = self._find_uom(unit_en)

                # Map rounding rule
                rounding_key = self.ROUNDING_RULE_MAP.get(rounding_rule_text, False)

                # Check if product already exists (by default_code within same province context)
                # Use item_code + province as a unique key
                internal_ref = f"{item_code}_{province.lower().replace(' ', '_')}" if province else item_code
                existing = ProductTemplate.search([('default_code', '=', internal_ref)], limit=1)

                vals = {
                    'name': product_name,
                    'default_code': internal_ref,
                    'list_price': base_fee or 0,
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'active': item_active,
                    'categ_id': categ_id,
                }

                if uom_id:
                    vals['uom_id'] = uom_id

                if rounding_key:
                    vals['rounding_rule'] = rounding_key

                if existing:
                    existing.write(vals)
                    result['updated'] += 1
                    log_lines.append(f"  Updated: {internal_ref} - {product_name} ({base_fee} VND)")
                else:
                    product = ProductTemplate.create(vals)
                    result['created'] += 1
                    log_lines.append(f"  Created: {internal_ref} - {product_name} ({base_fee} VND)")

                    # Set Vietnamese translation for product name
                    if item_description_vi:
                        product.with_context(lang='vi_VN').write({'name': item_description_vi})

            except Exception as e:
                log_lines.append(f"  ERROR row {row_idx}: {str(e)}")
                _logger.error(f"Import error on row {row_idx}: {e}", exc_info=True)

        return result

    def _import_adjustments_sheet(self, ws, log_lines):
        """Import pricing rules from an Adjustments sheet.

        Expected columns (1-indexed):
        1:Region, 2:item_code, 3:item_name_vi, 4:item_name_en,
        5:Trigger_Condition_vi, 6:Trigger_Condition_en,
        7:Adjustment_Type_vi, 8:Adjustment_Type_en,
        9:Adjustment_Value, 10:Data_Required_vi, 11:Data_Required_en,
        12:Calc_Seq, 13:Trigger_Source_vi, 14:Trigger_Source_en,
        15:Notes_vi, 16:Notes_en
        """
        result = {'created': 0, 'skipped': 0}
        PricingRule = self.env['advanced.pricing.rule']

        for row_idx in range(2, ws.max_row + 1):
            try:
                region = self._cell_val(ws, row_idx, 1) or ''
                item_code_raw = self._cell_val(ws, row_idx, 2) or ''
                item_name_vi = self._cell_val(ws, row_idx, 3) or ''
                item_name_en = self._cell_val(ws, row_idx, 4) or ''
                trigger_condition_en = self._cell_val(ws, row_idx, 6) or ''
                adjustment_type_en = (self._cell_val(ws, row_idx, 8) or '').strip().lower()
                adjustment_value_raw = self._cell_val(ws, row_idx, 9)
                data_required_en = self._cell_val(ws, row_idx, 11) or ''
                calc_seq = self._parse_numeric(self._cell_val(ws, row_idx, 12)) or 10
                trigger_source_en = (self._cell_val(ws, row_idx, 14) or '').strip().lower()
                notes_en = self._cell_val(ws, row_idx, 16) or ''

                if not item_code_raw and not trigger_condition_en:
                    continue

                # Parse adjustment value
                # First check for per-unit patterns (e.g., "10,000 per km")
                per_unit_info = self._check_per_unit_value(str(adjustment_value_raw or ''))
                if per_unit_info:
                    adjustment_value = per_unit_info['value']
                    action_type = 'per_unit'
                else:
                    adjustment_value = self._parse_numeric(adjustment_value_raw)
                    if adjustment_value is None:
                        log_lines.append(
                            f"  SKIPPED row {row_idx}: Non-numeric value '{adjustment_value_raw}' "
                            f"({region} / {item_code_raw} / {trigger_condition_en})"
                        )
                        result['skipped'] += 1
                        continue
                    # Map adjustment type
                    action_type = self.ADJUSTMENT_TYPE_MAP.get(adjustment_type_en, 'add')

                # Map trigger source
                trigger_source = self.TRIGGER_SOURCE_MAP.get(trigger_source_en, False)

                # Build rule name
                rule_name = f"{region} - {item_name_en or item_code_raw} - {trigger_condition_en}"
                if len(rule_name) > 200:
                    rule_name = rule_name[:200]

                # Determine product targeting
                applied_on, product_tmpl_id, categ_id = self._resolve_product_targeting(
                    item_code_raw, region, log_lines
                )

                # Parse trigger condition into condition fields
                condition_vals = self._parse_trigger_condition(trigger_condition_en)

                # Set per_unit_field if this was a per-unit value
                if per_unit_info:
                    condition_vals['per_unit_field'] = per_unit_info['field']

                # Build rule vals
                rule_vals = {
                    'name': rule_name,
                    'engine_id': self.engine_id.id,
                    'sequence': int(calc_seq) * 10,  # multiply sequence to allow insertion
                    'level': '1' if int(calc_seq) <= 2 else '2',
                    'rule_type': 'condition',
                    'active': True,
                    'approval_status': 'draft',
                    'region': region,
                    'item_code': item_code_raw,
                    'action_type': action_type,
                    'action_value': adjustment_value,
                    'applied_on': applied_on,
                    'trigger_source': trigger_source,
                    'data_required': data_required_en,
                    'notes': notes_en,
                }

                if product_tmpl_id:
                    rule_vals['product_tmpl_id'] = product_tmpl_id
                if categ_id:
                    rule_vals['categ_id'] = categ_id

                # Merge condition fields
                rule_vals.update(condition_vals)

                PricingRule.create(rule_vals)
                result['created'] += 1
                log_lines.append(
                    f"  Created rule: {rule_name} "
                    f"(action={action_type}, value={adjustment_value}, seq={calc_seq})"
                )

            except Exception as e:
                log_lines.append(f"  ERROR row {row_idx}: {str(e)}")
                _logger.error(f"Import error on row {row_idx}: {e}", exc_info=True)

        return result

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _cell_val(self, ws, row, col):
        """Get cell value, return None if empty."""
        val = ws.cell(row=row, column=col).value
        if val is None:
            return None
        if isinstance(val, str):
            val = val.strip()
            return val if val else None
        return val

    def _parse_numeric(self, val):
        """Parse a value to float, return None if not numeric."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            # Handle comma-separated numbers like "10,000"
            cleaned = val.replace(',', '').replace(' ', '').strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return None
        return None

    def _get_or_create_category(self, parent_en, parent_vi, child_en, child_vi, log_lines):
        """Find or create a 2-level product category hierarchy.

        `product.category.name` is translatable in this install (advanced_pricing
        overrides it), so BOTH languages from the sheet are stored on the same
        record: English in en_US, Vietnamese in vi_VN. The category then reads
        correctly in whichever language the user logged in with.

        Categories created before that override hold a single Vietnamese-primary
        string in en_US; matching therefore falls back to the Vietnamese name so
        a re-import updates the existing row instead of duplicating it.
        """
        ProductCategory = self.env['product.category']

        if not (parent_en or parent_vi or child_en or child_vi):
            return self.env.ref('product.product_category_all').id

        def _find_or_create(name_en, name_vi, parent=False):
            """One category, keyed on English, with the Vietnamese translation
            written alongside it."""
            primary = name_en or name_vi
            if not primary:
                return False
            # Match on either language: pre-override rows are named in
            # Vietnamese, post-override rows in English.
            candidates = [primary] + ([name_vi] if name_vi and name_vi != primary else [])
            domain_base = [('parent_id', '=', parent.id)] if parent else []
            categ = ProductCategory.search(
                domain_base + [('name', 'in', candidates)], limit=1)
            if not categ:
                categ = ProductCategory.create(dict(
                    {'name': primary},
                    **({'parent_id': parent.id} if parent else {})))
                log_lines.append(f"  Created category: {primary}")
            if name_vi:
                # Only the vi_VN key is touched; en_US keeps the English name.
                categ.with_context(lang='vi_VN').name = name_vi
            return categ

        parent_categ = _find_or_create(parent_en, parent_vi)
        child_categ = _find_or_create(child_en, child_vi, parent=parent_categ)

        if child_categ:
            return child_categ.id
        return parent_categ.id if parent_categ else self.env.ref('product.product_category_all').id

    def _find_uom(self, unit_en):
        """Find UoM by name, return id or False."""
        uom_name = self.UNIT_MAP.get(unit_en, 'Units')
        uom = self.env['uom.uom'].search([('name', 'ilike', uom_name)], limit=1)
        return uom.id if uom else False

    def _resolve_product_targeting(self, item_code_raw, region, log_lines):
        """Resolve Excel item_code to applied_on + product/category IDs.

        Returns: (applied_on, product_tmpl_id, categ_id)
        """
        item_code_lower = item_code_raw.strip().lower() if item_code_raw else ''

        # "Any Service" → global
        if 'any service' in item_code_lower and 'nursing' not in item_code_lower:
            return ('3_global', False, False)

        # "Any nursing service" → target by category
        if 'nursing' in item_code_lower:
            categ = self.env['product.category'].search(
                [('name', 'ilike', 'Nurse Service')], limit=1
            )
            if categ:
                return ('2_product_category', False, categ.id)
            return ('3_global', False, False)

        # Specific item_code → find product by default_code
        if item_code_raw:
            # Try with region-specific code first
            region_suffix = region.lower().replace(' ', '_') if region else ''
            internal_ref = f"{item_code_raw}_{region_suffix}" if region_suffix else item_code_raw

            product = self.env['product.template'].search(
                [('default_code', '=', internal_ref)], limit=1
            )
            if product:
                return ('1_product', product.id, False)

            # Try without region suffix
            product = self.env['product.template'].search(
                [('default_code', 'ilike', item_code_raw)], limit=1
            )
            if product:
                return ('1_product', product.id, False)

            log_lines.append(
                f"  WARNING: Product not found for item_code '{item_code_raw}' "
                f"(region: {region}). Rule will target all products."
            )

        return ('3_global', False, False)

    def _parse_trigger_condition(self, condition_en):
        """Parse Excel trigger condition text into model field values."""
        vals = {}
        condition_lower = condition_en.lower().strip()

        # Distance-based conditions
        dist_match = re.search(r'distance.*?(\d+)\s*km\s*-\s*(\d+)\s*km', condition_lower)
        if dist_match:
            vals['distance_min'] = float(dist_match.group(1))
            vals['distance_max'] = float(dist_match.group(2))
            return vals

        dist_gt_match = re.search(r'distance.*?>\s*(\d+)\s*km', condition_lower)
        if dist_gt_match:
            vals['distance_min'] = float(dist_gt_match.group(1))
            return vals

        # "Is Service at home"
        if 'service at home' in condition_lower:
            vals['requires_home_service'] = True
            # Check for compound condition
            if 'another service' in condition_lower or 'other service' in condition_lower:
                vals['requires_other_service_same_visit'] = True
            return vals

        # "Is After Hours or Weekend"
        if 'after hours' in condition_lower and 'weekend' in condition_lower:
            vals['is_after_hours_or_weekend'] = True
            return vals

        # "Is Public Holiday"
        if 'public holiday' in condition_lower or 'holiday' in condition_lower:
            vals['is_holiday_required'] = True
            return vals

        # After-hours time ranges
        if 'after 20:00' in condition_lower or 'after 8' in condition_lower:
            vals['appointment_hour_min'] = 20
            vals['appointment_hour_max'] = 6  # wraps around
            vals['is_after_hours_required'] = True
            return vals

        if 'between 8 pm' in condition_lower or 'between 20' in condition_lower:
            vals['appointment_hour_min'] = 20
            vals['appointment_hour_max'] = 24
            return vals

        # "Subsequent Wounds" / "Wounds after the first"
        if 'wound' in condition_lower and ('subsequent' in condition_lower or 'after' in condition_lower):
            vals['wound_count_min'] = 2  # after the 1st = 2+
            return vals

        # "After 1st bottle of IV fluid"
        if 'iv fluid' in condition_lower or 'bottle' in condition_lower:
            vals['iv_fluid_count_min'] = 2
            return vals

        # "Every Additional Injection" / "After 1st injection"
        if 'injection' in condition_lower:
            vals['injection_count_min'] = 2
            return vals

        # "Every Additional Medication"
        if 'medication' in condition_lower:
            vals['medication_count_min'] = 2
            return vals

        # "Client receives another service this visit"
        if 'another service' in condition_lower or 'other service' in condition_lower:
            vals['requires_other_service_same_visit'] = True
            return vals

        # "Client Requires Bilingual Provider"
        if 'bilingual' in condition_lower:
            vals['requires_bilingual_provider'] = True
            return vals

        # "Any client after the first at the same location"
        if 'after the first' in condition_lower and 'location' in condition_lower:
            vals['requires_multi_client_same_location'] = True
            return vals

        # "Multiple and/or repeat bookings"
        if 'repeat' in condition_lower or 'multiple' in condition_lower:
            vals['is_repeat_booking'] = True
            return vals

        # "Sales/OM Prequotes"
        if 'prequote' in condition_lower or 'sales/om' in condition_lower:
            vals['is_manual_quote'] = True
            return vals

        return vals

    def _check_per_unit_value(self, value_str):
        """Check if the value is a 'per unit' value like '10,000 per km'.

        Returns dict with value and field, or None.
        """
        value_lower = value_str.lower().strip()
        per_match = re.search(r'([\d,]+)\s*per\s+(\w+)', value_lower)
        if per_match:
            value = float(per_match.group(1).replace(',', ''))
            unit = per_match.group(2)
            field_map = {
                'km': 'distance',
                'wound': 'wound_count',
                'injection': 'injection_count',
            }
            per_unit_field = field_map.get(unit, 'distance')
            return {'value': value, 'field': per_unit_field}
        return None