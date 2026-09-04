# -*- coding: utf-8 -*-
"""What the clinic lets somebody DO about a colleague, from the People lens.

WHY THESE FOUR AND NOT OTHERS. The People lens answers "what does this person
have", and the moment somebody has that answer the next thing they want is
almost never another access question. It is: this person has left, switch them
off. This person is new, add them. This person cannot get in, send them a reset.
This person's details are wrong, open their staff record. Four doors, and every
one of them used to mean leaving this screen for another one.

THE REFUSALS ARE THE POINT, AND THEY ARE NOT NEW. Every one of these is a thing
this clinic could already do, on an older screen, with a set of refusals somebody
thought about carefully: never switch off the system administrator, never switch
off yourself, never reset the system administrator's password unless you are
them. Those sentences are carried across word for word rather than rewritten,
because a refusal that is reworded is a refusal somebody has to re-argue.

AND THEY ARE CHECKED ON DISPATCH, NOT ON DRAWING. A button that is not drawn is
not a rule; it is a hidden button. `run_person_action` in the module underneath
asks again who is calling, and each handler here asks again whether THIS act on
THIS person is one anybody may do.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BizAccess(models.AbstractModel):
    _inherit = 'biz.access'

    # ====================================================== the re-run doors
    #
    # A HOOK DOES NOT FIRE ON AN UPGRADE. The carry-over runs the day this
    # module lands and never again on its own, so a permission that arrives with
    # a module installed later in the same cascade — or a role somebody adds to
    # the previous application next month — would be missed for good. These two
    # are the doors that close that: the first re-runs the carry-over, the
    # second re-runs the proof.
    #
    # Both are idempotent and neither is wired to a button. The caller is
    # somebody who has just installed something, or somebody checking.

    @api.model
    def carry_over_legacy_access(self):
        """Write anything the previous application holds that is not here yet."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "Re-running the carry-over is something a system "
                "administrator does."))
        from ..hooks import migrate_legacy      # noqa: PLC0415 - see below
        # Imported here rather than at the top of the file: this module's
        # `__init__` loads `models` BEFORE `hooks`, and a top-level import would
        # tie the two together for the sake of one call.
        return migrate_legacy(self.env)

    @api.model
    def carry_over_diff(self, path=None):
        """Every colleague, before and after, for both menus. Reads only.

        Safe on a live database and meant to be run there — three fabricated
        users prove the rule, and only the real seventy prove the clinic.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "The before-and-after report is something a system "
                "administrator runs."))
        from .. import diff                     # noqa: PLC0415 - as above
        if path:
            return diff.write(self.env, path)
        return diff.as_markdown(self.env)

    @api.model
    def retire_legacy_access(self):
        """Everything that has to be true before the old application goes.

        The job on every record, what each role counts as, the clinic's own
        administrator tier, and who may build a report. Idempotent, and it runs
        correctly on a database that never had the old application — which is
        what makes it a migration rather than a one-off script.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "Retiring the previous access application is something a "
                "system administrator does."))
        from ..hooks import retire_legacy        # noqa: PLC0415 - as above
        return retire_legacy(self.env)

    @api.model
    def access_snapshot(self, path=None):
        """What everybody can see right now, written down. Reads only.

        Run once before a change of this size and once after, and compare the
        two files: it is the only honest way to prove that a retirement took
        nothing away, because no single moment holds both answers.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "The before-and-after snapshot is something a system "
                "administrator runs."))
        from .. import diff                      # noqa: PLC0415 - as above
        if path:
            return diff.write_snapshot(self.env, path)
        return diff.snapshot(self.env)

    @api.model
    def access_snapshot_diff(self, before_path, path=None):
        """The snapshot from before this change, against the way things are."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "The before-and-after report is something a system "
                "administrator runs."))
        from .. import diff                      # noqa: PLC0415 - as above
        if path:
            return diff.write_compare(self.env, before_path, path)
        return diff.compare_markdown(self.env, before_path)

    # ============================================================ the header
    def _people_actions(self):
        """One door: somebody new is starting.

        It opens the clinic's own form rather than doing anything itself,
        because adding a colleague is half a dozen decisions (where they work,
        what they do, which role) and a button that made those decisions for
        anybody would be a button nobody could use twice.
        """
        return [{
            'id': 'new_person',
            'label': _("Add a person"),
            'icon': 'userPlus',
            'action_xmlid': 'health_access.action_health_access_new_person',
            'context': {},
        }]

    # ========================================================== the passport
    def _person_actions(self, user):
        """What can be done about THIS person, worked out for this person.

        The list changes with them — somebody already switched off is offered
        "switch back on" and not "switch off" — because a screen that offers an
        action it is about to refuse has wasted somebody's press to tell them
        something it already knew.
        """
        target = user.sudo()
        rows = []
        if target.active:
            rows.append({
                'id': 'deactivate',
                'label': _("Switch off"),
                'icon': 'powerOff',
                'kind': 'run',
                'danger': True,
                'confirm': _(
                    "Switch off %s? They will not be able to sign in, and "
                    "nothing they have done is removed. You can switch them "
                    "back on here whenever you want.", target.name or ''),
            })
        else:
            rows.append({
                'id': 'activate',
                'label': _("Switch back on"),
                'icon': 'checkCircle',
                'kind': 'run',
            })
        rows.append({
            'id': 'reset_password',
            'label': _("Send a password reset"),
            'icon': 'mail',
            'kind': 'run',
            'confirm': _("Email %s a link to set a new password?",
                         target.name or ''),
        })
        rows.append({
            'id': 'set_job',
            'label': _("Change their job"),
            'icon': 'briefcase',
            'kind': 'open',
        })
        rows.append({
            'id': 'open_staff',
            'label': _("Their staff record"),
            'icon': 'idCard',
            'kind': 'open',
        })
        return rows

    # ------------------------------------------------------------- the deeds
    def _person_action_deactivate(self, user):
        """Switch somebody off. Never the system administrator, never yourself.

        Archiving and not deleting, for the same reason the audit trail has no
        delete button: what somebody did here is part of the record, and a
        removed account leaves every row that points at it saying nothing.
        """
        target = user.sudo()
        self._biz_refuse_if_system(target, _(
            "%s is the system administrator for this box. Switching them off "
            "is not something this screen does — it would leave the system "
            "with nobody able to fix it.", target.name or ''))
        if target.id == self.env.uid:
            raise UserError(_("You cannot switch off your own account."))
        if not target.active:
            raise UserError(_("%s is already switched off.",
                              target.name or ''))
        target.write({'active': False})
        return {'message': _(
            "%s is switched off. They cannot sign in, and everything they did "
            "is still here.", target.name or '')}

    def _person_action_activate(self, user):
        target = user.sudo()
        if target.active:
            raise UserError(_("%s is already able to sign in.",
                              target.name or ''))
        target.with_context(active_test=False).write({'active': True})
        return {'message': _("%s can sign in again.", target.name or '')}

    def _person_action_reset_password(self, user):
        """Send the standard reset link — and say plainly when it cannot go.

        THE HONEST FAILURE IS THE FEATURE HERE. This clinic has no outgoing mail
        account connected, so the link is written and never sent, and a screen
        that reported "sent" would send somebody to wait by an inbox for
        something that is not coming. So the state of the mail account is
        checked FIRST, and the refusal names what is missing and who fixes it.
        """
        target = user.sudo()
        if target.id != self.env.uid:
            self._biz_refuse_if_system(target, _(
                "%s is the system administrator for this box. Their password "
                "is reset on their own record, deliberately.",
                target.name or ''))
        if not target.email and not target.login:
            raise UserError(_(
                "%s has no email address on their record, so there is nowhere "
                "to send the link. Add one first.", target.name or ''))
        if not self.env['ir.mail_server'].sudo().search_count([], limit=1):
            raise UserError(_(
                "No outgoing mail account is connected yet, so the link would "
                "be written and never sent. Connect one first and this will "
                "work as it reads."))
        if not hasattr(target, 'action_reset_password'):
            raise UserError(_(
                "Setting a password by link is not switched on for this "
                "system, so there is nothing to send."))
        target.action_reset_password()
        return {'message': _(
            "A link to set a new password is on its way to %s.",
            target.email or target.login or '')}

    def _person_action_set_job(self, user):
        """Open the one-field form that says what somebody is employed as.

        A door, not a deed, for the same reason "add a person" is: choosing a
        job is a choice, and a button that made it would be a button nobody
        could use twice. The form re-checks who is asking on the server.
        """
        target = user.sudo()
        return {
            'message': '',
            'action': {
                'type': 'ir.actions.act_window',
                'name': _("%s — what they are employed as", target.name or ''),
                'res_model': 'health.access.set.job',
                'view_mode': 'form',
                'views': [[self.env.ref(
                    'health_access.view_health_access_set_job_form').id,
                    'form']],
                'target': 'new',
                'context': {'default_user_id': target.id},
            },
        }

    def _person_action_open_staff(self, user):
        """Open the staff record, or say plainly that there is not one.

        A door, not a deed: the answer carries an action and the browser opens
        it. The Access home is the wrong place to edit a joining date, and
        pretending otherwise would grow a second staff form nobody maintains.
        """
        target = user.sudo()
        if 'hr.employee' not in self.env:
            raise UserError(_("Staff records are not part of this system."))
        employee = self.env['hr.employee'].sudo().with_context(
            active_test=False).search([('user_id', '=', target.id)], limit=1)
        if not employee:
            raise UserError(_(
                "%s has a login but no staff record. Add one from the staff "
                "list and it will open from here afterwards.",
                target.name or ''))
        return {
            'message': '',
            'action': {
                'type': 'ir.actions.act_window',
                'name': _("%s — staff record", target.name or ''),
                'res_model': 'hr.employee',
                'res_id': employee.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            },
        }

    # -------------------------------------------------------------- the rail
    @api.model
    def _biz_refuse_if_system(self, target, sentence):
        """The one refusal that is the same on every one of these doors.

        AND IT FAILS CLOSED. If whether somebody is the system administrator
        cannot be worked out, the answer is "refuse", not "carry on": a check
        that cannot be made has not passed.
        """
        try:
            is_system = target.has_group('base.group_system')
        except Exception:                               # noqa: BLE001
            _logger.warning(
                'health_access: could not tell whether %s is the system '
                'administrator — refusing rather than guessing', target.id,
                exc_info=True)
            is_system = True
        if is_system:
            raise UserError(sentence)
