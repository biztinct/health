# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase


class BiCase(TransactionCase):
    """Shared fixture: a 2-node dataset over res.partner joined to
    res.country, with a calculated field — exercises joins, roles,
    translation-free columns and the full publish path without depending
    on any business module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.workspace = env['bi.workspace'].create({
            'name': 'Test Workspace', 'is_default': False})

        cls.country_a = env['res.country'].search([('code', '=', 'VN')])
        cls.country_b = env['res.country'].search([('code', '=', 'AU')])
        cls.partners = env['res.partner'].create([
            {'name': 'BI Test Alpha', 'country_id': cls.country_a.id,
             'partner_latitude': 10.0},
            {'name': 'BI Test Beta', 'country_id': cls.country_a.id,
             'partner_latitude': 20.0},
            {'name': 'BI Test Gamma', 'country_id': cls.country_b.id,
             'partner_latitude': 30.0},
        ])

        cls.source_partner = env['bi.source'].create({
            'name': 'Partners', 'type': 'odoo_model',
            'model_id': env['ir.model']._get_id('res.partner')})
        cls.source_country = env['bi.source'].create({
            'name': 'Countries', 'type': 'odoo_model',
            'model_id': env['ir.model']._get_id('res.country')})

        cls.dataset = env['bi.dataset'].create({
            'name': 'Test Partners', 'workspace_id': cls.workspace.id})
        cls.node_root = env['bi.dataset.node'].create({
            'dataset_id': cls.dataset.id,
            'source_id': cls.source_partner.id, 'is_root': True})
        cls.node_country = env['bi.dataset.node'].create({
            'dataset_id': cls.dataset.id,
            'source_id': cls.source_country.id})
        env['bi.relationship'].create({
            'dataset_id': cls.dataset.id,
            'parent_node_id': cls.node_root.id,
            'child_node_id': cls.node_country.id,
            'parent_field': 'country_id', 'child_field': 'id',
            'cardinality': 'many2one', 'origin': 'manual'})

        (cls.node_root | cls.node_country).action_scan_fields()

        def field(node, technical_name):
            return cls.dataset.field_ids.filtered(
                lambda f: f.node_id == node
                and f.technical_name == technical_name)

        cls.f_name = field(cls.node_root, 'name')
        cls.f_latitude = field(cls.node_root, 'partner_latitude')
        cls.f_country_name = field(cls.node_country, 'name')
        # `res_country.name` is a TRANSLATED jsonb column, so the engine reads
        # it through `->> <caller language>` — a row rule keyed on the literal
        # "Vietnam" matches nothing for a vi_VN reader (and matches a different
        # string on any other language). `code` is a plain varchar and is the
        # same on every database: key rules on the CODE, assert on the name.
        cls.f_country_code = field(cls.node_country, 'code')
        cls.f_create_date = field(cls.node_root, 'create_date')

        # scanner may classify latitude as non-measure; force it for tests
        cls.f_latitude.write({'role': 'measure', 'default_agg': 'sum',
                              'visibility': 'visible'})
        cls.f_country_name.write({'visibility': 'visible'})

        cls.f_calc = env['bi.field'].create({
            'dataset_id': cls.dataset.id,
            'node_id': cls.node_root.id,
            'technical_name': 'calc_double_lat',
            'name': 'Double Latitude',
            'origin': 'calculated',
            'expression': '[partner_latitude] * 2',
            'data_type': 'float',
            'role': 'measure',
            'default_agg': 'sum',
        })

        cls.dataset.action_publish()
        # Relative date windows ('today', 'this_month') resolve through the
        # CALLER's timezone (`fields.Date.context_today`) while every datetime
        # column is stored in UTC — and the superuser that runs tests carries
        # **Europe/Brussels** on this deployment (ledger §5.107). Between
        # 22:00 and 24:00 UTC "today" is already tomorrow, and on the last day
        # of a month "this month" is already the next one, so a fixture row
        # created seconds earlier falls outside its own window. Pin UTC: the
        # windows then mean exactly what the fixtures' own `create_date` means,
        # at any hour of any day, on any database.
        cls.env_utc = env(context=dict(env.context, tz='UTC'))
        cls.engine = cls.env_utc['bi.query.engine']

    def _allow_all_partners(self):
        """Let this transaction read every partner.

        vietuat's live `res.partner` record rules pin a plain internal user to
        their OWN partner ("User: Own Partner Record", ir_rule 340), and the
        engine injects the root model's `ir.rule` domain into every live query
        (`_compile_root_ir_rules`). Without this, a non-admin test user sees
        none of the three fixture rows, so an RLS assertion is either an
        IndexError or vacuously true — it measures the partner ACL instead of
        the BI trust boundary it is about. The rule is created INSIDE the test
        transaction and rolls back with it; no deployment rule is touched.
        """
        self.env['ir.rule'].create({
            'name': 'BI test: read every partner',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'domain_force': "[(1, '=', 1)]",
            'groups': [(4, self.env.ref('base.group_user').id)],
            'perm_read': True, 'perm_write': False,
            'perm_create': False, 'perm_unlink': False,
        })
        # `ir.rule._get_rules` reads `ir_rule` with RAW SQL, so an unflushed
        # row is invisible to it, and `_compute_domain` is ormcache'd (§5.112).
        self.env.flush_all()
        self.env.registry.clear_cache()

    def _base_request(self, **overrides):
        request = {
            'dataset_id': self.dataset.id,
            'dimensions': [{'field_id': self.f_country_name.id}],
            'measures': [{'field_id': self.f_latitude.id, 'agg': 'sum'}],
            'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                         'value': 'BI Test'}],
            'sort': [{'ref': 'm0', 'dir': 'desc'}],
            'limit': 100,
        }
        request.update(overrides)
        return request
