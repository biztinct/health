"""Generic crosswalk + reversible archive log for the migration."""
from odoo import models, fields


class MigrationXref(models.Model):
    """Maps a legacy dimension value to the target record it resolved to.

    Used by the get_or_create_* resolvers (staff stubs, services, facilities,
    tags) to dedupe across rows and audit everything the migration fabricated.
    """
    _name = 'migration.xref'
    _description = 'Migration Crosswalk'
    _rec_name = 'legacy_key'

    source = fields.Char('Source File/Run', index=True)
    target_model = fields.Char('Target Model', required=True, index=True)
    legacy_key = fields.Char('Legacy Key', required=True, index=True)
    res_id = fields.Integer('Target Record ID', required=True)
    raw_value = fields.Char('Raw Legacy Value')
    auto_created = fields.Boolean('Auto-created by migration', default=False)
    notes = fields.Char('Notes')

    _sql_constraints = [
        ('uniq_key', 'unique(target_model, legacy_key)',
         'A crosswalk entry already exists for this model + legacy key.'),
    ]


class MigrationBaseline(models.Model):
    """Log of records archived (active=False) by the migration so the
    pre-existing demo/test data can be restored with one action."""
    _name = 'migration.baseline'
    _description = 'Migration Archive Baseline'
    _rec_name = 'target_model'

    run = fields.Char('Run Tag', index=True)
    target_model = fields.Char('Model', required=True, index=True)
    res_id = fields.Integer('Record ID', required=True)
    archived_at = fields.Datetime('Archived At')

    _sql_constraints = [
        ('uniq_rec', 'unique(target_model, res_id, run)',
         'Record already logged for this run.'),
    ]
