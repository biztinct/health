# -*- coding: utf-8 -*-
"""Developer mode belongs to the person who owns the box.

WHAT IT ACTUALLY IS. `?debug=1` on any address turns on the framework's
technical layer: raw field names on every form, the technical menus, the
"open the view" tools, the assets in their unminified form. On a product that
has been given a curated vocabulary — roles in plain English, a rail somebody
designed, screens named for the work rather than for the table underneath — it
is a switch that turns all of that off and shows the machinery instead.

It is not a permission, and it grants none. Everything behind it is still
governed by `ir.model.access` and the record rules. What it does is put a
different product in front of somebody who was given this one, and it does it
from the address bar, which means anybody who has ever seen the trick can do it
and nobody who has not will ever know it was possible.

There is also one thing it plainly should not do, and does today: the sign-in
page renders a **"Log in as superuser"** button when the page is rendered in
debug. Nobody is signed in on that page, so there is no one to ask whether they
are allowed — and the answer, on a white-labelled product, is that the button
should not be drawn at all.

THE FIRST SEAM. `web`'s `ir.http._handle_debug` copies the query string into
`request.session.debug` during `_pre_dispatch`, and the web client reads it back
off the session (`session_info`'s `bundle_params`). So there is one place to
stand for the whole backend: immediately after `_pre_dispatch`, before anything
has read it.

THE SECOND SEAM, AND IT HAD TO BE FOUND BY RUNNING IT. Emptying the session is
NOT enough for the sign-in page, because that page never reads the session for
this: `web_login` copies a whitelist of QUERY-STRING parameters straight into the
template values, and `debug` is on that whitelist. The button therefore came back
on a page whose session had already been cleared — the rail firing correctly and
the page ignoring it. `ir.qweb._prepare_environment` is where the two meet, and
forcing the template's `debug` to agree with the session there is what makes the
rule one rule rather than two that can disagree.

TWO THINGS THAT LOOK LIKE DETAILS AND ARE NOT.

  * **The environment is not on the person yet.** At `_pre_dispatch` a request
    to a public route carries the public user, and one to the backend may not
    have swapped in the signed-in user's environment. So who is asking is read
    from `request.session.uid` and browsed with `sudo()` — never from
    `self.env.user`, which on the sign-in page is nobody at all.
  * **The switch has an off switch.** `biz_access.debug_block = off` puts the
    framework's behaviour back for a database where somebody needs it, without
    a deploy. Anything else — including the parameter being absent, which is the
    normal state — means on.
"""

import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

#: Anything but this word means the block is on. Written as "which value turns
#: it OFF" rather than "which turns it on" so that a typo, an empty string or a
#: missing row all fail SAFE.
DEBUG_BLOCK_PARAM = 'biz_access.debug_block'


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        """The framework reads `?debug=` here; this takes it back off."""
        super()._pre_dispatch(rule, args)
        cls._biz_access_block_debug()

    @classmethod
    def _biz_access_block_debug(cls):
        """Empty the session's debug flag unless a system administrator asked.

        Cheap by construction: almost every request has no debug flag at all, so
        the first line ends it before anything is read.
        """
        try:
            if not request or not request.session.debug:
                return
            env = request.env
            setting = env['ir.config_parameter'].sudo().get_param(
                DEBUG_BLOCK_PARAM, 'on')
            if str(setting or '').strip().lower() == 'off':
                return
            uid = request.session.uid
            if uid:
                user = env['res.users'].sudo().browse(uid).exists()
                if user and user.has_group('base.group_system'):
                    return
            # Nobody signed in (the sign-in page), or somebody who is not the
            # system administrator. Either way the flag goes.
            request.session.debug = ''
        except Exception:                               # noqa: BLE001
            # A guard that cannot run must not take the request with it — but it
            # says so at WARNING with the traceback, because a rail that has
            # quietly stopped working is worse than no rail.
            _logger.warning(
                'biz_access: could not decide whether developer mode was '
                'allowed on this request', exc_info=True)


class IrQweb(models.AbstractModel):
    """The second seam: a template may never claim more than the session has.

    The sign-in page does not read `request.session.debug`. It reads a whitelist
    of QUERY-STRING parameters that `web_login` copies into its template values,
    and `debug` is one of them — so emptying the session left the page drawing
    its "Log in as superuser" button anyway, from the address bar, for somebody
    nobody had asked about.

    `_prepare_environment` is where those two meet: it is the one place every
    rendered template gets its `debug` value, and it uses `setdefault`, which is
    exactly why the controller's copy wins. Forcing it back into step with the
    session here means there is still ONE rule about who gets developer mode
    rather than two that can disagree — and it costs nothing on the overwhelming
    majority of renders, where neither is set.
    """

    _inherit = 'ir.qweb'

    def _prepare_environment(self, values):
        res = super()._prepare_environment(values)
        try:
            if values.get('debug') and not (request and request.session.debug):
                values['debug'] = ''
        except Exception:                               # noqa: BLE001
            _logger.warning(
                'biz_access: could not decide whether this page was allowed to '
                'render in developer mode', exc_info=True)
        return res
