# -*- coding: utf-8 -*-
"""The job somebody is employed as — one field, and what writing it does.

WHY THIS LIVES HERE AND NOT IN `health_base`. It used to: `health_base` carried
a pointer at the previous access application's role, plus the four flags every
other module reads off it. `health_base` is the root of this product's
dependency tree and cannot depend on the Access home, so the moment the job
became a `biz.access.role` the field had to move up to the module that knows
what one is. THE FIELD NAMES DID NOT MOVE WITH IT: `is_doctor_role`,
`is_nurse_role`, `is_om_role` and `access_role_display` are read in sixty-odd
places across a dozen modules, and renaming them would have turned a change of
meaning into a change of vocabulary as well.

WHAT WRITING THE JOB DOES. It grants the matching role. That is the same
behaviour the previous application had — assigning a role handed out its
permissions — and it is what everybody who has ever used this clinic's staff
form expects. Two details make it safe rather than merely convenient:

  * the PREVIOUS job's role is taken back through the Access home's own
    removal, which keeps every permission another role they hold still needs;
  * only somebody who may manage access can write it at all. A staff form is
    not a permission screen, and a field on it that quietly granted permissions
    to anybody who could edit a staff record would be a permission screen
    wearing a disguise.

CLASSIFICATION IS NOT PERMISSION, AND THE ARROW ONLY POINTS ONE WAY. Setting
somebody's job gives them that role. Giving somebody a role on the Access home
does NOT change their job — an owner who is granted the Doctor bundle is still
an owner, and the roster still knows it.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

#: The sentence under the field on every form that shows it. Written once.
JOB_HELP = ("The role this person is employed as. It decides what the "
            "schedule, the pickers and the dashboards call them. Their "
            "permissions are the roles they HOLD, on the Access home.")


class ResUsers(models.Model):
    _inherit = 'res.users'

    job_role_id = fields.Many2one(
        'biz.access.role', string='Job', ondelete='restrict',
        domain="[('active', '=', True)]", help=JOB_HELP)

    is_doctor_role = fields.Boolean(
        compute='_compute_user_role_flags', store=True, readonly=True,
    )
    is_nurse_role = fields.Boolean(
        compute='_compute_user_role_flags', store=True, readonly=True,
    )

    @api.depends('job_role_id', 'job_role_id.clinical_kind')
    def _compute_user_role_flags(self):
        for user in self:
            kind = user.job_role_id.clinical_kind if user.job_role_id else False
            user.is_doctor_role = kind == 'doctor'
            user.is_nurse_role = kind == 'nurse'

    # ------------------------------------------------------------- writing it
    def write(self, vals):
        """Change the job, change the role — and only if you may.

        The old job is read BEFORE `super()`, because afterwards there is no
        way to know what it was, and the removal has to name the role that is
        going rather than the one that arrived.
        """
        if 'job_role_id' in vals:
            self._check_may_set_job()
            before = {user.id: user.job_role_id for user in self}
            result = super().write(vals)
            self._apply_job_role(before)
            return result
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any('job_role_id' in (vals or {}) for vals in vals_list):
            self._check_may_set_job()
        users = super().create(vals_list)
        users._apply_job_role({user.id: self.env['biz.access.role']
                               for user in users})
        return users

    def _check_may_set_job(self):
        """Who may say what somebody's job is.

        THE SERVER SAYS NO, NOT THE FORM. The field is on a staff record that
        plenty of people can edit, and hiding it from them would leave the
        write open to anything that is not the form. Refused in plain words,
        naming the screen where the same thing is done properly.
        """
        if self.env.su or self.env.is_superuser():
            return
        if self.env['biz.access'].can_manage():
            return
        raise AccessError(_(
            "Saying what somebody's job is also gives them that role, so it "
            "is something the access team does. Ask one of them, or open the "
            "Access home if that is you."))

    def _apply_job_role(self, before):
        """Take the old role back, then give the new one. In that order.

        THE OTHER WAY ROUND WOULD BE WRONG. Two jobs can share permissions;
        removing after granting would take back part of what was just given.

        BOTH CALLS ARE ALLOWED TO REFUSE, AND A REFUSAL IS NOT A FAILURE. The
        Access home says "they already have that" and "there is nothing here to
        remove" as `UserError`s, because on the board those are answers to a
        question somebody asked. Here nobody asked; the job simply is what it
        is, and both sentences mean "already true".
        """
        facade = self.env['biz.access'].sudo()
        for user in self:
            was = before.get(user.id) or self.env['biz.access.role']
            now = user.job_role_id
            if was == now:
                continue
            if was:
                self._quietly(facade.remove, was.id, user.id, _(
                    "%s is no longer their job.", was.name or ''))
            if now:
                self._quietly(facade.grant, now.id, user.id, _(
                    "job set on the staff record"))

    def _quietly(self, fn, role_id, user_id, reason):
        """Run one of the board's writes and swallow only its own refusals.

        `UserError` here means "nothing would change", which is the answer this
        caller wants. Anything else is a real problem and is logged with its
        traceback rather than disappearing — a job that silently failed to
        grant its role is the defect this whole field exists to prevent.
        """
        from odoo.exceptions import UserError                # noqa: PLC0415
        try:
            fn(role_id, user_id, reason=reason)
        except UserError:
            return False
        except Exception:                                    # noqa: BLE001
            _logger.warning(
                'health_access: the job change on user %s could not be '
                'applied to their roles', user_id, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------ the picker
    @api.model
    def _job_role_options(self):
        """Active roles that say what they count as, for the person action."""
        return self.env['biz.access.role'].sudo().search(
            [('active', '=', True)], order='sequence, name')

    # =========================================================== the buttons
    #
    # THE PEOPLE LIST'S OWN DOORS, AND WHY THEY ARE THREE LINES EACH.
    #
    # Switching a colleague off, switching them back on and sending a password
    # link are the three things somebody does from a list of people. They have
    # a careful set of refusals — never the platform administrator, never
    # yourself, and say plainly when there is no mail account rather than
    # reporting a send that did not happen — and those refusals are written
    # ONCE, on the Access home's passport, where the same three doors live.
    #
    # So these do not re-implement them. They call the same dispatcher the
    # passport calls, which re-checks who is asking and then re-checks whether
    # this particular act on this particular person is allowed at all. Two
    # copies of a refusal is one refusal that will eventually be reworded.
    def _run_access_action(self, action_id):
        self.ensure_one()
        result = self.env['biz.access'].run_person_action(action_id, self.id)
        action = (result or {}).get('action')
        if action:
            return action
        message = (result or {}).get('message')
        if not message:
            return True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message, 'type': 'success',
                       'sticky': False, 'next': {'type': 'ir.actions.act_window_close'}},
        }

    def action_health_deactivate(self):
        return self._run_access_action('deactivate')

    def action_health_activate(self):
        return self._run_access_action('activate')

    def action_health_reset_password_link(self):
        return self._run_access_action('reset_password')

    def action_health_open_staff(self):
        return self._run_access_action('open_staff')
