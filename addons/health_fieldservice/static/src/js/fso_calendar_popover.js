import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { patch } from "@web/core/utils/patch";

/**
 * Patch the CalendarCommonPopover to add Dashboard button and action
 * for Booking calendar popups and CRM calendar popups
 */
patch(CalendarCommonPopover, {
    subTemplates: {
        ...CalendarCommonPopover.subTemplates,
        // Override the footer template to use our custom one with Dashboard button
        footer: "health_fieldservice.FSO_CalendarPopover.footer",
    },
});

patch(CalendarCommonPopover.prototype, {
    /**
     * Handle Dashboard button click
     * Opens the appropriate dashboard based on the model
     */
    async onDashboardAction(e) {
        e.preventDefault();
        e.stopPropagation();

        try {
            const record = this.props.record;
            const orm = this.env.services.orm;
            const action = this.env.services.action;

            // Determine which model we're working with
            const modelName = this.props.model?.resModel || record?.resModel || '';
            let actionResult = null;

            if (modelName === 'health.fieldservice.order') {
                // FSO Calendar - call action_open_fso_dashboard
                actionResult = await orm.call(
                    'health.fieldservice.order',
                    'action_open_fso_dashboard',
                    [record.id]
                );
            } else if (modelName === 'crm.lead') {
                // CRM Calendar - call action_open_lead_hub
                actionResult = await orm.call(
                    'crm.lead',
                    'action_open_lead_hub',
                    [record.id]
                );
            } else {
                // Unknown model - try to open a generic form view
                console.warn('[Calendar] Unknown model for dashboard:', modelName);
                actionResult = {
                    type: 'ir.actions.act_window',
                    res_model: modelName,
                    res_id: record.id,
                    views: [[false, 'form']],
                    target: 'current',
                };
            }

            if (actionResult) {
                // Execute the returned action
                action.doAction(actionResult);
                // Close the calendar popup
                this.props.close();
            }
        } catch (error) {
            console.error('Error opening dashboard:', error);
        }
    },
});
