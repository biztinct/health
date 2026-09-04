# -*- coding: utf-8 -*-
"""Getting into a customer's system honestly.

THE ARGUMENT, AND IT IS THE WHOLE DESIGN. Sooner or later whoever runs this
platform has to look at a customer's screen to answer a question about it.
There are three ways to arrange that and only one of them is defensible:

  1. know somebody's password — permanent, invisible, and it is now their
     account doing whatever we do;
  2. keep an account of our own on their system — permanent and invisible;
  3. a door that has to be OPENED, for a stated reason, that CLOSES ITSELF,
     and that leaves a record THE CUSTOMER CAN READ on their own system.

This is the third. The record is written on the customer's database and not on
ours, deliberately: a trail kept by the people it is about is not a trail.

⚠ THE CUSTOMER CAN REFUSE IT ENTIRELY, and the refusal is theirs to make, on
their own screen, with no way for this side to override it
(`biz_tenancy.support_allowed`). This door reads it BEFORE it mints anything,
and refuses BY NAME. A door only one side can open is not support, it is
access.

⚠ AND THE ALERT GOES OUT ON THE PRESS OF THE BUTTON, NOT ON THE SWEEP (ledger
F67). Everything the fifteen-minute sweep announces is a fault that will still
be a fault in a quarter of an hour. A support session is an ACT: a thirty-minute
session ended after two is over before the sweep ever looks at it, and the
owner would have heard nothing at all about somebody being inside a live
customer's system.

⚠ EVERY HELPER IS NAMED FOR THIS FILE (ledger F52).
"""
import logging
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common

_logger = logging.getLogger(__name__)

#: The three time boxes on the dialog. Not free text: "how long do you need"
#: answered in a box produces 480, and a number somebody typed by accident is
#: a door left open all day.
TIME_BOXES = (15, 30, 60)

#: A reason shorter than this is not a reason. Measured against the ones people
#: actually type: "check invoice numbering for Mrs Tran" is 38 characters,
#: "look" is four.
MIN_REASON = 12


def support_link(base_url, token):
    """The one address the operator is handed. PURE."""
    return '%s/biz_tenancy/support/link/%s' % (
        (base_url or '').rstrip('/'), token)


def check_support_request(reason, minutes):
    """Is this a request the door should even consider? PURE.

    Returns `''` when it is fine, or the sentence to refuse it with. A pure
    function because the refusals are the interesting half and a test has to be
    able to reach every one of them without a customer's database.
    """
    reason = (reason or '').strip()
    if not reason:
        return ("Say why you need to go in. It is written on the customer's "
                "own record and they can read it.")
    if len(reason) < MIN_REASON:
        return ("Write a reason somebody could act on in six months — "
                "\"%s\" is not one." % reason)
    if len(reason) > 300:
        return ("Keep the reason under 300 characters. It is a line on the "
                "customer's screen, not a file note.")
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return "Choose how long you need."
    if minutes not in TIME_BOXES:
        return ("Choose %s minutes. A door with no time on it is a door "
                "somebody forgets."
                % ', '.join(str(m) for m in TIME_BOXES[:-1])
                + ' or %d' % TIME_BOXES[-1])
    return ''


class BizTenantsSupport(models.AbstractModel):
    _inherit = 'biz.tenants'

    # =====================================================================
    #  READING WHAT IS HAPPENING ON A CUSTOMER'S SYSTEM
    # =====================================================================
    def _support_rows(self, dbname, limit=10):
        """The customer's own support record, read with a plain query.

        SQL AND NOT A DATA ENVIRONMENT, for the same reason the fleet screen is
        (ACCESS H4): opening a whole registry per customer to draw a read-only
        panel would make it the most expensive thing on the machine. Guarded on
        the table existing, because a customer who has not been brought in step
        does not have it.
        """
        rows = []
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT to_regclass('public.biz_support_session')")
                if not (cr.fetchone() or [None])[0]:
                    return rows
                cr.execute(
                    "SELECT id, state, reason, minutes, operator_name, "
                    "       issued_at, opened_at, ended_at, expires_at, "
                    "       coalesce(end_reason, '') "
                    "FROM biz_support_session ORDER BY issued_at DESC, id DESC "
                    "LIMIT %s", (int(limit),))
                for r in cr.fetchall():
                    rows.append({
                        'id': r[0], 'state': r[1], 'reason': r[2],
                        'minutes': r[3], 'who': r[4] or '',
                        'issued_at': self._stamp(r[5]),
                        'opened_at': self._stamp(r[6]),
                        'ended_at': self._stamp(r[7]),
                        'expires_at': self._stamp(r[8]),
                        'end_reason': r[9],
                    })
                ids = [r['id'] for r in rows]
                if ids:
                    cr.execute(
                        "SELECT session_id, path, coalesce(name,''), count "
                        "FROM biz_support_screen WHERE session_id = ANY(%s) "
                        "ORDER BY first_seen, id", (ids,))
                    seen = {}
                    for sid, path, name, count in cr.fetchall():
                        seen.setdefault(sid, []).append(
                            {'path': path, 'name': name, 'count': count})
                    for row in rows:
                        row['screens'] = seen.get(row['id'], [])
        except Exception as e:                               # noqa: BLE001
            _logger.info("biz_tenants: could not read the support record on "
                         "%s: %s", dbname, e)
        return rows

    def _support_allowed_on(self, dbname):
        """Does this customer allow us in? `(allowed, why_not)`.

        DEFAULTS TO YES — a customer who has never been asked expects the
        people they bought the product from to be able to look when they ring
        up. But it is read from THEIR database every time: a value cached here
        would be a permission we granted ourselves.
        """
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT value FROM ir_config_parameter "
                           "WHERE key = %s", (common.T_SUPPORT_ALLOWED,))
                row = cr.fetchone()
        except Exception as e:                               # noqa: BLE001
            return False, ("This customer's system could not be asked whether "
                           "it allows support access (%s), so nothing was "
                           "opened." % e)
        if not row or row[0] in (None, ''):
            return True, ''
        if str(row[0]).strip().lower() in ('0', 'false', 'no', 'off'):
            return False, ''
        return True, ''

    def _support_recovery_uid(self, dbname):
        """Which account on the customer's system the link signs in as.

        THE RECOVERY ACCOUNT AND NEVER A PERSON'S. It has no password, so it
        cannot be signed into by anybody who has not been handed a link by this
        door — which is what makes the record complete.
        """
        login = common.param(self.env, common.P_RECOVERY_LOGIN) or ''
        with self._pg_cursor(dbname) as cr:
            if login:
                cr.execute("SELECT id FROM res_users WHERE login = %s AND "
                           "active", (login,))
                row = cr.fetchone()
                if row:
                    return row[0], login
            # No setting, or the setting names an account that is not there.
            # Fall back to the one account a blank system ships with that has
            # no password, and SAY which one was used — guessing silently is
            # how somebody ends up signed in as the wrong account.
            cr.execute("SELECT id, login FROM res_users "
                       "WHERE active AND password IS NULL AND NOT share "
                       "AND login NOT IN ('admin', '__system__') "
                       "ORDER BY id LIMIT 1")
            row = cr.fetchone()
        if not row:
            return 0, ''
        return row[0], row[1]

    # =====================================================================
    #  THE SCREEN
    # =====================================================================
    @api.model
    def support_data(self, tenant_id):
        """What the cockpit shows about getting into ONE customer's system."""
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not here any more."))
        allowed, why = self._support_allowed_on(tenant.slug)
        return {
            'tenant_id': tenant.id,
            'tenant': tenant.name,
            'slug': tenant.slug,
            'allowed': allowed,
            'blocked_reason': why,
            'time_boxes': list(TIME_BOXES),
            'min_reason': MIN_REASON,
            'sessions': self._support_rows(tenant.slug),
            'note': ("Everything below is written on %s's own system, where "
                     "their own people can read it — not here." % tenant.name),
        }

    # =====================================================================
    #  OPENING THE DOOR
    # =====================================================================
    @api.model
    def support_start(self, tenant_id, reason, minutes=30):
        """A reason, a time box, one link. The whole act."""
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not here any more."))
        if tenant.state != 'live':
            raise UserError(self.env._(
                '"%(name)s" is not live (%(state)s), so there is nothing to '
                'go into.', name=tenant.name, state=tenant.state))
        problem = check_support_request(reason, minutes)
        if problem:
            raise UserError(problem)
        reason = reason.strip()
        minutes = int(minutes)

        if not self._db_exists(tenant.slug):
            raise UserError(self.env._(
                'There is no system called "%s".', tenant.slug))

        # ---- the customer's own refusal, read from THEIR database --------
        allowed, why = self._support_allowed_on(tenant.slug)
        if not allowed:
            self._support_mark_refusal(tenant, reason, minutes)
            raise UserError(self.env._(
                '%(name)s has switched support access off on their own '
                'system, so no link was made. %(extra)sThey can switch it '
                'back on from their About screen; nobody here can do it for '
                'them.',
                name=tenant.name, extra=('%s ' % why) if why else ''))

        uid, login = self._support_recovery_uid(tenant.slug)
        if not uid:
            raise UserError(self.env._(
                'There is no account on "%s" that a support link could sign '
                'in as. The blank system ships with one; this customer has '
                'none, so nothing was opened.', tenant.slug))

        token = secrets.token_urlsafe(32)
        operator = self.env.user.name or self.env.user.login
        brand = common.brand(self.env) or 'the platform'
        with self._tenant_env(tenant.slug) as env:
            session_id = env['biz.support.session'].mint({
                'reason': reason, 'minutes': minutes,
                'token_sha': self._support_token_sha(token),
                'operator_name': operator,
                'platform_name': brand,
                'platform_url': self._platform_url(),
                'user_id': uid,
            })
        link = support_link(self._tenant_url(tenant.slug), token)
        tenant.log('A support link was made for %s: %d minutes — "%s". It '
                   'signs in as %s.' % (operator, minutes, reason, login))
        self._support_announce(tenant, reason, minutes, operator)
        _logger.info("biz_tenants: support link for %s (%d min) by %s",
                     tenant.slug, minutes, operator)
        return {
            'ok': True,
            'link': link,
            'session_id': session_id,
            'minutes': minutes,
            'expires_words': ("The link stops working in %d minutes if nobody "
                              "uses it." % minutes),
            'message': ("The link is below. It works ONCE, it signs you in as "
                        "the recovery account for %d minutes, and %s can read "
                        "what you opened afterwards on their own screen."
                        % (minutes, tenant.name)),
        }

    def _support_token_sha(self, token):
        import hashlib
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def _support_mark_refusal(self, tenant, reason, minutes):
        """⚠ A REFUSAL LEAVES ITS MARK ON THE CUSTOMER'S OWN RECORD.

        The point of a trail is that it records the attempts as well as the
        entries. A customer who has switched support off wants to know that
        somebody tried, and finding out only from us would defeat the whole
        arrangement.
        """
        try:
            with self._tenant_env(tenant.slug) as env:
                env['biz.support.session'].refuse({
                    'reason': reason, 'minutes': minutes,
                    'operator_name': self.env.user.name or '',
                    'platform_name': common.brand(self.env) or '',
                    'platform_url': self._platform_url(),
                    'refusal': ("This system has support access switched off, "
                                "so the link was refused."),
                })
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: the refused support request could "
                            "not be written on %s's own record", tenant.slug,
                            exc_info=True)
        tenant.log('A support link was REFUSED: they have support access '
                   'switched off. Reason given was "%s".' % reason)
        self._support_announce(tenant, reason, minutes,
                               self.env.user.name or '', refused=True)
        # ⚠ THE REFUSAL IS ABOUT TO RAISE, AND A RAISE ROLLS BACK ITS OWN
        # RECORD OF ITSELF. Found live: the mark on the CUSTOMER's record
        # survived (it is written through their own cursor, which commits),
        # and everything written on OUR side — the alert and the line in their
        # log — vanished with the exception that carried the refusal to the
        # screen. So the platform had no record of an attempt the customer
        # could see, which is the wrong way round.
        #
        # This is F64's lesson on the writing side rather than the testing
        # side: whenever the POINT of a refusal is that it leaves something
        # behind, the something has to be committed before the refusal is
        # thrown. Nothing else has been written in this transaction by the time
        # this runs, so there is nothing else to commit with it.
        self.env.flush_all()
        self.env.cr.commit()

    def _support_announce(self, tenant, reason, minutes, operator,
                          refused=False):
        """Raise the alert NOW, on the press (ledger F67).

        Dark like everything else on this platform — there is no outgoing mail
        account — so it is recorded on the Alerts screen, which is the channel.
        """
        Alert = self.env['biz.alert'].sudo()
        kind = 'support_refused' if refused else 'support_session'
        key = '%s:%s' % (kind, tenant.slug)
        now = fields.Datetime.now()
        subject = (("Somebody was refused entry to %s" % tenant.name)
                   if refused else
                   ("%s went into %s" % (operator or 'Somebody', tenant.name)))
        text = (
            '%(who)s %(verb)s %(name)s for %(mins)d minutes.\n\n'
            'Reason given: "%(reason)s"\n\n'
            '%(tail)s'
            % {'who': operator or 'Somebody on this platform',
               'verb': ('was refused entry to' if refused else 'opened a '
                        'support session on'),
               'name': tenant.name, 'mins': minutes, 'reason': reason,
               'tail': ("They have switched support access off on their own "
                        "system. Nothing was opened, and the attempt is on "
                        "their own record."
                        if refused else
                        "It closes on its own at the time box, and every "
                        "screen opened is written on their own record where "
                        "they can read it.")})
        existing = Alert.search([('key', '=', key),
                                 ('state', 'in', ('open', 'acknowledged'))],
                                limit=1)
        if existing:
            existing.write({'last_seen': now, 'count': existing.count + 1,
                            'subject': subject, 'body_text': text,
                            'state': 'open'})
            alert = existing
        else:
            alert = Alert.create({
                'key': key, 'kind': kind,
                'severity': 'warning' if refused else 'info',
                'subject': subject, 'body_text': text,
                'tenant_id': tenant.id, 'first_seen': now, 'last_seen': now,
                'count': 1, 'state': 'open', 'channel_state': 'dark',
            })
        # Announced on the press, through the same honest channel as
        # everything else: it returns ('dark', reason) rather than raising or
        # queueing a message nobody will ever receive.
        state, why = self._send_alert_mail(subject, text)
        if state == 'sent':
            alert.write({'spoken_at': now, 'spoken_severity': alert.severity,
                         'channel_state': 'sent', 'channel_reason': ''})
        else:
            alert.write({'channel_state': state, 'channel_reason': why})
        return alert

    # =====================================================================
    #  CLOSING IT
    # =====================================================================
    @api.model
    def support_end(self, tenant_id, session_id=None):
        """End it from this side. The operator's own bar can do it too."""
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not here any more."))
        ended = 0
        with self._tenant_env(tenant.slug) as env:
            Session = env['biz.support.session'].sudo()
            rows = (Session.browse(int(session_id)).exists() if session_id
                    else Session.search([('state', 'in', ('issued', 'active'))]))
            if rows:
                rows.finish('operator')
                ended = len(rows)
        if ended:
            tenant.log('The support session was ended from the platform.')
            self._support_resolve_alerts(tenant)
        return {'ok': True, 'ended': ended,
                'sessions': self._support_rows(tenant.slug),
                'message': ("Ended." if ended else
                            "There was nothing open to end.")}

    def _support_resolve_alerts(self, tenant):
        """Close the alert when the door is shut.

        ⚠ `issued` COUNTS AS RUNNING (ledger F68). A link that has been made
        and not yet used is a door about to open; treating it as "nothing is
        running" closes the alert about a session that has not begun.
        """
        pending = [r for r in self._support_rows(tenant.slug, limit=5)
                   if r['state'] in ('issued', 'active')]
        if pending:
            return False
        alerts = self.env['biz.alert'].sudo().search([
            ('key', '=', 'support_session:%s' % tenant.slug),
            ('state', 'in', ('open', 'acknowledged'))])
        if alerts:
            alerts.write({'state': 'resolved',
                          'resolved_at': fields.Datetime.now(),
                          'resolution': "The support session ended."})
        return bool(alerts)
