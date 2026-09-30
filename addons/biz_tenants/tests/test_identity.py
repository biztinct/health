from contextlib import contextmanager
from unittest.mock import patch
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestCustomerIdentity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service=self.env['biz.tenants']
        self.tenant=self.env['biz.tenant'].create({'name':'Brand test','slug':'brand-test','state':'live'})
        self.staff=self.env['res.users'].with_context(no_reset_password=True).create({'name':'Brand staff','login':'brand-staff','group_ids':[(6,0,[self.env.ref('base.group_user').id])]})

    def test_identity_and_domain_rpcs_are_platform_only(self):
        s=self.service.with_user(self.staff)
        for method,args in [('identity_options',[]),('tenant_brand',[self.tenant.id]),('tenant_set_brand',[self.tenant.id,{}]),('tenant_push_brand',[self.tenant.id]),('domain_add',[self.tenant.id,'care.example.com']),('domain_check',[0]),('domain_activate',[0]),('domain_remove',[0])]:
            with self.assertRaises(AccessError,msg=method):getattr(s,method)(*args)

    def test_country_currency_and_style_validation(self):
        for values in ({'country_id':99999999},{'currency_id':99999999},{'brand_level':'invalid'},{'brand_color':'red;display:none'}):
            with self.assertRaises(ValidationError):self.service._identity_form(values)

    def test_existing_tenant_currency_cannot_be_changed_from_brand_screen(self):
        with self.assertRaises(UserError):self.service.tenant_set_brand(self.tenant.id,{'currency_id':1})

    def test_hostname_guards_and_duplicate_ownership(self):
        with patch.object(type(self.service),'tenant_brand',return_value={}):
            for host in ['https://care.example.com','../../etc','bad;host.com',self.service._apex(),self.service._tenant_host(self.tenant.slug)]:
                with self.assertRaises(UserError):self.service.domain_add(self.tenant.id,host)
            self.service.domain_add(self.tenant.id,'CARE.EXAMPLE.COM')
            with self.assertRaises(UserError):self.service.domain_add(self.tenant.id,'care.example.com')

    def test_brand_push_and_drift(self):
        if not hasattr(self.env['ir.http'],'_apply_tenant_identity'):
            self.skipTest('Product identity provider not installed')
        @contextmanager
        def target(*args):yield self.env
        with patch.object(type(self.service),'_tenant_env',target):
            result=self.service.tenant_set_brand(self.tenant.id,{'brand_level':'white','brand_name':'Sample Practice'})
            self.assertTrue(result['in_step'])
            self.assertEqual(result['live']['name'],'Sample Practice')
            self.env['ir.config_parameter'].sudo().set_param('tenant.identity.name','Changed elsewhere')
            self.assertIn('name',self.service.tenant_brand(self.tenant.id)['differences'])
            self.assertTrue(self.service.tenant_push_brand(self.tenant.id)['in_step'])

    def test_locale_is_applied_to_new_company(self):
        from odoo.addons.biz_tenants.models.service import BizTenants
        country=self.env.ref('base.au')
        currency=self.env.ref('base.AUD')
        self.tenant.write({'country_id':country.id,'currency_id':currency.id})
        @contextmanager
        def target(*args):yield self.env
        with patch.object(BizTenants,'_step_configure',return_value={}), patch.object(type(self.service),'_tenant_env',target), patch.object(type(self.env['account.move']),'search_count',return_value=0):
            self.service._step_configure(self.tenant,lambda *a:None,False)
        company=self.env['res.company'].browse(1)
        self.assertEqual(company.country_id,country)
        self.assertEqual(company.currency_id,currency)

    def test_accounting_entries_prevent_currency_change(self):
        from odoo.addons.biz_tenants.models.service import BizTenants
        currency=self.env['res.currency'].with_context(active_test=False).search([('id','!=',self.env.company.currency_id.id)],limit=1)
        self.tenant.currency_id=currency
        @contextmanager
        def target(*args):yield self.env
        with patch.object(BizTenants,'_step_configure',return_value={}), patch.object(type(self.service),'_tenant_env',target), patch.object(type(self.env['account.move']),'search_count',return_value=1):
            with self.assertRaises(UserError):self.service._step_configure(self.tenant,lambda *a:None,False)

    def test_provisioning_overrides_keep_model_rpc_contract(self):
        from odoo.addons.biz_tenants.models.service import BizTenants
        from odoo.service.model import call_kw
        with patch.object(BizTenants,'provision_preview',new=lambda self, form: {'plan':[{}, {'what':'Configure.'}]}):
            result=call_kw(self.service,'provision_preview',[{'name':'New company','brand_level':'white'}],{})
            self.assertIn('New company',result['plan'][1]['what'])
        self.assertTrue(self.service.provision_start._api_model)
