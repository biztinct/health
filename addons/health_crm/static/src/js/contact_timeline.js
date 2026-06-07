/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const TYPE_CONFIG = {
    created:    { color: '#78909C', icon: 'fa-plus-circle',  label: _t('Created') },
    status:     { color: '#2E7D32', icon: 'fa-exchange',     label: _t('Status') },
    activity:   { color: '#E65100', icon: 'fa-tasks',        label: _t('Activity') },
    escalation: { color: '#C62828', icon: 'fa-arrow-up',     label: _t('Escalation') },
    booking:    { color: '#1A237E', icon: 'fa-calendar',     label: _t('Booking') },
    referral:   { color: '#6A1B9A', icon: 'fa-share-alt',    label: _t('Referral') },
};

export class ContactTimeline extends Component {
    static template = "health_crm.ContactTimeline";
    static props = { record: { type: Object }, name: { type: String, optional: true }, readonly: { type: Boolean, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.containerRef = useRef("timeline-container");
        this.state = useState({ events: [], loading: true });

        onWillStart(async () => {
            await this._loadTimeline();
        });

        onMounted(() => {
            this._scrollToEnd();
        });
    }

    get leadId() {
        return this.props.record.resId;
    }

    async _loadTimeline() {
        if (!this.leadId) { this.state.loading = false; return; }
        this.state.loading = true;
        try {
            const events = await this.orm.call("crm.lead", "get_contact_timeline", [this.leadId]);
            this.state.events = events || [];
        } catch (e) {
            console.error("Timeline load error:", e);
            this.state.events = [];
        }
        this.state.loading = false;
    }

    _scrollToEnd() {
        const el = this.containerRef.el;
        if (el) el.scrollLeft = el.scrollWidth;
    }

    getTypeConfig(type) {
        return TYPE_CONFIG[type] || TYPE_CONFIG.created;
    }

    getCardStyle(type) {
        const cfg = this.getTypeConfig(type);
        return `border-left: 3px solid ${cfg.color};`;
    }

    getDotStyle(type) {
        const cfg = this.getTypeConfig(type);
        return `background: ${cfg.color}; box-shadow: 0 0 0 3px ${cfg.color}22;`;
    }

    getIconClass(ev) {
        return ev.icon || this.getTypeConfig(ev.type).icon;
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'Z');
        const day = d.getDate();
        const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        const month = months[d.getMonth()];
        const hours = d.getHours();
        const mins = String(d.getMinutes()).padStart(2, '0');
        if (hours === 0 && mins === '00') return `${day} ${month}`;
        return `${day} ${month}, ${hours}:${mins}`;
    }

    stripHtml(html) {
        if (!html) return '';
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        const text = tmp.textContent || tmp.innerText || '';
        return text.length > 60 ? text.substring(0, 60) + '…' : text;
    }

    onCardClick(ev) {
        const bookingId = parseInt(ev.currentTarget.dataset.bookingId);
        if (!bookingId) return;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_booking_detail',
            name: ev.currentTarget.dataset.title || _t('Booking'),
            target: 'current',
            context: { active_id: bookingId },
        });
    }
}

export const contactTimelineWidget = { component: ContactTimeline };
registry.category("view_widgets").add("contact_timeline", contactTimelineWidget);
