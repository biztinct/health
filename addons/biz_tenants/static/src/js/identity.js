/** @odoo-module **/
import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';
import { _t } from '@web/core/l10n/translation';
import { BizTenants } from './tenants';

patch(BizTenants.prototype, {
    setup() {super.setup();this.identityOptions=useState({countries:[],currencies:[]});onWillStart(async()=>{Object.assign(this.identityOptions,await this.orm.call('biz.tenants','identity_options',[]));});},
    openWizard(){super.openWizard();Object.assign(this.state.form,{brand_level:'product',brand_name:'',brand_color:'#1565C0',country_id:'',currency_id:''});},
    openIdentity(){this.action.doAction({type:'ir.actions.client',tag:'biz_tenant_identity',name:_t('Brand and addresses'),context:{active_id:this.state.tenant.id},params:{tenant_id:this.state.tenant.id}});},
});

class TenantIdentity extends Component {
    static template='biz_tenants.Identity';static props=['*'];
    setup(){this.orm=useService('orm');this.action=useService('action');this.state=useState({data:null,form:{},busy:false,error:'',hostname:'',message:''});onWillStart(()=>this.load());}
    get id(){return this.props.action.params?.tenant_id || this.props.action.context?.active_id || this.props.action.params?.active_id;}
    async run(method,args){this.state.busy=true;this.state.error='';this.state.message='';try{const data=await this.orm.call('biz.tenants',method,args);this.state.data=data;this.state.form={...data.values};return true;}catch(e){this.state.error=e.data?.message||e.message;}finally{this.state.busy=false;}}
    load(){if(!this.id){this.state.error=_t('Choose an existing customer.');return;}return this.run('tenant_brand',[this.id]);}
    async save(){if(await this.run('tenant_set_brand',[this.id,this.state.form]))this.state.message=_t('Branding saved and applied. Refresh the customer’s browser to see the change.');}
    retry(){return this.run('tenant_push_brand',[this.id]);}
    async upload(key,ev){const f=ev.target.files[0];if(!f)return;if(f.size>2097152){this.state.error=_t('Choose an image smaller than 2 MB.');return;}const r=new FileReader();r.onload=()=>{this.state.form[key]=String(r.result).split(',')[1];};r.readAsDataURL(f);}
    addDomain(){return this.run('domain_add',[this.id,this.state.hostname]);}
    domain(method,id){return this.run(method,[id]);}
    back(){this.action.doAction('biz_tenants.action_biz_tenants');}
}
registry.category('actions').add('biz_tenant_identity',TenantIdentity);
