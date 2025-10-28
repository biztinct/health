import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { patch } from "@web/core/utils/patch";

/**
 * Patch the CalendarCommonPopover to add Dashboard button and action
 * for Booking calendar popups
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
     * Opens the client dashboard (patient form view)
     */
    async onDashboardAction(e) {
        e.preventDefault();
        e.stopPropagation();

        try {
            const record = this.props.record;
            const orm = this.env.services.orm;
            const action = this.env.services.action;

            // Call the action_open_fso_dashboard method on the backend using ORM service
            // This method is defined in health.fieldservice.order model
            const actionResult = await orm.call(
                'health.fieldservice.order',
                'action_open_fso_dashboard',
                [record.id]
            );

            if (actionResult) {
                // Execute the returned action (which opens the client dashboard)
                action.doAction(actionResult);
                // Close the calendar popup
                this.props.close();
            }
        } catch (error) {
            console.error('Error opening dashboard:', error);
        }
    },
});
