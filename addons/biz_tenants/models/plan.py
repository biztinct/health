# -*- coding: utf-8 -*-
"""What a customer pays for, and the number it is worked out from.

ONE RECORD, SIX WAYS OF CHARGING. The owner's ruling is that any of the numbers
the platform already measures can price a plan, plus a flat price and a flat
price by size band. So `price_kind` is the structure and `meter_key` is which
number it reads — see the long note at the top of `billing_rules.py` for why it
is written that way round rather than as six named structures.

⚠ A PLAN PRICED BY BAND MUST BE CREATED WITH ITS BANDS, IN ONE WRITE (ledger
F60). The constraint below refuses a banded plan with no bands, which is
correct — and it means a data file that creates the plan and THEN adds the bands
fails in between and takes the whole upgrade down with it. The seed uses an
inline `tier_ids` eval; `plan_save` builds `[(5, 0, 0)] + [(0, 0, …)]` into the
same write.

PRICES ARE DATA, NOT CODE. The three seeded plans carry the owner's placeholder
figures and say on the screen that they are placeholders. Nothing here has an
opinion about what anything should cost.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from . import tenants_common as common
from .billing_rules import (
    DEFAULT_TRIAL_DAYS, PRICE_KIND_LABEL, PRICE_KINDS, money, qty_text,
    unit_words,
)

_logger = logging.getLogger(__name__)


def _meter_label(key):
    """What the product calls one of its numbers, or the bare key.

    Read from the registry at CALL time, never at import time: one registry
    serves every database this process loads, and a label frozen into a field
    default is a label from whichever product happened to import first.
    """
    for spec in common.meters():
        if spec['key'] == key:
            return spec.get('label') or key
    return key or ''


class BizPlan(models.Model):
    _name = 'biz.plan'
    _description = 'What a customer pays'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True,
                       help="What this plan is called on the screen and on the "
                            "invoice.")
    code = fields.Char(required=True, index=True,
                       help="A short name nobody outside this screen sees. "
                            "Used to find the plan from a script.")
    blurb = fields.Char(translate=True,
                        help="One plain sentence: who this plan is for.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    #: THE PLACEHOLDER FLAG, AND IT IS ON THE SCREEN. The seeded figures are
    #: the owner's to overwrite, and an invoice raised from a figure nobody has
    #: looked at is the one mistake this whole phase could make.
    is_placeholder = fields.Boolean(
        default=False,
        help="The price on this plan was seeded as an example and has not been "
             "confirmed by anybody yet.")

    price_kind = fields.Selection(
        [(k, PRICE_KIND_LABEL[k]) for k in PRICE_KINDS],
        default='flat', required=True,
        help="How this plan works out what to charge.")
    #: WHICH NUMBER IT READS. A plain string rather than a pointer, because the
    #: numbers are a REGISTRY supplied by the product and not rows in a table:
    #: a product that stops measuring something must leave the plan readable
    #: enough to say so, and a broken foreign key cannot.
    meter_key = fields.Char(
        help="Which of the numbers the platform measures this plan charges on.")
    meter_label = fields.Char(compute='_compute_meter_label')

    price = fields.Float(
        digits=(16, 2),
        help="The price of ONE, each month, or the whole monthly price on a "
             "flat plan. Not used by a plan priced by size band.")
    included = fields.Integer(
        default=0,
        help="How many are included before anything is charged. Nought "
             "charges from the first one.")
    minimum = fields.Float(
        digits=(16, 2), default=0.0,
        help="The least this plan charges in a month, however quiet it was. "
             "Nought means a quiet month costs nothing.")
    tier_ids = fields.One2many('biz.plan.tier', 'plan_id',
                               help="Only for a plan priced by size band.")

    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Every invoice raised from this plan is in this currency.")
    vat_rate = fields.Float(
        digits=(16, 2), default=0.0,
        help="Tax added to the invoice, as a percentage. Nought adds nothing "
             "and prints no tax line at all.")
    seat_limit = fields.Integer(
        default=0,
        help="How many people with a login this plan allows. Nought means no "
             "limit, and no limit is the default.")
    trial_days = fields.Integer(
        default=DEFAULT_TRIAL_DAYS,
        help="How long a trial on this plan lasts, in days.")

    tenant_ids = fields.One2many('biz.tenant', 'plan_id')
    tenant_count = fields.Integer(compute='_compute_tenant_count')

    # ⚠ `models.Constraint`, NOT the old `_sql_constraints` LIST — that form is
    # INERT on this framework and leaves `pg_constraint` with nothing in it
    # (ledger H63).
    _code_unique = models.Constraint(
        'UNIQUE (code)', "Another plan already has that short name.")

    @api.depends('meter_key')
    def _compute_meter_label(self):
        for plan in self:
            plan.meter_label = _meter_label(plan.meter_key)

    @api.depends('tenant_ids.state')
    def _compute_tenant_count(self):
        for plan in self:
            plan.tenant_count = len(plan.tenant_ids.filtered(
                lambda t: t.state != 'decommissioned'))

    @api.constrains('price_kind', 'tier_ids')
    def _check_tiers(self):
        for plan in self:
            if plan.price_kind == 'flat_tier' and not plan.tier_ids:
                raise ValidationError(self.env._(
                    "The %s plan charges one price by size band, so it needs "
                    "at least one band. Add the bands in the same breath as "
                    "the plan.", plan.name or ''))

    @api.constrains('price_kind', 'meter_key')
    def _check_meter(self):
        for plan in self:
            if plan.price_kind in ('per_unit', 'flat_tier') \
                    and not (plan.meter_key or '').strip():
                raise ValidationError(self.env._(
                    "The %s plan charges on one of the numbers the platform "
                    "measures, so it has to say which one.", plan.name or ''))

    # ------------------------------------------------------------------ rules
    def as_dict(self):
        """One plan as the pure rules read it (rail R6)."""
        self.ensure_one()
        cur = self.currency_id
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        return {
            'id': self.id,
            'name': self.name or '',
            'code': self.code or '',
            'blurb': self.blurb or '',
            'price_kind': self.price_kind,
            'price_kind_label': PRICE_KIND_LABEL.get(self.price_kind, ''),
            'meter_key': self.meter_key or '',
            'meter_label': _meter_label(self.meter_key),
            'price': self.price or 0.0,
            'price_h': fmt(self.price),
            'included': self.included or 0,
            'minimum': self.minimum or 0.0,
            'minimum_h': fmt(self.minimum) if self.minimum else '',
            # EVERY FIGURE THAT REACHES A SCREEN IS FORMATTED HERE, once, by
            # the one money formatter. A band shown as "9000000" is a number
            # nobody can read at a glance and nobody can check against an
            # invoice.
            'tiers': [{'id': t.id, 'up_to': t.up_to, 'price': t.price,
                       'up_to_h': qty_text(t.up_to),
                       'price_h': fmt(t.price)}
                      for t in self.tier_ids.sorted(lambda t: t.up_to)],
            'currency_id': cur.id,
            'currency': cur.name or '',
            'symbol': cur.symbol or '',
            'position': cur.position or 'after',
            'rounding': cur.rounding or 0.01,
            'vat_rate': self.vat_rate or 0.0,
            'seat_limit': self.seat_limit or 0,
            'trial_days': self.trial_days or DEFAULT_TRIAL_DAYS,
            'active': self.active,
            'sequence': self.sequence,
            'is_placeholder': self.is_placeholder,
            'tenants': self.tenant_count,
            'headline': self.headline(),
            'limit_text': self.limit_text(),
        }

    def headline(self):
        """"30,000 ₫ for each person in care, every month" — in one line."""
        self.ensure_one()
        cur = self.currency_id
        fmt = lambda v: money(v, cur.symbol or '', cur.rounding or 0.01,   # noqa: E731
                              cur.position or 'after')
        label = unit_words(_meter_label(self.meter_key))
        if self.price_kind == 'flat':
            return self.env._("%s a month", fmt(self.price))
        if self.price_kind == 'per_unit':
            # ⚠ NOT "for each <label>". The label is the product's own words
            # and it is written for a column heading, so it is nearly always a
            # PLURAL — "30,000 ₫ for each people in care" is how a screen
            # announces that a programme wrote it. The card carries a
            # "Charged on" row right underneath, which says the unit properly,
            # so the price line says the price and stops.
            base = self.env._("%s each, every month", fmt(self.price))
            if self.included:
                base += self.env._(" — the first %s are included",
                                   qty_text(self.included))
            return base
        tiers = self.tier_ids.sorted(lambda t: t.up_to)
        if not tiers:
            return self.env._("No size bands yet")
        return self.env._("From %(low)s a month, by %(unit)s",
                          low=fmt(min(tiers.mapped('price') or [0.0])),
                          unit=label)

    def limit_text(self):
        self.ensure_one()
        if not self.seat_limit:
            return self.env._("No limit on people with a login")
        return self.env._("Up to %s people with a login",
                          qty_text(self.seat_limit))

    # =====================================================================
    #  SEEDING
    # =====================================================================
    @api.model
    def ensure_seeded(self):
        """Put the product's plans in the table, once, and never again.

        ⚠ `@api.model` IS LOAD-BEARING HERE AND NOT DECORATION (ledger F45). A
        `<function>` in a data file with no arguments reads the FIRST argument
        as the records to call the method on; without the marker the upgrade
        dies on "not enough values to unpack" and the traceback names the XML
        line rather than the method it could not reach.

        ⚠ AND A BANDED PLAN IS CREATED WITH ITS BANDS, IN ONE `create`
        (ledger F60). The constraint refuses a banded plan with no bands, which
        is right — and it means a two-step seed fails in between and takes the
        whole upgrade with it.

        IT NEVER TOUCHES A PLAN THAT EXISTS. These are placeholder figures the
        owner is expected to overwrite; a seeder that put them back on every
        upgrade would undo the one decision this table exists for.
        """
        specs = common.plans()
        if not specs:
            _logger.debug("biz_tenants: no product has said what it sells.")
            return self.browse()
        have = set(self.with_context(active_test=False).sudo()
                   .search([]).mapped('code'))
        made = self.browse()
        for spec in specs:
            if spec['code'] in have:
                continue
            currency = self.env.company.currency_id
            if spec.get('currency_xmlid'):
                found = self.env.ref(spec['currency_xmlid'],
                                     raise_if_not_found=False)
                if found:
                    currency = found
                    # A currency that ships inactive prices nothing until it is
                    # switched on, and the failure looks like a wrong total.
                    if not found.active:
                        found.sudo().write({'active': True})
            made |= self.sudo().create({
                'code': spec['code'], 'name': spec['name'],
                'blurb': spec['blurb'], 'sequence': spec['sequence'],
                'price_kind': spec['price_kind'],
                'meter_key': spec['meter_key'],
                'price': spec['price'], 'included': spec['included'],
                'minimum': spec['minimum'], 'vat_rate': spec['vat_rate'],
                'seat_limit': spec['seat_limit'],
                'trial_days': spec['trial_days'] or DEFAULT_TRIAL_DAYS,
                'currency_id': currency.id,
                'is_placeholder': spec['placeholder'],
                'tier_ids': [(0, 0, {'up_to': int(t.get('up_to') or 0),
                                     'price': float(t.get('price') or 0.0),
                                     'meter_key': spec['meter_key']})
                             for t in spec['tiers']],
            })
        if made:
            _logger.info("biz_tenants: seeded %d plans from what the "
                         "product registered.", len(made))
        return made

    @api.model
    def catalogue(self):
        """Every plan, in order, seeded on first read.

        SEEDED LAZILY AS WELL AS FROM THE DATA FILE, on purpose: the data file
        runs when this module is installed or upgraded, and the product's
        overlay may be installed AFTER it.
        """
        rows = self.with_context(active_test=False).sudo().search([])
        if {p['code'] for p in common.plans()} - set(rows.mapped('code')):
            self.ensure_seeded()
            rows = self.with_context(active_test=False).sudo().search([])
        return [p.as_dict() for p in rows]


class BizPlanTier(models.Model):
    _name = 'biz.plan.tier'
    _description = 'One size band of a plan'
    _order = 'up_to, id'

    plan_id = fields.Many2one('biz.plan', required=True, ondelete='cascade',
                              index=True)
    #: Kept on the BAND as well as on the plan so a band can be read on its own
    #: — and so a plan whose meter changes leaves a band that says what it was
    #: measured against rather than one that silently means something else.
    meter_key = fields.Char()
    up_to = fields.Integer(
        required=True,
        help="The largest this band covers. The band with the highest number "
             "also covers anything above it.")
    price = fields.Float(digits=(16, 2), required=True,
                         help="What a customer in this band pays each month.")
