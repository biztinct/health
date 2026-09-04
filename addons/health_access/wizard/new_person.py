# -*- coding: utf-8 -*-
"""Somebody new is starting on Monday — the whole of it, on one form.

WHAT IT ACTUALLY DOES, AND WHY IT IS ONE FORM. A new colleague needs three
things that live in three different places: a login, a staff record, and a role.
Done separately they drift — the login exists and the staff record does not, or
the staff record says "Da Nang" and the login was never given an area — and the
drift is invisible until somebody cannot see their own visits. So the three are
one form, and either all three happen or none of them does.

WHAT MAKES IT SAFE FOR SOMEBODY WHO IS NOT THE SYSTEM ADMINISTRATOR. Creating a
user is the most dangerous write in any system: whoever can do it can, in
principle, create one with the keys to the box. Three things stop that here, and
all three are on the server:

  * the fields that reach `res.users` are a WHITELIST, so nothing arrives that
    was not asked for on this form;
  * the role is refused if it carries — or merely IMPLIES, over the whole
    closure — the system administrator permission, which is how an
    ordinary-looking wrapper group smuggled one in once before;
  * the role is granted through the Access home's own `grant`, so the permissions
    added are exactly the role's and the audit trail records that it happened.

THE QUALIFIERS ARE ASKED BY ABILITY, NEVER BY THE NAME OF THE ROLE. "Is this a
duty doctor" is offered when the role actually carries the ability to practise
as a doctor — not when its name contains the word "doctor". A role called
"Doctor's assistant" would have matched the substring and not the job, and a
role called "Bác sĩ" would have matched neither.

BOTH LANES, WHILE THERE ARE TWO. The person is given the new bundle AND, where
the previous access application is still installed and has a role of the same
name, that role too — so somebody added today looks exactly like somebody added
last week to every screen that has not moved across yet.
"""

import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.biz_access.models.access_common import forbidden_in_closure

_logger = logging.getLogger(__name__)

#: Which qualifier is offered for which ability. By KEY, because a key is fixed
#: and a name is something an administrator is invited to reword.
DOCTOR_ABILITIES = ('doctoring',)
NURSE_ABILITIES = ('nursing', 'head-nursing')

#: Everything that may reach `res.users` from this form, and nothing else.
USER_FIELDS = ('name', 'login', 'password', 'phone', 'company_id',
               'company_ids', 'lang', 'tz')


class HealthAccessNewPerson(models.TransientModel):
    """The form itself is open to anybody with a login; the BUTTON is not.

    A transient record belongs to the person who made it and is swept away by
    the framework, so the row is worth nothing to anybody. The gate that matters
    is on `action_create`, on the server, where it is asked again whichever way
    the form was reached — and it has to be there anyway, because a screen that
    was only hidden is a screen somebody can call around.

    The alternative — naming this clinic's administrator permission in the
    access file — would tie this module to the very module it exists to make
    replaceable, and would refuse to install on the day that one is gone.
    """

    _name = 'health.access.new.person'
    _description = 'Add a person'

    name = fields.Char(string='Their name', required=True)
    login = fields.Char(
        string='Email they sign in with', required=True,
        help='It is both their username and where a password link would go.')
    phone = fields.Char(string='Phone')
    password = fields.Char(
        string='First password',
        help='Leave it empty and they set their own from a link — which needs '
             'an outgoing mail account to be connected.')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    lang = fields.Selection(
        '_get_lang', string='Language',
        default=lambda self: self.env.lang or 'en_US')
    tz = fields.Selection(
        '_tz_get', string='Timezone',
        default=lambda self: (self.env.context.get('tz')
                              or self.env.user.tz or 'Asia/Ho_Chi_Minh'))

    role_id = fields.Many2one(
        'biz.access.role', string='What they will do',
        domain="[('active', '=', True)]",
        help='The job they are being given. What it lets somebody do is on its '
             'own card in the Access home.')
    role_description = fields.Text(
        string='What that lets them do', related='role_id.description',
        readonly=True)

    is_duty_doctor = fields.Boolean(string='On the duty roster')
    is_head_nurse = fields.Boolean(string='Leads a nursing team')
    show_duty_doctor = fields.Boolean(compute='_compute_show_qualifiers')
    show_head_nurse = fields.Boolean(compute='_compute_show_qualifiers')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Area they work in',
        options="{'no_create': True}")
    healthcare_facility_id = fields.Many2one(
        'health.facility', string='Where they are based',
        domain="[('catchment_province_id', '=', catchment_province_id)]")

    employment_status = fields.Selection([
        ('active', 'Working'),
        ('on_leave', 'On leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Left'),
    ], string='Status', default='active')
    # THE KIND OF CONTRACT IS A LIST THE CLINIC EDITS, NOT A FIXED SET.
    #
    # It used to be three hard-coded options on the staff record and is now a
    # row in the clinic's own lookup lists, so the form asks for the same thing
    # the staff record itself asks for. The older "add a user" form was never
    # moved across and still writes the field that was removed — which is why
    # it fails on this database and this one does not.
    #
    # A LIST OF WORDS, NOT A POINTER AT A ROW — and that is about who is filling
    # this form in. The lists behind the clinic's dropdowns are readable only by
    # the people who MAINTAIN them, and somebody whose job is adding colleagues
    # is an administrator of people, not of reference data. A pointer field would
    # refuse to render for exactly the person this form is for (it did, the first
    # time it was run). So the choices are read once, with `sudo()`, and what is
    # stored here is the code; the row is looked up again, with `sudo()`, when
    # the staff record is written.
    employment_type_code = fields.Selection(
        selection='_employment_types', string='Kind of contract',
        default=lambda self: self._default_employment_type())

    # ------------------------------------------------------------- the lists
    @api.model
    def _get_lang(self):
        return self.env['res.lang'].get_installed()

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in sorted(
            pytz.all_timezones,
            key=lambda tz: tz if not tz.startswith('Etc/') else '_')]

    @api.model
    def _employment_types(self):
        """The kinds of contract this clinic keeps, in its own words."""
        rows = self.env['health.lookup.value'].sudo().search(
            [('category_code', '=', 'employment_type'), ('active', '=', True)],
            order='sequence, id')
        return [(r.code, r.display_name or r.code) for r in rows if r.code]

    @api.model
    def _default_employment_type(self):
        """The same default the staff record itself would have used.

        `_default_for` hands back an ID rather than a record — it is written to
        be usable as a column default, where a recordset would be wrong — so it
        is browsed here rather than treated as one.
        """
        Lookup = self.env['health.lookup.value'].sudo()
        row_id = Lookup._default_for('employment_type', 'full_time')
        row = Lookup.browse(row_id).exists() if row_id else Lookup.browse()
        return row.code if row else False

    def _employment_type_row(self):
        """The row behind the word, looked up when the record is written."""
        if not self.employment_type_code:
            return self.env['health.lookup.value'].browse()
        return self.env['health.lookup.value'].sudo().search(
            [('category_code', '=', 'employment_type'),
             ('code', '=', self.employment_type_code)], limit=1)

    # -------------------------------------------------------- the qualifiers
    @api.depends('role_id', 'role_id.ability_ids')
    def _compute_show_qualifiers(self):
        """Offered when the role carries the ABILITY, never when the name
        happens to contain the word."""
        for rec in self:
            keys = set(rec.role_id.sudo().ability_ids.mapped('technical_key'))
            rec.show_duty_doctor = bool(keys & set(DOCTOR_ABILITIES))
            rec.show_head_nurse = bool(keys & set(NURSE_ABILITIES))

    @api.onchange('role_id')
    def _onchange_role_id(self):
        """A qualifier that no longer applies is cleared rather than hidden.

        Hidden and still set is how somebody ends up on the duty roster because
        of a role they were given for ten seconds before it was changed.
        """
        self._compute_show_qualifiers()
        if not self.show_duty_doctor:
            self.is_duty_doctor = False
        if not self.show_head_nurse:
            self.is_head_nurse = False

    @api.onchange('catchment_province_id')
    def _onchange_catchment_province_id(self):
        self.healthcare_facility_id = False

    # ------------------------------------------------------------- doing it
    def action_create(self):
        """The login, the staff record and the role — or none of the three."""
        self.ensure_one()
        facade = self.env['biz.access']
        if not facade.can_manage():
            raise UserError(_(
                "Adding a colleague is something the access team does. You "
                "can still hand your own access to somebody for a while — "
                "that is the Hand-overs tab."))

        login = (self.login or '').strip()
        if not login:
            raise ValidationError(_("An email to sign in with is required."))
        clash = self.env['res.users'].sudo().with_context(
            active_test=False).search([('login', '=ilike', login)], limit=1)
        if clash:
            raise ValidationError(_(
                "Somebody already signs in with %(login)s — %(who)s. Two "
                "logins cannot share an address; use a different one, or "
                "switch that account back on if it is the same person.",
                login=login, who=clash.name or ''))

        role = self.role_id.sudo()
        if role:
            self._check_role_is_safe(role)

        company = self.company_id or self.env.company
        vals = {
            'name': (self.name or '').strip(),
            'login': login,
            'phone': self.phone or False,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'lang': self.lang,
            'tz': self.tz,
        }
        if self.password:
            vals['password'] = self.password
        # THE WHITELIST, APPLIED RATHER THAN ASSUMED. The dict above is written
        # right here and could hardly contain a surprise — which is exactly the
        # kind of confidence that stops being true after the third person edits
        # this method.
        vals = {k: v for k, v in vals.items() if k in USER_FIELDS}

        user = self.env['res.users'].sudo().create(vals)
        user.write({
            'is_healthcare_staff': True,
            'is_duty_doctor': bool(self.is_duty_doctor),
            'is_head_nurse': bool(self.is_head_nurse),
            'catchment_province_id': self.catchment_province_id.id or False,
        })

        if role:
            # Through the Access home's own grant, so the permissions added are
            # exactly the role's and the history records that it happened.
            facade.sudo().grant(role.id, user.id, reason=_(
                "Given when %s was added.", self.name or ''))
            self._also_write_the_older_lane(user, role)

        employee_vals = {
            'name': (self.name or '').strip(),
            'user_id': user.id,
            'company_id': company.id,
            'is_healthcare_staff': True,
            'is_duty_doctor': bool(self.is_duty_doctor),
            'is_head_nurse': bool(self.is_head_nurse),
            'healthcare_facility_id': self.healthcare_facility_id.id or False,
            'staff_catchment_province_id': (
                self.catchment_province_id.id or False),
            'employment_status': self.employment_status or 'active',
        }
        contract = self._employment_type_row()
        if contract:
            employee_vals['employment_type_id'] = contract.id
        self.env['hr.employee'].sudo().create(employee_vals)

        _logger.info(
            'health_access: %s was added by %s with the "%s" role',
            login, self.env.user.login, role.name if role else 'no')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self._welcome_line(user, role),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _welcome_line(self, user, role):
        """What actually happened, in the order somebody cares about it."""
        if role and not self.password:
            return _(
                "%(who)s can sign in as %(login)s and holds \"%(role)s\". They "
                "have no password yet — send them a reset from their card.",
                who=user.name or '', login=user.login or '',
                role=role.name or '')
        if role:
            return _("%(who)s can sign in as %(login)s and holds \"%(role)s\".",
                     who=user.name or '', login=user.login or '',
                     role=role.name or '')
        return _(
            "%(who)s can sign in as %(login)s. They hold no role yet — give "
            "them one from their card whenever you are ready.",
            who=user.name or '', login=user.login or '')

    def _check_role_is_safe(self, role):
        """The absolute, once more, before anything is created.

        The role model refuses it and the Access home refuses it again; this is
        the third, and it is here because this form is reached by people who
        deliberately do NOT have the keys to the box. Over the whole implied
        closure, because the one route that has ever got past a direct check is
        an ordinary-looking group that merely implies the dangerous one.
        """
        bad = forbidden_in_closure(role.group_ids, self.env)
        if bad:
            raise UserError(_(
                "\"%(role)s\" would carry %(bad)s — the administrator "
                "permission for the whole system. It is never given out from "
                "this screen.",
                role=role.name or '',
                bad=', '.join('"%s"' % (g.display_name or g.name or '')
                              for g in bad)))
        if not role.group_ids:
            raise UserError(_(
                "\"%s\" does not hand out anything yet, so giving it to "
                "somebody would give them nothing.", role.name or ''))

    def _also_write_the_older_lane(self, user, role):
        """Keep the two lanes in step while there are two.

        Somebody added today has to look exactly like somebody added last week
        to every screen that has not moved across yet — the left menu's older
        gate, and the top-bar rule the previous application still enforces.
        Guarded, so the day that application is uninstalled this simply does
        nothing.
        """
        if 'access.role' not in self.env:
            return False
        if 'access_role_id' not in self.env['res.users']._fields:
            return False
        old = self.env['access.role'].sudo().with_context(
            active_test=False).search([('name', '=', role.name)], limit=1)
        if not old:
            return False
        try:
            user.sudo().write({'access_role_id': old.id})
        except Exception:                               # noqa: BLE001
            _logger.warning(
                'health_access: %s was added but the older access app could '
                'not be told about their role', user.login, exc_info=True)
            return False
        return True
