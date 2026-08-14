# -*- coding: utf-8 -*-
from odoo.tests import new_test_user, tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestRelationLabels(BiCase):
    """A many2one dimension must GROUP by id but READ as the record's name.
    Before this, 'Catchment Area' rendered as 1 / 2."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # country_id is a many2one column on the root node — the scanner
        # classifies it as geo (GEO_HINTS), i.e. offered as a dimension.
        cls.f_country_id = cls.dataset.field_ids.filtered(
            lambda f: f.technical_name == 'country_id'
            and f.node_id == cls.node_root)
        cls.f_country_id.visibility = 'visible'

    def _country_dim_request(self):
        return self._base_request(
            dimensions=[{'field_id': self.f_country_id.id}])

    def test_scan_records_the_lookup_model(self):
        self.assertEqual(self.f_country_id.relation_model, 'res.country')

    def test_backfill_is_idempotent_and_finds_stale_columns(self):
        """Columns scanned before relation_model existed get filled by the
        end-migration helper, and re-running changes nothing."""
        self.f_country_id.relation_model = False
        self.assertTrue(self.env['bi.field']._backfill_relation_models())
        self.assertEqual(self.f_country_id.relation_model, 'res.country')
        # a text column must never acquire a lookup model
        self.assertFalse(self.f_name.relation_model)
        self.assertEqual(self.env['bi.field']._backfill_relation_models(), 0)

    def test_ids_are_labelled_with_record_names(self):
        result = self.engine.run(self._country_dim_request())
        column = result['columns'][0]
        labels = column.get('value_labels') or {}
        self.assertEqual(labels.get(str(self.country_a.id)),
                         self.country_a.display_name)
        self.assertEqual(labels.get(str(self.country_b.id)),
                         self.country_b.display_name)

    def test_grouping_still_happens_on_the_id(self):
        # two countries renamed identically must remain two rows — labels
        # are presentation, never grouping
        result = self.engine.run(self._country_dim_request())
        ids = sorted(row[0] for row in result['rows'])
        self.assertEqual(ids, sorted([self.country_a.id, self.country_b.id]))
        self.assertEqual(len(result['rows']), 2)

    def test_labels_are_not_served_from_another_users_cache(self):
        """The cache is shared across users with the same RLS fingerprint,
        so labels must be resolved per reader, not stored in the envelope."""
        request = self._country_dim_request()
        self.engine.run(request)                      # warms the cache
        cached = self.engine.run(request)
        self.assertEqual(cached['meta']['cache'], 'hit')
        self.assertTrue(cached['columns'][0].get('value_labels'),
                        "a cache hit must still carry resolved labels")

        raw = self.env['bi.query.cache'].sudo().search(
            [('dataset_id', '=', self.dataset.id)], limit=1)
        stored_columns = raw.result_json['columns']  # also proves the ORM
        # can read this model at all (fetch() used to shadow BaseModel.fetch)
        self.assertNotIn('value_labels', stored_columns[0],
                         "labels must never be written to the shared cache")

    def _synthetic_envelope(self):
        return {
            'columns': [{'ref': 'd0', 'field_id': self.f_country_id.id},
                        {'ref': 'm0', 'field_id': self.f_latitude.id}],
            'rows': [[self.country_a.id, 30.0], [self.country_b.id, 30.0]],
        }

    def test_every_id_present_is_labelled_not_just_the_first_2000(self):
        """A wide relation column used to fall off a cliff.

        `MAX_LABEL_LOOKUP = 2000` SKIPPED the whole lookup once a result held
        more distinct ids than that, so a big Records export of a many2one
        column silently reverted to raw ids — the one remaining path by which
        an id reached a user (RT-1 report §9). Every id present is resolved
        now, in chunks, and the row caps the engine already applies are what
        bound the work.
        """
        Partner = self.env['res.partner'].with_context(
            tracking_disable=True, no_reset_password=True,
            mail_create_nosubscribe=True, mail_create_nolog=True)
        many = Partner.create([
            {'name': 'BI Label Probe %04d' % index} for index in range(2500)])
        self.assertEqual(len(many), 2500)

        # the lookup is keyed on the COLUMN's relation_model, so any column
        # pointing at res.partner exercises it; borrow the country column's
        # slot rather than depend on which m2o the scanner classified.
        self.f_country_id.relation_model = 'res.partner'
        envelope = {
            'columns': [{'ref': 'd0', 'field_id': self.f_country_id.id},
                        {'ref': 'm0', 'field_id': self.f_latitude.id}],
            'rows': [[partner.id, 1.0] for partner in many],
        }

        cursor = self.env.cr
        original = cursor.execute
        counter = {'n': 0}

        def counting(*args, **kwargs):
            counter['n'] += 1
            return original(*args, **kwargs)

        cursor.execute = counting
        try:
            result = self.engine._attach_relation_labels(envelope)
        finally:
            cursor.execute = original

        labels = result['columns'][0].get('value_labels') or {}
        self.assertEqual(len(labels), 2500,
                         "every id present in the rows must be labelled")
        for partner in many[:5] + many[-5:]:
            self.assertEqual(labels[str(partner.id)], partner.display_name)

        # 2500 ids, 3 chunks: a per-id query would be ~2500 statements. The
        # bound is deliberately loose — this asserts the SHAPE of the work,
        # not a query budget that a prefetch change would flip red.
        self.assertLess(counter['n'], 60,
                        "labels must resolve in chunks, never one query per "
                        "id (%s statements)" % counter['n'])

    def test_unreadable_lookup_records_fall_back_to_ids(self):
        """A reader the comodel's record rules hide sees the raw id, not
        someone else's record name — and nothing raises.

        Driven through _attach_relation_labels rather than a full query:
        this database carries bi.access.rule rows that already filter every
        row away for a fresh non-admin user, which would mask the assertion.
        """
        user = new_test_user(self.env, login='bi_no_country',
                             groups='base.group_user,biz_bi.group_bi_viewer')
        self.env['ir.rule'].create({
            'name': 'BI test: hide all countries',
            'model_id': self.env['ir.model']._get_id('res.country'),
            'domain_force': "[(0, '=', 1)]",
            'groups': [(4, self.env.ref('base.group_user').id)],
            'perm_read': True,
        })
        self.env.registry.clear_cache()

        result = self.engine.with_user(user)._attach_relation_labels(
            self._synthetic_envelope())
        self.assertFalse(result['columns'][0].get('value_labels'),
                         "no readable record → no borrowed names")
        # and the admin, who may read them, still gets labels
        admin_result = self.engine._attach_relation_labels(
            self._synthetic_envelope())
        self.assertEqual(
            admin_result['columns'][0]['value_labels'][str(self.country_a.id)],
            self.country_a.display_name)
