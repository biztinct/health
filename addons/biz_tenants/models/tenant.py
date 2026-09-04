# -*- coding: utf-8 -*-
"""One customer, everything kept about them, and nothing kept about their data.

WHAT IS ON THIS RECORD AND WHAT IS NOT. Everything here is a fact about the
SYSTEM: where it lives, what release it is on, how big it is, when it was last
backed up, what happened to it. Nothing here is a fact about the people or the
records inside it. The cockpit reads a customer's system to answer "is it
healthy"; it never copies what is in it.

THE PROVISIONING LOG IS THE ONLY RECORD OF WHAT HAPPENED TO A CUSTOMER'S
SYSTEM, so it is append-only in practice and nothing in this module ever
shortens it.
"""
from odoo import api, fields, models

from .billing_rules import SERVING_STATES as _SERVING

#: The states, and the one line that matters about them: only `decommissioned`
#: means the database is GONE. Everything else still has one, and is backed up,
#: measured and watched exactly the same way.
#:
#: ⚠ `paused` IS ON THAT LIST ON PURPOSE (SAAS H4d). A paused customer's people
#: cannot sign in, and that is exactly the week in which losing their copies
#: would be unforgivable. Pausing is a DOOR, never a deletion.
#:
#: ONE DEFINITION, NEXT DOOR. `billing_rules.SERVING_STATES` is the list every
#: nightly job, meter and invoice run works from; a second copy here would be a
#: second thing to forget.
SERVING_STATES = tuple(['provisioning', 'error'] + list(_SERVING))


class BizTenant(models.Model):
    _name = 'biz.tenant'
    _description = 'Customer system'
    _order = 'state, name'

    name = fields.Char(required=True, string="Customer",
                       help="What this customer is called, in their own words.")
    #: THE DATABASE NAME AND THE HOSTNAME LABEL, one field, because they are one
    #: thing (see `provision_rules.check_slug`). Two fields would be two places
    #: for them to disagree, and the day they disagree the address answers
    #: nothing at all.
    slug = fields.Char(required=True, index=True, string="Short name",
                       help="The first word of their web address, and the name "
                            "of their system on this machine. Small letters "
                            "and digits only.")
    state = fields.Selection([
        ('draft', 'Not started'),
        ('provisioning', 'Being set up'),
        ('trial', 'On trial'),
        ('live', 'Live'),
        ('paused', 'Paused'),
        ('pending_deletion', 'Closing down'),
        ('error', 'Needs attention'),
        ('decommissioned', 'Closed'),
    ], default='draft', required=True, index=True)

    contact_name = fields.Char(string="Their administrator")
    contact_email = fields.Char(string="Their administrator's email")
    note = fields.Text()
    created_on = fields.Datetime(default=fields.Datetime.now, readonly=True)

    # ------------------------------------------------------------ provisioning
    provision_step = fields.Char(
        help="The last step that finished. The screen offers the next one.")
    #: APPEND-ONLY, one line per act, timestamped. The only record of what was
    #: done to a customer's system.
    provision_log = fields.Text(default='')
    last_error = fields.Text()

    # ----------------------------------------------------------------- release
    release_id = fields.Many2one('biz.release', ondelete='set null',
                                 string="Release")
    release_state = fields.Selection([
        ('on', 'In step'),
        ('behind', 'Behind'),
        ('none', 'Not on a release'),
        ('unknown', 'Not checked'),
    ], default='unknown', index=True)
    behind_count = fields.Integer(help="Parts of the product it does not have.")
    stale_count = fields.Integer(help="Parts it has at an older version.")
    skipped_count = fields.Integer(
        default=-1,
        help="Parts it says it has but which did not load. -1 means it could "
             "not be determined — an honest 'could not tell' rather than a "
             "green nought.")
    drift_checked = fields.Datetime()
    last_sync_at = fields.Datetime()
    last_sync_result = fields.Text(
        help="What the last 'bring in step' actually did, so the question has "
             "an answer afterwards.")

    # ------------------------------------------------------------------ health
    health_state = fields.Selection([
        ('ok', 'Healthy'),
        ('warn', 'Worth a look'),
        ('down', 'Not answering'),
        ('unknown', 'Not checked'),
    ], default='unknown', index=True)
    health_checked_at = fields.Datetime()
    health_detail = fields.Text(help="The last full reading, as it was taken.")
    db_size = fields.Float(help="bytes")
    filestore_size = fields.Float(help="bytes")
    module_count = fields.Integer()
    user_count = fields.Integer()
    http_status = fields.Integer(default=0)
    ping_ms = fields.Integer(default=-1)

    # ------------------------------------------------------------ certificates
    cert_expires_on = fields.Date()
    cert_state = fields.Selection([
        ('own', 'Its own certificate'),
        ('shared', 'Falling back to the shared one'),
        ('none', 'Could not be read'),
    ], default='none')

    # ======================================================================
    #  WHAT THEY PAY, AND WHERE THEY STAND (SAAS H4d)
    #
    #  ⚠ NOTHING HERE EVER LOCKS ANYBODY OUT ON A TIMER, AND NOTHING HERE EVER
    #  DELETES ANYTHING ON A SCHEDULE. `trial_ends_on` running out raises an
    #  alert and says so; `delete_after` running out lets the cockpit OFFER the
    #  button. Both are reminders to a person. The one automatic pause on this
    #  platform is behind a switch that ships OFF.
    # ======================================================================
    plan_id = fields.Many2one('biz.plan', ondelete='set null', string="Plan",
                              help="What they pay, and the number it is worked "
                                   "out from.")
    trial_ends_on = fields.Date(
        string="Trial ends",
        help="The last day of their trial. Nothing happens on this day on its "
             "own — it raises a note on the Alerts screen.")
    #: Which phase of the trial they have already been told about, so a nightly
    #: job says each thing once rather than once a night (the same counted
    #: shape the invoice reminders use).
    trial_told = fields.Char(default='')
    paused_at = fields.Datetime()
    paused_reason = fields.Char(
        help="Shown to their people on the page they meet, in these words.")
    delete_after = fields.Date(
        string="May be removed after",
        help="A promise about how long their data is kept. NOTHING removes it "
             "when this passes; the screen offers the button and a person "
             "presses it.")
    deletion_reason = fields.Char()
    #: When the platform last told their system where they stand. A push that
    #: did not land is the difference between a paused customer and a customer
    #: who thinks they are paused.
    standing_pushed_at = fields.Datetime()
    invoice_ids = fields.One2many('biz.tenant.invoice', 'tenant_id')
    #: Their own invoicing address, when it differs from the administrator's.
    #: Read off THEIR system first (§3.4) — this is only the fallback.
    billing_email = fields.Char(string="Send invoices to")

    # ---------------------------------------------------------------- the rest
    backup_ids = fields.One2many('biz.tenant.backup', 'tenant_id')
    domain_ids = fields.One2many('biz.tenant.domain', 'tenant_id')
    meter_ids = fields.One2many('biz.tenant.meter', 'tenant_id')
    last_backup_at = fields.Datetime()

    #: A MIRROR of what was written onto their system, kept here so the cockpit
    #: can answer "what are they being shown right now" without opening their
    #: registry. Their copy is the one that counts; this one is for the screen.
    notice = fields.Text()
    notice_kind = fields.Char()
    notice_from = fields.Datetime()
    notice_to = fields.Datetime()
    notice_sent_at = fields.Datetime()

    # ⚠ `models.Constraint`, NOT the old `_sql_constraints` LIST. On this
    # framework the list form is INERT — it is accepted, it is never applied,
    # and `pg_constraint` simply has nothing in it. Two customers could then be
    # given the same short name, which means two records pointing at ONE
    # database. Found by a test that tried it rather than by reading the model
    # (memory: reference_odoo19_field_conversion).
    _slug_unique = models.Constraint(
        'UNIQUE (slug)',
        "Another customer already has that short name. It is also the name of "
        "their system on this machine, so no two can share one.")

    def log(self, text, level='info'):
        """One line, timestamped, on the end. THE ONLY RECORD, so never
        shortened and never rewritten."""
        self.ensure_one()
        stamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mark = {'error': 'FAILED', 'warn': 'NOTE'}.get(level, '')
        line = '%s  %s%s' % (stamp, ('%s: ' % mark) if mark else '', text)
        self.sudo().write({'provision_log': (self.provision_log or '') + line + '\n'})
        return line


class BizTenantBackup(models.Model):
    _name = 'biz.tenant.backup'
    _description = 'A copy of one customer system'
    _order = 'taken_at desc, id desc'

    tenant_id = fields.Many2one('biz.tenant', required=True,
                                ondelete='cascade', index=True)
    kind = fields.Selection([
        ('nightly', 'Nightly'),
        ('manual', 'Taken by hand'),
        ('final', 'Final, before closing'),
    ], default='manual', required=True, index=True)
    path = fields.Char(required=True, help="The database file.")
    filestore_path = fields.Char(help="The attachments archive beside it.")
    #: BOTH sizes, recorded separately and on purpose (ledger F59). A backup is
    #: the database AND the attachments; one number cannot say whether the
    #: second half is there.
    size = fields.Float(help="bytes — the database file")
    filestore_size = fields.Float(help="bytes — the attachments archive")
    filestore_files = fields.Integer()
    taken_at = fields.Datetime(default=fields.Datetime.now, required=True)
    state = fields.Selection([('done', 'Kept'), ('failed', 'Failed')],
                             default='done', required=True)
    note = fields.Char()


class BizTenantDomain(models.Model):
    _name = 'biz.tenant.domain'
    _description = 'A web address one customer answers on'
    _order = 'id'

    tenant_id = fields.Many2one('biz.tenant', required=True,
                                ondelete='cascade', index=True)
    hostname = fields.Char(required=True, index=True)
    #: READ-ONLY IN THIS PHASE. Every customer has exactly one address — their
    #: own `<short name>.<apex>` — and it is seeded when they are created.
    #: Customer-owned addresses need a change to the application itself before
    #: they can work at all (see the Domains tab's own sentence), so nothing
    #: here writes a routing rule that would do nothing.
    kind = fields.Selection([
        ('platform', "The platform's own address"),
        ('custom', "The customer's own address"),
    ], default='platform', required=True)
    note = fields.Char()

    # See the note on `biz.tenant`: the old list form is inert here.
    _hostname_unique = models.Constraint(
        'UNIQUE (hostname)',
        "That address is already attached to a customer.")


class BizTenantMeter(models.Model):
    """One reading of one number, for one customer, for one period.

    NOT USED BY ANYTHING YET, and that is deliberate (handover §3.7): the next
    phase bills from these rows, and a table that starts collecting on the day
    billing is switched on has no history to bill from. Everything is collected
    every time; which number a customer is SOLD on is decided later, out of
    figures that were already gathered.
    """
    _name = 'biz.tenant.meter'
    _description = 'One reading of one customer number'
    _order = 'period_start desc, key'

    tenant_id = fields.Many2one('biz.tenant', required=True,
                                ondelete='cascade', index=True)
    key = fields.Char(required=True, index=True)
    label = fields.Char()
    unit = fields.Char()
    value = fields.Integer()
    #: -1 rather than 0 when the number could not be read at all. A zero is a
    #: measurement; "not available here" is not, and a meter that reads 0 on a
    #: busy customer is worse than no meter.
    available = fields.Boolean(default=True)
    reason = fields.Char(help="Why it could not be read, when it could not.")
    period_start = fields.Date(required=True, index=True)
    period_end = fields.Date(required=True)
    taken_at = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def record(self, tenant, row, start, end):
        """Write one reading, replacing any earlier one for the same period."""
        existing = self.sudo().search([
            ('tenant_id', '=', tenant.id), ('key', '=', row['key']),
            ('period_start', '=', start), ('period_end', '=', end),
        ], limit=1)
        vals = {
            'tenant_id': tenant.id, 'key': row['key'],
            'label': row.get('label') or row['key'], 'unit': row.get('unit') or '',
            'value': int(row.get('value') or 0),
            'available': bool(row.get('available', True)),
            'reason': row.get('reason') or '',
            'period_start': start, 'period_end': end,
            'taken_at': fields.Datetime.now(),
        }
        if existing:
            existing.write(vals)
            return existing
        return self.sudo().create(vals)
