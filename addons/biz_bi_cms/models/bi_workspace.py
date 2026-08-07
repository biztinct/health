# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError


class BiWorkspace(models.Model):
    """One RPC for the whole Analytics Hub landing.

    The old Home awaited three RPCs in sequence (workspaces, recents, then a
    dashboard list) and the third was
    ``searchRead('bi.dashboard', [], limit=40)`` — unscoped and capped, so on
    a database with more than forty visible dashboards the workspaces that
    sorted last showed "No dashboards yet" while holding plenty. Here the
    dashboards are fetched ONCE, keyed by workspace, with no limit, and the
    whole landing arrives in a single round trip.

    Everything is read as the CURRENT user: the workspace / dataset /
    dashboard record rules are the access boundary and there is no ``sudo()``
    anywhere in this module.
    """
    _inherit = 'bi.workspace'

    @api.model
    def get_hub_data(self):
        home = self.get_home_data()
        workspaces = home['workspaces']
        workspace_ids = [ws['id'] for ws in workspaces]

        by_workspace = {ws_id: [] for ws_id in workspace_ids}
        if workspace_ids:
            rows = self.env['bi.dashboard'].search_read(
                [('workspace_id', 'in', workspace_ids)],
                ['name', 'description', 'workspace_id'],
                order='name',
            )
            for row in rows:
                bucket = by_workspace.get(row['workspace_id'][0])
                # A dashboard the user owns inside a workspace they cannot see
                # is filtered out by the domain above; the guard costs nothing
                # and keeps a future rule change from raising a KeyError.
                if bucket is None:
                    continue
                bucket.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'] or '',
                })

        for workspace in workspaces:
            workspace['dashboards'] = by_workspace.get(workspace['id'], [])

        return {
            'workspaces': workspaces,
            'recents': self._hub_recents(),
            'is_creator': home['is_creator'],
            'is_modeler': home['is_modeler'],
            'is_admin': home['is_admin'],
            'ai_available': self._hub_ai_available(),
        }

    def _hub_recents(self):
        """"Continue where you left off", with the dead entries removed.

        ``bi.audit.log`` is append-only: a `dashboard_view` row survives the
        dashboard it refers to, and it survives that dashboard being moved into
        a workspace the user can no longer see. A recents strip is the one place
        on the landing where a stale id turns into a chip that 404s (or, worse,
        a name the user is no longer entitled to read), so the ids are re-read
        through the ORM as the CURRENT user and anything that does not come
        back is dropped rather than shown.

        ``get_recents`` (``bi_audit_log.py:57-72``) already re-searches the ids
        it collected, which makes the prune below a no-op on today's biz_bi —
        that is the point: the hub states the guarantee at its own boundary
        instead of inheriting it from a helper it does not own, and the test
        pins it here.

        The ``AccessError`` guard is NOT belt and braces; it was earned. That
        same helper finishes with ``d.workspace_id.name``, and a dashboard can
        be readable while its workspace is not — the dashboard rule grants
        ``owner_id = user`` on its own, the workspace rule has no such clause.
        Measured live on vietuat while staging the first-run card: scoping the
        workspaces to a group turned the user's OWN recent dashboard into an
        AccessError on the workspace read, and the whole landing went to the
        "no analytics access" state over one stale chip. §5.47's rule applied
        to a landing page: catch AccessError ONLY, drop the compartment that
        refused, and keep the page.
        """
        try:
            recents = self.env['bi.audit.log'].get_recents() or []
        except AccessError:
            return []
        ids = [row['id'] for row in recents if row.get('id')]
        if not ids:
            return []
        alive = set(self.env['bi.dashboard'].search([('id', 'in', ids)]).ids)
        return [row for row in recents if row['id'] in alive]

    def _hub_ai_available(self):
        """Whether the AI report composer can run — Phase 2 needs this.

        ``bi.ai.is_available()`` searches ``bi.ai.provider``, whose ACL starts
        at ``group_bi_modeler``: a plain creator raises AccessError on the
        read. That must not take the whole landing down, so the refusal is
        caught and reported as "no AI" — the §5.47 pattern (catch AccessError
        ONLY, never a blanket Exception, and degrade rather than fail).

        ``models/bi_ai.py`` now guards the probe itself, so this is belt and
        braces — deliberately kept, because it documents the hazard where the
        call is made and it survives the override being changed.
        """
        try:
            return bool(self.env['bi.ai'].is_available())
        except AccessError:
            return False
