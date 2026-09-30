/** @odoo-module **/
import { patch } from '@web/core/utils/patch';
import { session } from '@web/session';
import { CmsSidebar } from '@health_cms_sidebar/js/cms_sidebar';
patch(CmsSidebar.prototype, {
    get tenantBrand() { return session.tenant_identity || {own:false}; },
});
