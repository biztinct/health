# -*- coding: utf-8 -*-
"""What was measured, and what was invoiced for it.

TWO TABLES AND THEY ARE NOT THE SAME THING. `biz.tenant.meter` (H4a's, extended
here) is a READING: how many of each number a customer had in one month. It is
taken once, it is never rewritten, and it is taken for every customer whatever
plan they are on — because a plan can change next month and last month cannot be
measured again.

`biz.tenant.invoice` is what the owner DECIDED to charge for that reading. It
carries its own copy of the plan's name, price and tax at the moment it was
raised, so an invoice issued in September still says what it said in September
after the plan is edited in October. **An invoice that recomputes itself from
today's plan is not a document, it is a query.**

NOT AN ACCOUNTING ENTRY. These are the platform's own records — no journal, no
ledger entry, no reconciliation. The owner marks an invoice paid when the
transfer arrives, and the seam for a payment provider later is `payment_reference`
plus `paid_via`, which nothing today writes.
"""
from odoo import api, fields, models

from .billing_rules import (
    INVOICE_STATE_LABEL, INVOICE_STATES, PRICE_KINDS, PRICE_KIND_LABEL, money,
    overdue_days, period_label, qty_text,
)


class BizTenantInvoice(models.Model):
    _name = 'biz.tenant.invoice'
    _description = 'One invoice to one customer'
    _order = 'period_start desc, number desc, id desc'

    tenant_id = fields.Many2one('biz.tenant', required=True,
                                ondelete='cascade', index=True)
    number = fields.Char(required=True, index=True, copy=False,
                         help="Sequential inside a year, and never reused.")
    period_start = fields.Date(required=True, index=True,
                               help="The first day of the month being charged.")
    period_end = fields.Date(required=True)

    #: A SNAPSHOT, not a live link. The plan may be renamed or repriced
    #: tomorrow; this invoice must keep saying what it said when it was issued.
    plan_id = fields.Many2one('biz.plan', ondelete='set null')
    plan_name = fields.Char()
    plan_kind = fields.Selection([(k, PRICE_KIND_LABEL[k]) for k in PRICE_KINDS])
    #: The arithmetic in the words the preview showed, kept so the answer to
    #: "why is it this much?" is on the record rather than in somebody's head.
    explain = fields.Char()

    line_ids = fields.One2many('biz.tenant.invoice.line', 'invoice_id')

    currency_id = fields.Many2one('res.currency', required=True)
    subtotal = fields.Float(digits=(16, 2))
    vat_rate = fields.Float(digits=(16, 2), default=0.0)
    vat_amount = fields.Float(digits=(16, 2))
    total = fields.Float(digits=(16, 2))

    state = fields.Selection([(s, INVOICE_STATE_LABEL[s]) for s in INVOICE_STATES],
                             default='draft', required=True, index=True)
    issued_on = fields.Date()
    due_on = fields.Date(index=True)
    paid_on = fields.Date()
    #: THE SEAM FOR A PAYMENT PROVIDER, and nothing writes it automatically
    #: today. When cards arrive, the provider's reference lands here and the
    #: state moves through the same method the owner presses now.
    payment_reference = fields.Char(string="Reference")
    paid_via = fields.Char(string="Paid how")
    cancel_reason = fields.Char()

    reminder_count = fields.Integer(default=0)
    last_reminder_on = fields.Date()
    #: ⚠ EMPTY WHILE THERE IS NO WAY TO SEND ANYTHING (ledger F40). A record of
    #: "spoken" on a platform with no mail account is a record of something
    #: that did not happen, and it is the field somebody will later use to
    #: decide not to chase.
    spoken_at = fields.Datetime()

    #: The document as it was rendered when the invoice was issued. Stored
    #: rather than re-rendered on demand, for the same reason the plan is
    #: snapshotted: a document that changes after it was sent is not a document.
    pdf = fields.Binary(attachment=True)
    pdf_name = fields.Char()

    _number_unique = models.Constraint(
        'UNIQUE (number)', "That invoice number already exists.")

    def money(self, amount):
        self.ensure_one()
        cur = self.currency_id
        return money(amount, cur.symbol or '', cur.rounding or 0.01,
                     cur.position or 'after')

    def as_dict(self):
        out = []
        today = fields.Date.context_today(self)
        for inv in self:
            days = overdue_days({'state': inv.state, 'due_on': inv.due_on},
                                today)
            out.append({
                'id': inv.id,
                'tenant_id': inv.tenant_id.id,
                'tenant': inv.tenant_id.name or '',
                'slug': inv.tenant_id.slug or '',
                'number': inv.number or '',
                'period': inv.period_start.isoformat() if inv.period_start else '',
                'period_label': period_label(inv.period_start),
                'plan_name': inv.plan_name or '',
                'explain': inv.explain or '',
                'state': inv.state,
                'state_label': INVOICE_STATE_LABEL.get(inv.state, inv.state),
                'subtotal': inv.subtotal, 'subtotal_h': inv.money(inv.subtotal),
                'vat_rate': inv.vat_rate, 'vat_amount': inv.vat_amount,
                'vat_h': inv.money(inv.vat_amount),
                'total': inv.total, 'total_h': inv.money(inv.total),
                'currency': inv.currency_id.name or '',
                'issued_on': inv.issued_on.isoformat() if inv.issued_on else '',
                'due_on': inv.due_on.isoformat() if inv.due_on else '',
                'paid_on': inv.paid_on.isoformat() if inv.paid_on else '',
                'days_overdue': days,
                'payment_reference': inv.payment_reference or '',
                'paid_via': inv.paid_via or '',
                'cancel_reason': inv.cancel_reason or '',
                'reminder_count': inv.reminder_count,
                # An honest nought: nothing has been said to anybody, because
                # there is nothing to say it with (F40).
                'spoken_at': (inv.spoken_at.strftime('%Y-%m-%d %H:%M')
                              if inv.spoken_at else ''),
                'has_pdf': bool(inv.pdf),
                'lines': [{
                    'label': l.label or '', 'detail': l.detail or '',
                    'qty': l.qty, 'qty_h': qty_text(l.qty),
                    'unit_price': l.unit_price,
                    'unit_h': inv.money(l.unit_price),
                    'amount': l.amount, 'amount_h': inv.money(l.amount),
                } for l in inv.line_ids],
            })
        return out

    # ------------------------------------------------------------------- PDF
    def _billing_render_data(self):
        """Everything the printed invoice puts on the page, already worded.

        ⚠ `_billing_*` (ledger F52). This model is small, but the service that
        fills it is one facade assembled from six files, and a helper called
        `_render_data` there would collide with somebody else's.

        The template holds property access and nothing else — no arithmetic and
        no formatting — so the figures on the document are the figures the
        record carries, formatted by the one money formatter the phase uses.
        """
        self.ensure_one()
        svc = self.env['biz.tenants'].sudo()
        who = svc._billing_customer_identity(self.tenant_id)
        seller = svc._billing_seller()
        data = self.as_dict()[0]
        missing = [label for label, value in (
            ("a company name", seller['name']),
            ("a company address", seller['address']),
            ("a tax number", seller['vat']),
            ("bank details to pay into", seller['bank']),
        ) if not value]
        return {
            'number': self.number or '',
            'state': self.state,
            'state_label': INVOICE_STATE_LABEL.get(self.state, self.state),
            'period_label': data['period_label'],
            'issued_on': (self.issued_on.strftime('%d %B %Y')
                          if self.issued_on else ''),
            'due_on': self.due_on.strftime('%d %B %Y') if self.due_on else '',
            'customer_name': who['name'],
            'customer_address': who['address'],
            'customer_vat': who['vat'],
            'customer_email': who['email'],
            'seller_name': seller['name'],
            'seller_address': seller['address'],
            'seller_vat': seller['vat'],
            'bank_details': seller['bank'],
            'footer': seller['footer'],
            'brand': seller['brand'],
            'lines': data['lines'],
            'explain': data['explain'],
            'subtotal_h': data['subtotal_h'],
            'vat_rate': self.vat_rate or 0.0,
            'vat_rate_h': ('%g' % (self.vat_rate or 0.0)),
            'vat_h': data['vat_h'],
            'total_h': data['total_h'],
            # ⚠ THE DOCUMENT SAYS SO ITSELF RATHER THAN PRINTING AN INVOICE
            # THAT CANNOT BE PAID. An invoice with no bank details on it is a
            # request for money with no way to send it, and the person who
            # receives it has no way of knowing that was an oversight.
            'missing': missing,
            # Said ONCE: the document's own block already opens with "Not
            # ready to send", so this is the list and nothing else.
            'missing_text': (
                "It is missing %s."
                % (', '.join(missing[:-1]) + ' and ' + missing[-1]
                   if len(missing) > 1 else (missing[0] if missing else ''))),
        }


class BizTenantInvoiceLine(models.Model):
    _name = 'biz.tenant.invoice.line'
    _description = 'One line of one invoice'
    _order = 'invoice_id, sequence, id'

    invoice_id = fields.Many2one('biz.tenant.invoice', required=True,
                                 ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True)
    detail = fields.Char(help="The small print under the line.")
    #: WHICH NUMBER THIS LINE WAS PRICED FROM, kept so an invoice can be traced
    #: back to the reading it came out of a year later.
    meter_key = fields.Char()
    measured = fields.Integer(help="What the platform measured, before any "
                                   "allowance was taken off.")
    qty = fields.Float(digits=(16, 2), default=1.0)
    unit_price = fields.Float(digits=(16, 2))
    amount = fields.Float(digits=(16, 2))


class BizTenantMeterHistory(models.Model):
    """H4a's meter, given the two things billing needs from it.

    ⚠ BILLING BILLS FROM WHAT WAS MEASURED AT THE TIME, NEVER FROM A NUMBER
    RECOMPUTED LATER (§3.3). That is the whole reason these rows exist, and it
    is why `snapshot` refuses to overwrite a month that already has one: a
    re-run is a no-op that SAYS it was a no-op, rather than quietly moving last
    year's invoice basis.
    """
    _inherit = 'biz.tenant.meter'

    #: The month this reading is FOR, as the first of that month. `period_start`
    #: already holds it for a monthly snapshot; this is the indexed, unambiguous
    #: form the billing queries use, and it is empty on an ad-hoc reading over
    #: some other span.
    month = fields.Date(index=True,
                        help="The month this reading belongs to, when it is a "
                             "monthly one.")
    #: ⚠ A BACKFILLED ROW IS NOT THE SAME FACT AS A ROW TAKEN AT THE TIME, and
    #: the difference has to survive onto the screen: a count of people taken
    #: three months after the month it is attributed to is today's number
    #: wearing an old date.
    backfilled = fields.Boolean(
        default=False,
        help="Taken after the month had ended, so it is today's number rather "
             "than the number at the time.")

    @api.model
    def snapshot(self, tenant, row, month, backfilled=False):
        """One monthly reading, written ONCE. Returns `(record, 'written'|'kept')`.

        A month that already has a reading is left exactly as it is, and the
        caller is told so in those words. Everything that bills reads these
        rows; rewriting one would rewrite the basis of an invoice that has
        already been sent.
        """
        from .billing_rules import month_end
        start = month
        end = month_end(month)
        existing = self.sudo().search([
            ('tenant_id', '=', tenant.id), ('key', '=', row['key']),
            ('month', '=', start),
        ], limit=1)
        if existing:
            return existing, 'kept'
        rec = self.sudo().create({
            'tenant_id': tenant.id, 'key': row['key'],
            'label': row.get('label') or row['key'],
            'unit': row.get('unit') or '',
            'value': int(row.get('value') or 0),
            'available': bool(row.get('available', True)),
            'reason': row.get('reason') or '',
            'period_start': start, 'period_end': end, 'month': start,
            'backfilled': bool(backfilled),
            'taken_at': fields.Datetime.now(),
        })
        return rec, 'written'

    @api.model
    def readings_for(self, tenant, month):
        """`({key: value}, {keys that could not be measured})` for one month.

        THE ONLY DOOR BILLING READS A NUMBER THROUGH. It answers out of the
        snapshot and never recounts, and a key with no row at all is simply
        absent — which the pricing rules read as nought and SAY SO, rather than
        guessing.
        """
        rows = self.sudo().search([('tenant_id', '=', tenant.id),
                                   ('month', '=', month)])
        values, unavailable = {}, set()
        for row in rows:
            values[row.key] = row.value
            if not row.available:
                unavailable.add(row.key)
        return values, unavailable
