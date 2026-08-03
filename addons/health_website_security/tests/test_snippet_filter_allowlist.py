import json

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSnippetFilterAllowlist(TransactionCase):
    """T-003 — the model allow-list itself and the model-method block."""

    def test_allowlist_shape(self):
        allow = self.env['website.snippet.filter']._get_public_snippet_model_allowlist()
        self.assertIn('product.product', allow)
        self.assertIn('product.template', allow)
        # The models this fix exists to keep off a public sudo route.
        for blocked in ('health.clinical.note', 'health.fieldservice.order',
                        'res.users', 'res.partner', 'account.move'):
            self.assertNotIn(
                blocked, allow,
                "%s must never be resolvable through the public snippet route" % blocked)

    def test_render_blocks_non_allowlisted_model(self):
        """`_render` with a caller-supplied non-allowlisted res_model → []."""
        result = self.env['website.snippet.filter']._render(
            template_key='website.dynamic_filter_template_product_product_products_item',
            limit=1, res_model='res.users',
            res_id=self.env.ref('base.user_admin').id)
        self.assertEqual(
            result, [],
            "a caller-supplied non-allowlisted res_model must render nothing")


@tagged('post_install', '-at_install')
class TestSnippetFilterRoute(HttpCase):
    """T-003 — the exploit path end-to-end through the auth='public' route."""

    def _call(self, res_model, res_id):
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {
                'filter_id': 0,
                'template_key':
                    'website.dynamic_filter_template_product_product_products_item',
                'limit': 1, 'res_model': res_model, 'res_id': res_id,
            },
        }
        resp = self.url_open(
            '/website/snippet/filters', data=json.dumps(payload),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def test_public_route_refuses_arbitrary_model(self):
        """As a fully unauthenticated caller, res_model=res.users must yield []."""
        admin_id = self.env.ref('base.user_admin').id
        body = self._call('res.users', admin_id)
        self.assertEqual(
            body.get('result'), [],
            "public snippet route resolved a non-allowlisted model: %r" % body)

    def test_public_route_refuses_health_model_when_present(self):
        """If a clinical note exists, the public route must not resolve it."""
        note = self.env['health.clinical.note'].search([], limit=1)
        if not note:
            self.skipTest("no health.clinical.note row to probe on this database")
        body = self._call('health.clinical.note', note.id)
        self.assertEqual(
            body.get('result'), [],
            "public snippet route resolved a clinical note: %r" % body)
