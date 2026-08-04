# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scanner heuristics (harvested from bi_studio and extended)
# ---------------------------------------------------------------------------

SKIP_FIELDS = {
    'id', '__last_update', 'display_name', 'create_uid', 'write_uid',
    'write_date', 'message_ids', 'message_follower_ids',
    'message_partner_ids', 'message_channel_ids', 'activity_ids',
    'activity_state', 'activity_user_id', 'activity_type_id',
    'activity_date_deadline', 'activity_summary',
    'activity_exception_decoration', 'activity_exception_icon',
    'message_is_follower', 'message_has_error', 'message_has_sms_error',
    'message_needaction', 'message_needaction_counter',
    'message_attachment_count', 'message_has_error_counter',
    'message_main_attachment_id', 'website_message_ids',
    'rating_ids', 'rating_last_value', 'rating_last_feedback',
    'rating_last_image', 'rating_count', 'rating_avg',
    'access_url', 'access_token', 'access_warning',
}

MEASURE_TYPES = {'integer', 'float', 'monetary'}
DATE_TYPES = {'date', 'datetime'}
DIMENSION_TYPES = {'char', 'text', 'selection', 'boolean'}

GEO_HINTS = ('province', 'district', 'city', 'country', 'region', 'ward',
             'state_id', 'latitude', 'longitude')

FOLDER_RULES = [
    ('Financial', ['amount', 'total', 'price', 'cost', 'tax', 'balance',
                   'credit', 'debit', 'revenue', 'profit', 'margin',
                   'payment', 'invoice', 'residual', 'currency']),
    ('Dates', ['date', 'deadline', 'scheduled', 'planned', 'start', 'end',
               'period', 'time']),
    ('People', ['partner', 'customer', 'client', 'contact', 'vendor',
                'supplier', 'patient', 'employee', 'staff', 'user']),
    ('Products & Services', ['product', 'item', 'service', 'article',
                             'sku', 'package']),
    ('Location', ['city', 'state', 'country', 'province', 'district',
                  'address', 'zip', 'street', 'region', 'area', 'branch',
                  'facility', 'ward']),
    ('Status', ['state', 'status', 'stage', 'priority', 'category',
                'active', 'type']),
]


def _guess_folder(fname, odoo_type):
    fname_lower = fname.lower()
    if odoo_type in DATE_TYPES:
        return 'Dates'
    for folder, keywords in FOLDER_RULES:
        if any(kw in fname_lower for kw in keywords):
            return folder
    return 'General'


def _classify(fname, odoo_type):
    """(role, default_agg) for a scanned column."""
    fname_lower = fname.lower()
    if odoo_type in MEASURE_TYPES:
        # foreign-key-ish integers are identifiers, not measures
        if fname_lower.endswith('_id') or fname_lower in ('sequence', 'color'):
            return 'id', 'none'
        return 'measure', 'sum'
    if odoo_type in DATE_TYPES:
        return 'date', 'none'
    if any(hint in fname_lower for hint in GEO_HINTS):
        return 'geo', 'none'
    if odoo_type in DIMENSION_TYPES:
        return 'dimension', 'none'
    if odoo_type == 'many2one':
        return 'id', 'none'
    return 'dimension', 'none'


class BiDatasetNode(models.Model):
    """A vertex of the dataset join graph: one physical source with an
    engine-assigned alias. The root node is the fact table."""
    _name = 'bi.dataset.node'
    _description = 'BI Dataset Node'
    _order = 'dataset_id, id'

    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    source_id = fields.Many2one('bi.source', required=True,
                                ondelete='restrict')
    name = fields.Char(compute='_compute_name', store=True)
    alias = fields.Char(compute='_compute_alias',
                        help="SQL alias, derived from the id — never user text.")
    is_root = fields.Boolean(default=False)
    field_ids = fields.One2many('bi.field', 'node_id', string='Fields')
    parent_relationship_ids = fields.One2many(
        'bi.relationship', 'child_node_id', string='Joined Via')

    @api.depends('source_id.name')
    def _compute_name(self):
        for node in self:
            node.name = node.source_id.name

    def _compute_alias(self):
        for node in self:
            node.alias = 't%d' % node.id

    @api.constrains('is_root', 'dataset_id')
    def _check_single_root(self):
        for node in self.filtered('is_root'):
            others = self.search_count([
                ('dataset_id', '=', node.dataset_id.id),
                ('is_root', '=', True), ('id', '!=', node.id)])
            if others:
                raise ValidationError(
                    _("Dataset %s already has a root node.",
                      node.dataset_id.name))

    def action_scan_fields(self):
        """(Re)scan the node's source schema into bi.field rows.
        Existing curated fields are kept; new columns are appended."""
        BiField = self.env['bi.field']
        for node in self:
            existing = {f.technical_name for f in node.field_ids
                        if f.origin == 'stored'}
            values_list = []
            sequence = 100
            for col in node.source_id._fetch_schema():
                sequence += 1
                if col['name'] in SKIP_FIELDS or col['name'] in existing:
                    continue
                role, agg = _classify(col['name'], col['odoo_type'])
                data_type = col['odoo_type']
                if data_type in ('char', 'text', 'html'):
                    data_type = 'text'
                elif data_type == 'many2one':
                    data_type = 'integer'
                if data_type not in ('text', 'integer', 'float', 'monetary',
                                     'boolean', 'date', 'datetime',
                                     'selection'):
                    continue  # unmappable column type — not analyzable
                values_list.append({
                    'dataset_id': node.dataset_id.id,
                    'node_id': node.id,
                    'technical_name': col['name'],
                    'name': col['string'],
                    'origin': 'stored',
                    'data_type': data_type,
                    'role': role,
                    'default_agg': agg,
                    'folder': _guess_folder(col['name'], col['odoo_type']),
                    'sequence': sequence,
                    'visibility': 'hidden' if role == 'id' else 'visible',
                    'is_filterable': role in ('dimension', 'date', 'geo'),
                    'is_translated_column': col['translated'],
                    'selection_labels_json': col['selection'] or False,
                })
            if values_list:
                BiField.create(values_list)
        return True

    def suggest_relationships(self):
        """Auto-discover join candidates from the ORM: every many2one on an
        odoo_model node whose comodel is a concrete stored model."""
        self.ensure_one()
        if self.source_id.type != 'odoo_model':
            return []
        model = self.env[self.source_id.model_name]
        suggestions = []
        for fname, field_obj in model._fields.items():
            if (field_obj.type != 'many2one' or not field_obj.store
                    or fname in SKIP_FIELDS or not field_obj.comodel_name):
                continue
            comodel = self.env.get(field_obj.comodel_name)
            if comodel is None or comodel._abstract or not comodel._auto:
                continue
            suggestions.append({
                'parent_field': fname,
                'label': field_obj.string or fname,
                'comodel': field_obj.comodel_name,
                'cardinality': 'many2one',
            })
        return suggestions


class BiRelationship(models.Model):
    """An edge of the join graph. many2one = child is a dimension/lookup
    entity (safe); one2many = child multiplies root rows (fan-out — parent
    side measures are guarded by the engine)."""
    _name = 'bi.relationship'
    _description = 'BI Relationship'

    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    parent_node_id = fields.Many2one('bi.dataset.node', required=True,
                                     ondelete='cascade')
    child_node_id = fields.Many2one('bi.dataset.node', required=True,
                                    ondelete='cascade')
    parent_field = fields.Char(
        required=True,
        help="Join column on the parent node's table (e.g. partner_id).")
    child_field = fields.Char(required=True, default='id',
                              help="Join column on the child node's table.")
    join_type = fields.Selection([('left', 'Left Join'),
                                  ('inner', 'Inner Join')],
                                 default='left', required=True)
    cardinality = fields.Selection([('many2one', 'Many-to-One (lookup)'),
                                    ('one2many', 'One-to-Many (detail)')],
                                   default='many2one', required=True)
    origin = fields.Selection([('auto', 'Auto-discovered'),
                               ('manual', 'Manual')], default='manual')

    _sql_constraints = [
        ('child_single_parent', 'unique(child_node_id)',
         'A node can only be joined into the graph once.'),
    ]

    def write(self, vals):
        result = super().write(vals)
        if {'join_type', 'cardinality', 'parent_field', 'child_field'} \
                & set(vals):
            for dataset in self.mapped('dataset_id'):
                if dataset.state == 'published':
                    dataset._recreate_silver_view()
        return result

    @api.constrains('parent_field', 'child_field', 'parent_node_id',
                    'child_node_id')
    def _check_join_columns(self):
        for rel in self:
            if rel.parent_node_id.dataset_id != rel.child_node_id.dataset_id:
                raise ValidationError(
                    _("Relationship nodes must belong to the same dataset."))
            if rel.parent_node_id == rel.child_node_id:
                raise ValidationError(_("A node cannot join to itself."))
            parent_cols = {c['name'] for c in
                           rel.parent_node_id.source_id._fetch_schema()}
            parent_cols.add('id')
            child_cols = {c['name'] for c in
                          rel.child_node_id.source_id._fetch_schema()}
            child_cols.add('id')
            if rel.parent_field not in parent_cols:
                raise ValidationError(_(
                    "Join column %(col)s does not exist on %(node)s.",
                    col=rel.parent_field, node=rel.parent_node_id.name))
            if rel.child_field not in child_cols:
                raise ValidationError(_(
                    "Join column %(col)s does not exist on %(node)s.",
                    col=rel.child_field, node=rel.child_node_id.name))


class BiDataset(models.Model):
    """The semantic model: a join graph of sources exposing curated,
    business-named fields. Silver = compiled SQL view (live queries);
    Gold = materialized view refreshed on a schedule."""
    _name = 'bi.dataset'
    _description = 'BI Dataset'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, translate=True, tracking=True)
    description = fields.Text(translate=True)
    workspace_id = fields.Many2one(
        'bi.workspace', required=True, index=True, ondelete='restrict',
        default=lambda self: self.env['bi.workspace'].search(
            [('is_default', '=', True)], limit=1))
    active = fields.Boolean(default=True)

    node_ids = fields.One2many('bi.dataset.node', 'dataset_id', string='Nodes')
    relationship_ids = fields.One2many('bi.relationship', 'dataset_id',
                                       string='Relationships')
    field_ids = fields.One2many('bi.field', 'dataset_id', string='Fields')
    root_node_id = fields.Many2one('bi.dataset.node',
                                   compute='_compute_root_node')

    grain = fields.Selection([('root_row', 'One Row per Root Record'),
                              ('aggregated', 'Pre-aggregated')],
                             default='root_row', required=True)
    storage_mode = fields.Selection([
        ('live', 'Live (query source tables)'),
        ('gold', 'Gold (materialized view)'),
    ], default='live', required=True, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published')],
                             default='draft', tracking=True)
    is_certified = fields.Boolean(
        tracking=True, help="Blessed by a Data Modeler — shown with a badge.")

    static_filters_json = fields.Json(
        help="Baked-in filters: [{field_id, op, value}] using the engine's "
             "operator enum. Applied inside the Silver view.")
    company_field_id = fields.Many2one(
        'bi.field', string='Company Field',
        help="Field carrying company_id. Required at publish when the root "
             "model is company-dependent; the engine always injects the "
             "user's allowed companies through it.")

    refresh_job_id = fields.Many2one('bi.refresh.job', readonly=True, copy=False)
    freshness_at = fields.Datetime(compute='_compute_freshness')
    has_fanout = fields.Boolean(compute='_compute_has_fanout', store=True)

    chart_count = fields.Integer(compute='_compute_chart_count')

    @api.depends('node_ids.is_root')
    def _compute_root_node(self):
        for dataset in self:
            dataset.root_node_id = dataset.node_ids.filtered('is_root')[:1]

    @api.depends('relationship_ids.cardinality')
    def _compute_has_fanout(self):
        for dataset in self:
            dataset.has_fanout = any(
                rel.cardinality == 'one2many'
                for rel in dataset.relationship_ids)

    def _compute_freshness(self):
        for dataset in self:
            if dataset.storage_mode == 'gold' and dataset.refresh_job_id:
                dataset.freshness_at = dataset.refresh_job_id.last_refresh
            else:
                dataset.freshness_at = fields.Datetime.now()

    def _compute_chart_count(self):
        counts = dict(self.env['bi.chart']._read_group(
            [('dataset_id', 'in', self.ids)], ['dataset_id'], ['__count']))
        for dataset in self:
            dataset.chart_count = counts.get(dataset, 0)

    # ------------------------------------------------------------------
    # Graph helpers
    # ------------------------------------------------------------------

    def _ordered_nodes(self):
        """Root-first BFS order; raises on orphan nodes (unreachable from
        root through relationships)."""
        self.ensure_one()
        root = self.root_node_id
        if not root:
            raise UserError(_("Dataset %s has no root node.", self.name))
        rels_by_parent = {}
        for rel in self.relationship_ids:
            rels_by_parent.setdefault(rel.parent_node_id.id, []).append(rel)
        ordered, edges = [root], []
        queue = [root]
        while queue:
            node = queue.pop(0)
            for rel in rels_by_parent.get(node.id, []):
                ordered.append(rel.child_node_id)
                edges.append(rel)
                queue.append(rel.child_node_id)
        orphans = self.node_ids - self.env['bi.dataset.node'].union(*ordered) \
            if ordered else self.node_ids
        if orphans:
            raise UserError(_(
                "Nodes not connected to the root: %s. Add relationships or "
                "remove them.", ', '.join(orphans.mapped('name'))))
        return ordered, edges

    def _fanout_unsafe_node_ids(self):
        """Nodes whose measures would double-count when any one2many edge is
        traversed: the root-side ancestors of every one2many relationship."""
        self.ensure_one()
        unsafe = set()
        for rel in self.relationship_ids.filtered(
                lambda r: r.cardinality == 'one2many'):
            node = rel.parent_node_id
            while node:
                unsafe.add(node.id)
                parent_rel = node.parent_relationship_ids[:1]
                node = parent_rel.parent_node_id if parent_rel else None
        return unsafe

    # ------------------------------------------------------------------
    # Silver SQL compilation
    # ------------------------------------------------------------------

    def _silver_view_name(self):
        self.ensure_one()
        return 'bi_silver_%d' % self.id

    def _gold_matview_name(self):
        self.ensure_one()
        return 'bi_gold_%d' % self.id

    def _compile_silver_sql(self):
        """The dataset's semantic SELECT: all stored fields as f_<id> columns
        plus _bi_row_key, with the full join tree. Calculated fields are NOT
        materialized here (they may be aggregate-context); the engine compiles
        them at query time. Translated jsonb columns pass through raw — the
        engine extracts the user language."""
        self.ensure_one()
        ordered, edges = self._ordered_nodes()
        root = ordered[0]

        select_parts = [SQL(
            "%s.id AS _bi_row_key",
            SQL.identifier(root.alias))]
        for field in self.field_ids:
            if field.origin != 'stored':
                continue
            select_parts.append(SQL(
                "%s.%s AS %s",
                SQL.identifier(field.node_id.alias),
                SQL.identifier(field.technical_name),
                SQL.identifier('f_%d' % field.id)))

        from_sql = SQL("%s AS %s",
                       SQL.identifier(root.source_id._table_name()),
                       SQL.identifier(root.alias))
        for rel in edges:
            join_kw = SQL("LEFT JOIN") if rel.join_type == 'left' \
                else SQL("JOIN")
            from_sql = SQL(
                "%s %s %s AS %s ON %s.%s = %s.%s",
                from_sql, join_kw,
                SQL.identifier(rel.child_node_id.source_id._table_name()),
                SQL.identifier(rel.child_node_id.alias),
                SQL.identifier(rel.parent_node_id.alias),
                SQL.identifier(rel.parent_field),
                SQL.identifier(rel.child_node_id.alias),
                SQL.identifier(rel.child_field))

        where_sql = self._compile_static_filters()

        # Record-lifecycle rule: soft-deleted rows (health.lifecycle.mixin
        # `deleted` flag) never enter BI datasets, while archived rows stay —
        # BI deliberately runs active_test=False (see bi_query_engine). The
        # predicate is applied on the ROOT table only and baked into the
        # silver view, so gold materializations inherit it automatically.
        root_model = root.source_id.model_name
        if root_model and root_model in self.env:
            deleted_field = self.env[root_model]._fields.get('deleted')
            if deleted_field is not None and deleted_field.store \
                    and deleted_field.type == 'boolean':
                lifecycle_sql = SQL(
                    "COALESCE(%s.deleted, FALSE) = FALSE",
                    SQL.identifier(root.alias))
                where_sql = SQL("%s AND %s", where_sql, lifecycle_sql) \
                    if where_sql else lifecycle_sql

        query = SQL("SELECT %s FROM %s",
                    SQL(", ").join(select_parts), from_sql)
        if where_sql:
            query = SQL("%s WHERE %s", query, where_sql)
        return query

    def _compile_static_filters(self):
        """Baked-in dataset filters — same operator enum as the engine."""
        self.ensure_one()
        filters = self.static_filters_json or []
        if not filters:
            return None
        # local import to avoid a cycle at module load
        engine = self.env['bi.query.engine']
        parts = []
        for spec in filters:
            field = self.env['bi.field'].browse(spec.get('field_id'))
            if not field.exists() or field.dataset_id != self:
                raise UserError(_("Static filter references an unknown field."))
            column = SQL("%s.%s",
                         SQL.identifier(field.node_id.alias),
                         SQL.identifier(field.technical_name))
            parts.append(engine._compile_filter_op(
                column, spec.get('op'), spec.get('value'), field))
        return SQL(" AND ").join(parts)

    def _recreate_silver_view(self):
        for dataset in self:
            if not dataset.root_node_id or not dataset.field_ids:
                continue
            view_name = dataset._silver_view_name()
            tools.drop_view_if_exists(self.env.cr, view_name)
            self.env.cr.execute(SQL(
                "CREATE VIEW %s AS (%s)",
                SQL.identifier(view_name),
                dataset._compile_silver_sql()))
            _logger.info("biz_bi: (re)created silver view %s", view_name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def action_publish(self):
        for dataset in self:
            if not dataset.root_node_id:
                raise UserError(_("Add a root node before publishing."))
            visible = dataset.field_ids.filtered(
                lambda f: f.visibility == 'visible')
            if not visible:
                raise UserError(_("No visible fields — nothing to publish."))
            dataset._check_company_gate()
            dataset._recreate_silver_view()
            if dataset.storage_mode == 'gold':
                dataset._publish_gold()
            dataset.state = 'published'
            self.env['bi.audit.log'].sudo().log(
                'dataset_publish', dataset=dataset)
        return True

    def action_open_modeler(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'biz_bi.modeler',
            'name': self.name,
            'params': {'dataset_id': self.id},
        }

    def action_unpublish(self):
        for dataset in self:
            dataset.state = 'draft'
            self.env['bi.audit.log'].sudo().log(
                'dataset_unpublish', dataset=dataset)
        return True

    def _check_company_gate(self):
        """Multi-company safety: when the root model has company_id, the
        dataset must declare which field carries it."""
        self.ensure_one()
        root_source = self.root_node_id.source_id
        if root_source.type != 'odoo_model':
            return
        model = self.env[root_source.model_name]
        if 'company_id' in model._fields and model._fields['company_id'].store:
            if not self.company_field_id:
                company_field = self.field_ids.filtered(
                    lambda f: f.node_id == self.root_node_id
                    and f.technical_name == 'company_id')
                if company_field:
                    self.company_field_id = company_field[0]
                else:
                    raise UserError(_(
                        "The root model %s is company-dependent: select the "
                        "Company Field before publishing (multi-company "
                        "safety gate).", root_source.model_name))

    def _publish_gold(self):
        self.ensure_one()
        if self.grain != 'root_row':
            raise UserError(_(
                "Pre-aggregated gold datasets are not supported yet."))
        self.env['bi.refresh.job']._publish_gold_for(self)

    def write(self, vals):
        result = super().write(vals)
        structural = {'node_ids', 'relationship_ids', 'field_ids',
                      'static_filters_json'}
        if structural & set(vals) and not self.env.context.get(
                'bi_skip_silver_rebuild'):
            published = self.filtered(lambda d: d.state == 'published')
            published._recreate_silver_view()
        return result

    def unlink(self):
        for dataset in self:
            tools.drop_view_if_exists(
                self.env.cr, dataset._silver_view_name())
            self.env.cr.execute(SQL(
                "DROP MATERIALIZED VIEW IF EXISTS %s CASCADE",
                SQL.identifier(dataset._gold_matview_name())))
        return super().unlink()

    # ------------------------------------------------------------------
    # Frontend metadata
    # ------------------------------------------------------------------

    def get_builder_metadata(self):
        """Everything the Explore builder needs about this dataset, in the
        user's language, with masked fields removed."""
        self.ensure_one()
        masked = self.env['bi.access.rule']._masked_field_ids(self)
        fields_payload = []
        for field in self.field_ids:
            if field.visibility != 'visible' or field.id in masked:
                continue
            fields_payload.append({
                'id': field.id,
                'name': field.name,
                'description': field.description or '',
                'data_type': field.data_type,
                'role': field.role,
                'default_agg': field.default_agg,
                'folder': field.folder or 'General',
                'node': field.node_id.name,
                'format': field.format_json or {},
                'selection_labels': field._selection_labels_for(),
                'glossary': field.glossary_term_id.definition or '',
            })
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'storage_mode': self.storage_mode,
            'is_certified': self.is_certified,
            'freshness_at': self.freshness_at,
            'fields': fields_payload,
        }

    def get_modeler_data(self):
        """Everything the visual Semantic Modeler needs: nodes with field
        stats, edges with join details, and per-node join suggestions."""
        self.ensure_one()
        nodes = []
        for node in self.node_ids:
            roles = {}
            for field in node.field_ids:
                if field.visibility == 'visible':
                    roles[field.role] = roles.get(field.role, 0) + 1
            existing_joins = {
                rel.parent_field for rel in self.relationship_ids
                if rel.parent_node_id == node}
            nodes.append({
                'id': node.id,
                'name': node.name,
                'alias': node.alias,
                'is_root': node.is_root,
                'table': node.source_id._table_name(),
                'source_type': node.source_id.type,
                'field_total': len(node.field_ids),
                'roles': roles,
                'suggestions': [
                    s for s in node.suggest_relationships()
                    if s['parent_field'] not in existing_joins],
            })
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'storage_mode': self.storage_mode,
            'is_certified': self.is_certified,
            'has_fanout': self.has_fanout,
            'nodes': nodes,
            'relationships': [{
                'id': rel.id,
                'parent_node_id': rel.parent_node_id.id,
                'child_node_id': rel.child_node_id.id,
                'parent_field': rel.parent_field,
                'child_field': rel.child_field,
                'join_type': rel.join_type,
                'cardinality': rel.cardinality,
                'origin': rel.origin,
            } for rel in self.relationship_ids],
        }

    def add_suggested_relationship(self, parent_node_id, parent_field,
                                   comodel, label):
        """Modeler one-click join: create (or reuse) the comodel source,
        add the child node + relationship, scan and prefix its fields."""
        self.ensure_one()
        parent_node = self.env['bi.dataset.node'].browse(int(parent_node_id))
        if parent_node.dataset_id != self:
            raise UserError(_("Node does not belong to this dataset."))
        Source = self.env['bi.source']
        ir_model = self.env['ir.model']._get(comodel)
        source = Source.search([('model_id', '=', ir_model.id)], limit=1)
        if not source:
            source = Source.create({
                'name': ir_model.name, 'type': 'odoo_model',
                'model_id': ir_model.id, 'state': 'ready'})
        child = self.env['bi.dataset.node'].create({
            'dataset_id': self.id, 'source_id': source.id})
        self.env['bi.relationship'].create({
            'dataset_id': self.id,
            'parent_node_id': parent_node.id,
            'child_node_id': child.id,
            'parent_field': parent_field,
            'child_field': 'id',
            'cardinality': 'many2one',
            'origin': 'manual',
        })
        child.action_scan_fields()
        for field in child.field_ids:
            if field.technical_name == 'name':
                field.write({'name': label, 'folder': label,
                             'visibility': 'visible', 'sequence': 1})
            else:
                field.visibility = 'hidden'
        if self.state == 'published':
            self._recreate_silver_view()
        return child.id

    def get_dataset_card(self):
        """LLM-ready dataset card: business names EN/VI, types, roles,
        relationships. Sensitive fields are excluded entirely; only
        low-cardinality dimension samples are included (no raw rows)."""
        self.ensure_one()
        installed_langs = {code for code, _name
                           in self.env['res.lang'].get_installed()}
        card_fields = []
        for field in self.field_ids:
            if field.visibility != 'visible':
                continue
            name_en = field.with_context(lang='en_US').name
            card_fields.append({
                'ref': field.id,
                'name_en': name_en,
                'name_vi': (field.with_context(lang='vi_VN').name
                            if 'vi_VN' in installed_langs else name_en),
                'type': field.data_type,
                'role': field.role,
                'default_agg': field.default_agg,
                'folder': field.folder or 'General',
                'description': field.description or '',
                'selection_values': list(
                    field._selection_labels_for('en_US').keys()) or None,
            })
        relationships = [
            '%s -> %s via %s (%s)' % (
                rel.parent_node_id.name, rel.child_node_id.name,
                rel.parent_field, rel.cardinality)
            for rel in self.relationship_ids]
        self.env.cr.execute(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = %s",
            (self.root_node_id.source_id._table_name(),))
        row = self.env.cr.fetchone()
        return {
            'dataset': self.name,
            'description': self.description or '',
            'grain': self.grain,
            'fields': card_fields,
            'relationships': relationships,
            'row_count_estimate': row and int(row[0]) or 0,
        }
