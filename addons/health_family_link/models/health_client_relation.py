from odoo import fields, models


class HealthClientRelation(models.Model):
    """A2 cond 1 — per-relation opt-in for family visit updates.

    Default False: installing this module changes no behavior until a human
    opts a specific relation in. This is NOT the consent authority (the
    shipped health.consent engine is — see the module description / A2); it is
    a simple channel preference on the kinship relation.
    """
    _inherit = 'health.client.relation'

    receives_visit_updates = fields.Boolean(
        string='Receives Visit Updates',
        default=False,
        help='Opt this relation in to the tokenized family visit page + '
             'Zalo visit/snapshot notifications. Off by default. Medical '
             'snapshot content additionally requires '
             '"Can Receive Medical Information" and the client\'s '
             'data-sharing consent.',
    )
