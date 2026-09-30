/** @odoo-module **/
import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { _t } from '@web/core/l10n/translation';

export class TenantWorkspace extends Component {
    static template = 'health_tenant_workspace.Workspace';
    static props = ['*'];
    setup() {
        this.orm = useService('orm'); this.action = useService('action'); this.notification = useService('notification');
        this.state = useState({profile:null, setup:null, history:null, busy:false, error:'', query:'', source:'all', offset:0});
        this.mode = (this.props.action.tag || '').split('_').pop();
        this.labels = {name:_t('Company name'),street:_t('Street'),street2:_t('Address line 2'),city:_t('City'),zip:_t('Postal code'),phone:_t('Phone'),email:_t('Email'),website:_t('Website'),vat:_t('Tax number'),company_registry:_t('Registration number')};
        this.steps = ['company','facilities','people','services','connections','review'];
        this.stepLabels = {company:_t('Company'),facilities:_t('Facilities'),people:_t('People'),services:_t('Services'),connections:_t('Connections'),review:_t('Review')};
        this.stepHelp = {company:_t('Save your company name, address and country below.'),facilities:_t('Add the clinics and locations where your team works.'),people:_t('Create staff accounts and assign their access using the guided account screen.'),services:_t('Add the services you offer and review their prices.'),connections:_t('Connect the communication channels you need. You can do this later.'),review:_t('Review the checks below and finish when the required items are ready.')};
        onWillStart(() => this.load());
    }
    get fieldKeys(){return Object.keys(this.labels);}
    get visibleChecks(){return this.state.setup.checks.filter(c=>this.state.setup.step==='review'||c.key===this.state.setup.step);}
    get setupIndex(){return this.steps.indexOf(this.state.setup.step);}
    readyLabel(ready){return ready?_t('Ready'):_t('Needs attention');}
    get title() {return this.mode === 'company' ? _t('Your company') : this.mode === 'setup' ? _t('Clinic setup') : _t('Activity history');}
    async run(fn) {
        this.state.busy=true;this.state.error='';
        try { return await fn(); } catch(e) {this.state.error=e.data?.message || e.message || _t('Please try again.');}
        finally {this.state.busy=false;}
    }
    async load() {await this.run(async()=>{
        if(this.mode==='history'){await this.loadHistory();return;}
        this.state.profile=await this.orm.call('health.tenant.workspace','profile',[]);
        if(this.mode==='setup') this.state.setup=await this.orm.call('health.tenant.workspace','setup_state',[]);
    });}
    async saveCompany() {await this.run(async()=>{
        const p=this.state.profile;
        p.company.country_id=Number(p.country_id);
        this.state.profile=await this.orm.call('health.tenant.workspace','save_profile',[p.company,p.revision]);
        this.notification.add(_t('Company details saved.'),{type:'success'});
        if(this.mode==='setup')this.state.setup=await this.orm.call('health.tenant.workspace','setup_state',[]);
    });}
    async upload(ev){const file=ev.target.files[0];if(!file)return;
        if(file.size>2097152){this.state.error=_t('Choose an image smaller than 2 MB.');return;}
        const reader=new FileReader();reader.onload=()=>{this.state.profile.company.logo=String(reader.result).split(',')[1];this.state.profile.logo=reader.result;};reader.readAsDataURL(file);
    }
    async step(key,complete=false){await this.run(async()=>{this.state.setup=await this.orm.call('health.tenant.workspace','save_setup',[key,this.state.setup.notes,complete]);});}
    async openCheck(check){if(check.key==='company'){await this.step('company');return;}if(check.action)await this.action.doAction(check.action);}
    async loadHistory(){this.state.history=await this.orm.call('health.tenant.workspace','history',[this.state.source,this.state.query,this.state.offset]);}
    async search(){this.state.offset=0;await this.run(()=>this.loadHistory());}
    async page(delta){this.state.offset=Math.max(0,this.state.offset+delta);await this.run(()=>this.loadHistory());}
}
for(const tag of ['health_tenant_company','health_tenant_setup','health_tenant_history'])registry.category('actions').add(tag,TenantWorkspace);
