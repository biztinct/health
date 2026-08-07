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
            'recents': self.env['bi.audit.log'].get_recents(),
            'is_creator': home['is_creator'],
            'is_modeler': home['is_modeler'],
            'is_admin': home['is_admin'],
            'ai_available': self._hub_ai_available(),
        }

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
