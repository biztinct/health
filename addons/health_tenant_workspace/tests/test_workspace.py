import base64
from io import BytesIO
from PIL import Image
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from ..models.identity import clean_identity
from ..models.brand import debrand_text

@tagged('post_install','-at_install')
class TestTenantWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal=cls.env.ref('base.group_user')
        cls.admin=cls.env['res.users'].with_context(no_reset_password=True).create({'name':'Workspace admin','login':'workspace-test-admin','group_ids':[(6,0,[cls.internal.id,cls.env.ref('health_access.group_clinic_admin').id])]})
        cls.staff=cls.env['res.users'].with_context(no_reset_password=True).create({'name':'Workspace staff','login':'workspace-test-staff','group_ids':[(6,0,[cls.internal.id])]})
        cls.facade=cls.env['health.tenant.workspace'].with_user(cls.admin)

    def test_staff_cannot_read_or_write_profile(self):
        with self.assertRaises(AccessError):self.env['health.tenant.workspace'].with_user(self.staff).profile()
        with self.assertRaises(AccessError):self.env['health.tenant.workspace'].with_user(self.staff).history()

    def test_company_scope_ignores_forged_context(self):
        other=self.env['res.company'].create({'name':'Other clinic'})
        p=self.facade.with_context(allowed_company_ids=[other.id]).profile()
        self.assertEqual(p['company']['name'],self.admin.company_id.name)

    def test_currency_and_company_id_refused(self):
        p=self.facade.profile()
        for field in ('currency_id','company_id','parent_id','partner_id'):
            with self.assertRaises(AccessError):self.facade.save_profile({field:1},p['revision'])

    def test_save_audited_and_history_immutable(self):
        p=self.facade.profile()
        self.facade.save_profile({'name':'Workspace QA clinic'},p['revision'])
        a=self.env['health.workspace.audit'].search([],limit=1)
        self.assertEqual(a.actor_id,self.admin)
        self.assertIn('Workspace QA clinic',a.detail)
        with self.assertRaises(AccessError):a.write({'subject':'tampered'})
        with self.assertRaises(AccessError):a.unlink()

    def test_stale_write_refused(self):
        with self.assertRaises(ValidationError):self.facade.save_profile({'name':'stale'},'2000-01-01 00:00:00')

    def test_brand_round_trip_and_company_fallback(self):
        obj=self.env['ir.http']
        b=obj._apply_tenant_identity({'level':'white','product':'Carejiox','name':'','color':'#123456'})
        self.assertEqual(b['name'],self.env['res.company'].browse(1).name)
        b=obj._apply_tenant_identity({'name':'Acme Clinic'})
        self.assertEqual(b['name'],'Acme Clinic')
        self.assertEqual(debrand_text('Welcome to Carejiox','Acme Clinic','https://example.test','Carejiox'),'Welcome to Acme Clinic')
        self.assertEqual(debrand_text('Viet Uc Care','Acme Clinic','https://example.test','Carejiox'),'Acme Clinic')
        b=obj._apply_tenant_identity({'level':'powered'})
        self.assertEqual(b['powered'],'Carejiox')
        b=obj._apply_tenant_identity({'level':'product'})
        self.assertEqual(b['name'],'Carejiox')
        self.assertFalse(b['powered'])
        self.assertEqual(self.env['website'].search([],limit=1).name,'Carejiox')

    def test_uploaded_assets_survive_upgrade_and_level_change(self):
        im=Image.new('RGB',(12,12),'red');buf=BytesIO();im.save(buf,'PNG');encoded=base64.b64encode(buf.getvalue()).decode()
        obj=self.env['ir.http'];obj._apply_tenant_identity({'level':'white','product':'Carejiox','logo':encoded,'favicon':encoded})
        p=self.env['ir.config_parameter'].sudo();before=p.get_param('tenant.identity.logo')
        self.env['res.config.settings']._biz_apply_brand()
        obj._apply_tenant_identity({'level':'product'})
        self.assertEqual(p.get_param('tenant.identity.logo'),before)

    def test_invalid_identity_refused(self):
        for values in ({'level':'unknown'},{'color':'red;display:none'},{'website':'javascript:alert(1)'},{'logo':'invalid'},{'database':'hhh'}):
            with self.assertRaises(ValidationError):clean_identity(values)

    def test_setup_resumes_and_missing_checks_cannot_complete(self):
        self.facade.save_setup('facilities','Saved note')
        self.assertEqual(self.facade.setup_state()['notes'],'Saved note')
        self.admin.company_id.sudo().write({'street':False})
        with self.assertRaises(ValidationError):self.facade.save_setup('review','',True)

    def test_history_has_explicit_sources_and_no_payloads(self):
        data=self.facade.history()
        self.assertTrue(data['sources'])
        self.assertLessEqual(len(data['rows']),50)
        for r in data['rows']:
            if r['source']!='workspace':self.assertFalse(r['detail'])

from odoo.tests import HttpCase
from lxml import html

@tagged('post_install', '-at_install')
class TestTenantIdentityHTTP(HttpCase):
    def test_white_label_login_manifest_and_worker(self):
        self.env['ir.http']._apply_tenant_identity({'level':'white','product':'Carejiox','name':'Sample Practice'})
        response=self.url_open('/web/login')
        self.assertEqual(response.status_code,200)
        tree=html.fromstring(response.content)
        self.assertTrue(tree.xpath('//meta[@name="biz-brand" and @content="Sample Practice"]'))
        self.assertTrue(tree.xpath('//link[@rel="icon" and @href="/tenant/identity/favicon"]'))
        manifest=self.url_open('/health_pwa/manifest.json')
        self.assertEqual(manifest.status_code,200)
        self.assertEqual(manifest.json()['name'],'Sample Practice')
        backend=self.url_open('/web/manifest.webmanifest').json()
        self.assertEqual(backend['name'],'Sample Practice')
        self.assertEqual(backend['icons'][1]['sizes'],'512x512')
        icon=self.url_open(backend['icons'][1]['src'])
        self.assertEqual(Image.open(BytesIO(icon.content)).size,(512,512))
        self.assertEqual(self.url_open('/tenant/identity/favicon').headers['Content-Type'],'image/png')
